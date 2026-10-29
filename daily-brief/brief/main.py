import argparse
import os
import re
import sys
import tomllib
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from . import classify, render, state as stmod, telegram
from .voice import Voice
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
    compact = set(cal_cfg.get("compact_calendars", []))
    tag_hw = cal_cfg.get("course_tag_is_homework", True)
    out = []
    for cal in g.calendars():
        name = cal.get("summaryOverride") or cal.get("summary", "")
        if name in skip or not cal.get("selected", True):
            continue
        for raw in g.events(cal["id"], start, end):
            if raw.get("status") != "cancelled":
                out.append(parse_event(raw, name, tz, hw, name in hw_cals, name in compact, tag_hw))
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


def assemble(events, mails, open_bills, failures, now, slot, cfg, multi=False, trace=None):
    today, n = now.date(), cfg["mail"]["max_per_section"]
    tomorrow = today + timedelta(days=1)
    horizon = today + timedelta(days=cfg["calendar"]["lookahead_days"])
    soon = today + timedelta(days=cfg["bills"]["due_soon_days"])

    by_key, uniq = {}, []
    for e in sorted(events, key=lambda e: (e.start, e.title)):   # same event in several calendars/logins -> once
        key = (e.title, e.start, e.end)
        if key in by_key:
            k = by_key[key]
            k.homework |= e.homework
            k.course, k.hint = k.course or e.course, k.hint or e.hint
            k.compact &= e.compact
        else:
            by_key[key] = e
            uniq.append(e)

    def on(ev, d):
        return ev.start.date() <= d < max(ev.end.date(), ev.start.date() + timedelta(days=1))

    aliases = cfg["calendar"].get("course_aliases", {})
    live = [e for e in uniq if on(e, today) and (e.all_day or e.end > now)]
    rest = [e for e in live if not e.compact and not e.homework]
    prayer = [e for e in live if e.compact and not e.all_day]
    nxt = [e for e in uniq if on(e, tomorrow) and not e.compact and not e.homework]
    notice_re = re.compile(cfg["calendar"].get("notice_pattern", r"(?!x)x"))

    def is_notice(e):   # Canvas items that are not assignments: polls, advising/enrollment notices, timed announcements
        return e.homework and (not e.all_day or bool(notice_re.search(e.title)))

    hw = [e for e in uniq if e.homework and not is_notice(e) and today <= e.start.date() <= horizon]
    notices = [e for e in uniq if is_notice(e) and today <= e.start.date() <= horizon]
    dropped = [m for m in mails if m.ignored]
    mails = [m for m in mails if not m.ignored]
    route = {}   # (account, id) -> where the mail went, for --explain

    def bill_line(m):
        return tag(render.mail_line(m, who=m.biller), m.account, multi)

    def is_alert(m):
        return m.event == "alert" or "security" in m.categories or bool(m.categories and ALERT_WORDS.search(m.subject))

    dues = sorted(open_bills, key=lambda m: m.due)
    attention = [f"{render.icon('ACCOUNT')}Account fault: {f}" for f in failures]
    attention += [render.icon("HOMEWORK") + "Coursework due: " + render.hw_line(e, aliases) for e in hw if e.start.date() <= tomorrow]
    attention += [render.icon("NOTICE") + "Notice: " + render.hw_line(e, aliases) for e in notices if e.hint and e.start.date() <= tomorrow]
    attention += [render.icon("DUE") + "Payment due: " + bill_line(m) for m in dues if m.due <= soon]
    attention += [render.icon("ALERT") + "Alert: " + tag(render.mail_line(m, who=m.biller), m.account, multi) for m in mails if is_alert(m)]
    for m in dues:
        route[(m.account, m.id)] = "Needs attention (due soon)" if m.due <= soon else "Upcoming payments"
    for m in mails:
        if is_alert(m):
            route[(m.account, m.id)] = "Needs attention (alert)"

    # Anything already listed above must not repeat in the per-category sections.
    shown = {(m.account, m.id) for m in dues} | {(m.account, m.id) for m in mails if is_alert(m)}

    def take(pred, section):
        items = [m for m in mails if (m.account, m.id) not in shown and pred(m)]
        shown.update((m.account, m.id) for m in items)
        for m in items:
            route[(m.account, m.id)] = section
        return items

    health = take(lambda m: m.kind == "health" or "health" in m.categories, "Health")
    statements = take(lambda m: m.event in ("statement", "due") or ("bill" in m.categories) or ("card" in m.categories), "New bills & statements")
    paid = take(lambda m: m.event == "paid", "Payments confirmed")
    bal = {}
    for m in take(lambda m: m.event == "balance", "Balances (latest only)"):
        k = (m.account, m.biller)
        if k not in bal or m.when > bal[k].when:
            bal[k] = m
    receipts = take(lambda m: m.event == "receipt" or "receipt" in m.categories, "Receipts (counted)")
    school = take(lambda m: "school" in m.categories, "School mail")
    logistics = take(lambda m: "logistics" in m.categories, "Deliveries & travel")
    infos = take(lambda m: m.event == "info", "Other account notices")
    important = take(lambda m: m.important and m.unread, "Other important mail")

    L = lambda items: [tag(render.mail_line(m, who=m.biller), m.account, multi) for m in items[:n]]
    sections = [("attention", attention),
                ("today", [render.event_line(e) for e in rest]),
                ("prayer", ["  ·  ".join(f"{e.title} {render.fmt_time(e)}" for e in prayer)] if prayer else []),
                ("tomorrow", [render.event_line(e) for e in nxt] if slot >= 12 else []),
                ("homework", [render.hw_line(e, aliases) for e in hw if e.start.date() > tomorrow]),
                ("notices", [render.hw_line(e, aliases) for e in notices if not (e.hint and e.start.date() <= tomorrow)]),
                ("dues", [bill_line(m) for m in dues if m.due > soon]),
                ("health", L(health)), ("bills", L(statements)), ("paid", L(paid)),
                ("balances", [tag(f"{m.biller}: {m.amount or 'new balance alert, see email'} (latest)", m.account, multi) for m in bal.values()]),
                ("school", L(school)), ("logistics", L(logistics)),
                ("receipts", [f"{len(receipts)} receipt(s): " + ", ".join(sorted({render.sender_name(m) for m in receipts})[:6])] if receipts else []),
                ("info", L(infos)), ("important", L(important))]
    if trace is not None:
        for e in uniq:
            where = ("Prayer times" if e in prayer else "Rest of today" if e in rest else "Tomorrow" if e in nxt else
                     ("Needs attention (due ≤ tomorrow)" if e.start.date() <= tomorrow else "Homework later this week") if e in hw else
                     "Class notices" if e in notices else
                     "not shown (already over, or outside the window)")
            trace.append(("cal" if not e.homework else "school", f"{e.calendar}", f"{e.title.strip()[:60]}", where))
        for m in dropped:
            trace.append(("mail", f"{m.account}: {render.sender_name(m)[:28]}", m.subject[:60], f"dropped by rule: {m.biller} → ignore"))
        for m in mails:
            how = f"{m.biller}/{m.event}" if m.biller else (",".join(m.categories) or "no rule")
            trace.append(("mail", f"{m.account}: {render.sender_name(m)[:28]}", m.subject[:60],
                          f"{route.get((m.account, m.id), 'not shown (no section wanted it)')}   [matched: {how}]"))
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


def make_leads(voice, sections, hw_any):
    present = {k for k, lines in sections if lines}
    leads = {}
    leads["attention"] = voice.say("attention_intro") if "attention" in present else voice.say("all_clear")
    leads["today"] = voice.say("today_intro") if "today" in present else ""
    if "today" not in present:
        leads["today"] = voice.say("today_empty")
    for key, bank in (("tomorrow", "tomorrow_intro"), ("homework", "homework_intro"), ("dues", "dues_intro"),
                      ("notices", "notices_intro"), ("bills", "bills_intro"), ("paid", "paid_intro"), ("health", "health_intro"),
                      ("important", "mail_intro")):
        if key in present:
            leads[key] = voice.say(bank)
    return leads


def telegram_blocks(sections, leads, redact_health):
    blocks = []
    for key, lines in sections:
        if key == "attention":
            blocks.append((render.title(key), leads.get(key, ""), lines))
        elif not lines or key in ("receipts", "info", "balances"):
            continue
        elif key == "health" and redact_health:
            blocks.append((render.title(key), "", [f"{len(lines)} item(s). Details are in your email."]))
        else:
            blocks.append((render.title(key), leads.get(key, ""), lines))
    return blocks


def run(argv=None, google=None, now=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="ignore the slot schedule")
    ap.add_argument("--dry-run", action="store_true", help="print instead of sending")
    ap.add_argument("--config")
    ap.add_argument("--explain", action="store_true", help="also print where every input came from and where it went")
    ap.add_argument("--state", help="path to state.json (kept on the brief-state branch in CI)")
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

    st = stmod.load(args.state)
    accounts = build_accounts(cfg, google)
    rules, n_sender = classify.compile_rules(cfg)
    billers = classify.compile_billers(cfg)
    since = window_start(now, slot, slots)
    prev = stmod.last_sent(st, tz)
    if prev and now - timedelta(days=3) <= prev <= now:
        since = prev                      # catch up on anything missed since the last brief
    seen = st.get("seen", {})
    day_end = datetime.combine(now.date() + timedelta(days=cfg["calendar"]["lookahead_days"] + 1), time.min, tz)

    events, mails, open_bills, failures = [], [], [], []
    for name, g, err in accounts:
        try:
            if err:
                raise RuntimeError(err)
            e, m, b = gather(name, g, cfg, tz, now, since, day_end, rules, n_sender, billers)
            events += e
            mails += [x for x in m if f"{x.account}:{x.id}" not in seen]
            open_bills += b
        except Exception as ex:   # one broken login must not silence the others
            failures.append(f"{name}: {str(ex)[:160]}")

    trace = [] if args.explain else None
    sections = assemble(events, mails, open_bills, failures, now, slot, cfg, multi=len(accounts) > 1, trace=trace)
    pcfg = cfg.get("persona", {})
    render.USE_EMOJI = bool(cfg.get("style", {}).get("emoji", False))
    voice = Voice.load(pcfg.get("name", "Bruno"), pcfg.get("user", ""), f"{now:%Y-%m-%d}-{slot}", st.get("phrases"),
                       address=pcfg.get("address", "sir"))
    greeting = voice.say("greet_morning" if slot < 12 else "greet_noon")
    closing = voice.say("closing_morning" if slot < 12 else "closing_noon")
    leads = make_leads(voice, sections, True)
    label = "Morning" if slot < 12 else "Midday"
    header = f"{label} brief — {now:%a %b %-d}"
    unread = sum(m.unread for m in mails)
    footer = f"{len(mails)} new emails checked ({unread} unread). Rules only, no AI."
    text, html = render.build(sections, header, greeting, closing, footer, leads)
    tg = telegram.fmt(greeting, telegram_blocks(sections, leads, cfg["delivery"].get("telegram_redact_health", True)), closing)

    if args.dry_run:
        print(text)
        if trace is not None:
            print("\n--- where every input went ---")
            for icon, src, what, where in trace:
                print(f"{icon} {src} | {what}\n     → {where}")
        print("\n--- telegram preview ---\n" + tg.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", ""))
        return 0

    sent, problems = [], []
    for ch in cfg["delivery"]["channels"]:
        try:
            if ch == "telegram":
                telegram.send(os.environ["TELEGRAM_BOT_TOKEN"], os.environ["TELEGRAM_CHAT_ID"], tg)
            elif ch == "email":
                sender = next(((n, g) for (n, g, e), a in zip(accounts, cfg["accounts"]) if g and a.get("send_from")), None) \
                    or next(((n, g) for n, g, e in accounts if g), None)
                if not sender:
                    raise RuntimeError("no usable account to send from")
                to = cfg.get("recipient") or os.environ.get("BRIEF_TO") or sender[1].my_address()
                body_text = text + ("\n\nDelivery problems: " + "; ".join(problems) if problems else "")
                sender[1].send(to, header, body_text, html)
            else:
                raise RuntimeError(f"unknown channel {ch}")
            sent.append(ch)
        except Exception as ex:
            problems.append(f"{ch}: {str(ex)[:140]}")
    print(f"Sent via {sent or 'nothing'}; problems: {problems or 'none'}; account failures: {len(failures)}")
    if sent:
        st["last_sent"] = now.isoformat()
        st["seen"] = stmod.prune_seen({**seen, **{f"{m.account}:{m.id}": now.isoformat() for m in mails}}, now)
        st["phrases"] = {**st.get("phrases", {}), **voice.used}
        late = int((now - now.replace(hour=slot, minute=0, second=0, microsecond=0)).total_seconds() // 60)
        st["history"] = (st.get("history", []) + [f"{now:%Y-%m-%d} slot {slot}h started {late}m after slot, via {','.join(sent)}"])[-30:]
        stmod.save(args.state, st)
    return 0 if sent else 1


if __name__ == "__main__":
    sys.exit(run())
