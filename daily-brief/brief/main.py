import argparse
import os
import re
import sys
import tomllib
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from . import classify, render
from .google import Google
from .parse import parse_event, parse_mail

ROOT = Path(__file__).resolve().parent.parent
ALERT_WORDS = re.compile(r"(?i)fraud|unusual|suspicious|declin|failed|past due|overdue|final notice|denied")


def load_config(path=None):
    with open(path or ROOT / "config.toml", "rb") as f:
        return tomllib.load(f)


def pick_slot(now, slots, grace_hours=1):
    """Return the slot hour this run belongs to, or None. GitHub cron can lag, so allow a grace window."""
    for h in slots:
        slot = now.replace(hour=h, minute=0, second=0, microsecond=0)
        if timedelta(0) <= now - slot < timedelta(hours=grace_hours):
            return h
    return None


def window_start(now, slot, slots):
    prev = [h for h in sorted(slots) if h < slot]
    if prev:
        return now.replace(hour=prev[-1], minute=0, second=0, microsecond=0)
    return (now - timedelta(days=1)).replace(hour=max(slots), minute=0, second=0, microsecond=0)


def collect_events(g, cfg, tz, start, end):
    cal_cfg = cfg["calendar"]
    hw = re.compile(cal_cfg["homework_pattern"])
    skip, hw_cals = set(cal_cfg["exclude_calendars"]), set(cal_cfg.get("homework_calendars", []))
    out = []
    for cal in g.calendars():
        name = cal.get("summaryOverride") or cal.get("summary", "")
        if name in skip or not cal.get("selected", True):
            continue
        for raw in g.events(cal["id"], start, end):
            if raw.get("status") != "cancelled":
                out.append(parse_event(raw, name, tz, hw, name in hw_cals))
    return out


def enrich(g, mid, tz, account, rules, n_sender, billers):
    m = parse_mail(g.message(mid), tz)
    m.account = account
    hit = classify.match_biller(m, billers)
    if hit:
        m.biller, m.kind, m.event = hit
        if m.event == "ignore":
            m.ignored = True
    m.categories = classify.categorize(m, rules, n_sender)
    needs_body = m.event in ("due", "statement", "paid") or {"health", "bill", "card"} & set(m.categories)
    if needs_body and not m.ignored:
        full = parse_mail(g.message(mid, full=True), tz)
        text = f"{m.subject} {full.body or m.snippet}"
        m.amount = classify.extract_amount(text)
        m.due = classify.extract_due(text, m.when.date())
        m.note = classify.extract_autopay(text) or ""
    if m.event == "balance":
        m.amount = classify.first_amount(m.subject + " " + m.snippet)
    return m


def collect_mail(g, tz, since, account, rules, n_sender, billers):
    q = f"after:{int(since.timestamp())} -in:spam -in:trash -category:promotions -category:social"
    return [enrich(g, mid, tz, account, rules, n_sender, billers) for mid in g.search(q, 100)]


def collect_open_bills(g, tz, now, days, account, rules, n_sender, billers):
    """Look back for 'payment due' notices that no later 'paid' notice has settled."""
    since = now - timedelta(days=days)
    q = (f"after:{int(since.timestamp())} -in:spam -in:trash "
         "(subject:(due OR statement OR bill OR invoice OR payment OR rent OR autopay OR overdue))")
    mails = [enrich(g, mid, tz, account, rules, n_sender, billers) for mid in g.search(q, 150)]
    paid = [m for m in mails if m.event == "paid"]
    out = []
    for m in mails:
        if m.event not in ("due", "statement") or m.due is None:
            continue
        settled = any(p.biller == m.biller and p.account == m.account and p.when >= m.when for p in paid)
        later = any(o.biller == m.biller and o.account == m.account and o.event in ("due", "statement")
                    and o.due and o.when > m.when for o in mails)
        if not settled and not later:
            out.append(m)
    return out


def gather(name, g, cfg, tz, now, since, day_end, rules, n_sender, billers):
    events = collect_events(g, cfg, tz, datetime.combine(now.date(), time.min, tz), day_end)
    mails = collect_mail(g, tz, since, name, rules, n_sender, billers)
    open_bills = collect_open_bills(g, tz, now, cfg["bills"]["lookback_days"], name, rules, n_sender, billers)
    return events, mails, open_bills


def tag(line, account, multi):
    return f"[{account}] {line}" if multi and account else line


def assemble(events, mails, open_bills, failures, now, slot, cfg, multi=False):
    today, n = now.date(), cfg["mail"]["max_per_section"]
    tomorrow = today + timedelta(days=1)
    horizon = today + timedelta(days=cfg["calendar"]["lookahead_days"])
    soon = today + timedelta(days=cfg["bills"]["due_soon_days"])

    seen, uniq = set(), []
    for e in sorted(events, key=lambda e: (e.start, e.title)):   # shared calendars appear in several accounts
        key = (e.title, e.start, e.end)
        if key not in seen:
            seen.add(key)
            uniq.append(e)

    def on(ev, d):
        return ev.start.date() <= d < max(ev.end.date(), ev.start.date() + timedelta(days=1))

    rest = [e for e in uniq if on(e, today) and (e.all_day or e.end > now)]
    nxt = [e for e in uniq if on(e, tomorrow)]
    hw = [e for e in uniq if e.homework and today <= e.start.date() <= horizon]
    mails = [m for m in mails if not m.ignored]

    def bill_line(m):
        return tag(render.mail_line(m, who=m.biller), m.account, multi)

    def is_alert(m):
        return m.event == "alert" or "security" in m.categories or bool(m.categories and ALERT_WORDS.search(m.subject))

    dues = sorted(open_bills, key=lambda m: m.due)
    attention = [f"ACCOUNT  {f}" for f in failures]
    attention += ["HOMEWORK  " + render.event_line(e, with_day=True) for e in hw if e.start.date() <= tomorrow]
    attention += ["DUE  " + bill_line(m) for m in dues if m.due <= soon]
    attention += ["ALERT  " + tag(render.mail_line(m, who=m.biller), m.account, multi) for m in mails if is_alert(m)]

    # Anything already listed above must not repeat in the per-category sections.
    shown = {(m.account, m.id) for m in dues} | {(m.account, m.id) for m in mails if is_alert(m)}

    def take(pred):
        items = [m for m in mails if (m.account, m.id) not in shown and pred(m)]
        shown.update((m.account, m.id) for m in items)
        return items

    health = take(lambda m: m.kind == "health" or "health" in m.categories)
    statements = take(lambda m: m.event in ("statement", "due") or ("bill" in m.categories) or ("card" in m.categories))
    paid = take(lambda m: m.event == "paid")
    bal = {}
    for m in take(lambda m: m.event == "balance"):
        k = (m.account, m.biller)
        if k not in bal or m.when > bal[k].when:
            bal[k] = m
    receipts = take(lambda m: m.event == "receipt" or "receipt" in m.categories)
    school = take(lambda m: "school" in m.categories)
    logistics = take(lambda m: "logistics" in m.categories)
    infos = take(lambda m: m.event == "info")
    important = take(lambda m: m.important and m.unread)

    L = lambda items: [tag(render.mail_line(m, who=m.biller), m.account, multi) for m in items[:n]]
    sections = [("attention", attention),
                ("today", [render.event_line(e) for e in rest]),
                ("tomorrow", [render.event_line(e) for e in nxt] if slot >= 12 else []),
                ("homework", [render.event_line(e, with_day=True) for e in hw]),
                ("dues", [bill_line(m) for m in dues if m.due > soon]),
                ("health", L(health)), ("bills", L(statements)), ("paid", L(paid)),
                ("balances", [tag(f"{m.biller}: {m.amount or 'new balance alert, see email'} (latest)", m.account, multi) for m in bal.values()]),
                ("school", L(school)), ("logistics", L(logistics)),
                ("receipts", [f"{len(receipts)} receipt(s): " + ", ".join(sorted({render.sender_name(m) for m in receipts})[:6])] if receipts else []),
                ("info", L(infos)), ("important", L(important))]
    return sections


def build_accounts(cfg, google):
    """-> list of (name, client|None, error|None). `google` injects fakes for tests."""
    out = []
    for a in cfg["accounts"]:
        if google is not None:
            g = google.get(a["name"]) if isinstance(google, dict) else google
            out.append((a["name"], g, None if g else "no client"))
            continue
        token = os.environ.get(a["token_env"], "")
        if not token:
            out.append((a["name"], None, f"secret {a['token_env']} is not set"))
        else:
            out.append((a["name"], Google(os.environ["GOOGLE_CLIENT_ID"], os.environ["GOOGLE_CLIENT_SECRET"], token), None))
    return out


def run(argv=None, google=None, now=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="ignore the slot schedule")
    ap.add_argument("--dry-run", action="store_true", help="print instead of emailing")
    ap.add_argument("--config")
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    tz = ZoneInfo(cfg["timezone"])
    now = now or datetime.now(tz)
    slots = cfg["slots"]
    slot = pick_slot(now, slots)
    if slot is None:
        if not args.force:
            print(f"{now:%H:%M} is not a briefing slot {slots}; nothing to do.")
            return 0
        slot = min((h for h in slots if h <= now.hour), default=slots[0])

    accounts = build_accounts(cfg, google)
    rules, n_sender = classify.compile_rules(cfg)
    billers = classify.compile_billers(cfg)
    since = window_start(now, slot, slots)
    day_end = datetime.combine(now.date() + timedelta(days=cfg["calendar"]["lookahead_days"] + 1), time.min, tz)

    events, mails, open_bills, failures = [], [], [], []
    for name, g, err in accounts:
        try:
            if err:
                raise RuntimeError(err)
            e, m, b = gather(name, g, cfg, tz, now, since, day_end, rules, n_sender, billers)
            events += e; mails += m; open_bills += b
        except Exception as ex:   # one broken login must not silence the others
            failures.append(f"{name}: {str(ex)[:160]}")

    sections = assemble(events, mails, open_bills, failures, now, slot, cfg, multi=len(accounts) > 1)
    unread = sum(m.unread for m in mails)
    label = "Morning" if slot < 12 else "Midday"
    header = f"{label} brief — {now:%a %b %-d}"
    footer = f"{len(mails)} new emails across {len(accounts)} account(s) since {since:%-I%p} ({unread} unread). Rules only, no AI."
    text, html = render.build(sections, header, footer)

    if args.dry_run:
        print(text)
        return 0
    sender = next(((n, g) for (n, g, e), a in zip(accounts, cfg["accounts"]) if g and a.get("send_from")), None) \
        or next(((n, g) for n, g, e in accounts if g), None)
    if not sender:
        print("No usable account to send from.", file=sys.stderr)
        return 1
    to = cfg.get("recipient") or os.environ.get("BRIEF_TO") or sender[1].my_address()
    sender[1].send(to, header, text, html)
    print(f"Sent '{header}' to {to} ({len(failures)} account failure(s))")
    return 1 if failures and len(failures) == len(accounts) else 0


if __name__ == "__main__":
    sys.exit(run())
