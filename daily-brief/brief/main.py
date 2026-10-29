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
    hw = re.compile(cfg["calendar"]["homework_pattern"])
    skip = set(cfg["calendar"]["exclude_calendars"])
    out = []
    for cal in g.calendars():
        name = cal.get("summaryOverride") or cal.get("summary", "")
        if name in skip or not cal.get("selected", True):
            continue
        for raw in g.events(cal["id"], start, end):
            if raw.get("status") == "cancelled":
                continue
            out.append(parse_event(raw, name, tz, hw))
    out.sort(key=lambda e: (e.start, e.title))
    return out


def collect_mail(g, tz, since, today, rules, n_sender):
    q = f"after:{int(since.timestamp())} -in:spam -in:trash -category:promotions -category:social"
    mails = []
    for mid in g.search(q, 100):
        m = parse_mail(g.message(mid), tz)
        m.categories = classify.categorize(m, rules, n_sender)
        if {"health", "card", "bill"} & set(m.categories):
            full = parse_mail(g.message(mid, full=True), tz)
            text = f"{m.subject} {full.body or m.snippet}"
            m.amount = classify.extract_amount(text)
            m.due = classify.extract_due(text, today)
        mails.append(m)
    return mails


def assemble(events, mails, now, slot, cfg):
    today, n = now.date(), cfg["mail"]["max_per_section"]
    tomorrow = today + timedelta(days=1)
    horizon = today + timedelta(days=cfg["calendar"]["lookahead_days"])

    def on(ev, d):  # event touches day d
        return ev.start.date() <= d < max(ev.end.date(), ev.start.date() + timedelta(days=1))

    rest = [e for e in events if on(e, today) and (e.all_day or e.end > now)]
    nxt = [e for e in events if on(e, tomorrow)]
    hw = [e for e in events if e.homework and today <= e.start.date() <= horizon]

    attention = []
    for e in hw:
        if e.start.date() <= tomorrow:
            attention.append("HOMEWORK  " + render.event_line(e, with_day=True))
    for m in mails:
        if m.due and m.due <= today + timedelta(days=3):
            attention.append("BILL DUE  " + render.mail_line(m))
        elif "security" in m.categories:
            attention.append("SECURITY  " + render.mail_line(m))
        elif m.categories and re.search(r"(?i)fraud|unusual|suspicious|declined|failed|past due|final notice|denied", m.subject):
            attention.append("ALERT  " + render.mail_line(m))

    sections = [("attention", attention),
                ("today", [render.event_line(e) for e in rest]),
                ("tomorrow", [render.event_line(e) for e in nxt] if slot >= 12 else []),
                ("homework", [render.event_line(e, with_day=True) for e in hw])]
    shown = set()
    for cat in ("health", "card", "bill", "school", "logistics"):
        items = [m for m in mails if cat in m.categories and m.id not in shown]
        shown.update(m.id for m in items)
        sections.append((cat, [render.mail_line(m) for m in items[:n]]))
    rest_imp = [m for m in mails if m.important and m.unread and m.id not in shown]
    sections.append(("important", [render.mail_line(m) for m in rest_imp[:n]]))
    return sections


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

    g = google or Google(*(os.environ[k] for k in
                           ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN")))
    day_end = datetime.combine(now.date() + timedelta(days=cfg["calendar"]["lookahead_days"] + 1), time.min, tz)
    events = collect_events(g, cfg, tz, datetime.combine(now.date(), time.min, tz), day_end)
    rules, n_sender = classify.compile_rules(cfg)
    since = window_start(now, slot, slots)
    mails = collect_mail(g, tz, since, now.date(), rules, n_sender)

    sections = assemble(events, mails, now, slot, cfg)
    unread = sum(m.unread for m in mails)
    label = "Morning" if slot < 12 else "Midday"
    header = f"{label} brief — {now:%a %b %-d}"
    footer = f"{len(mails)} new emails since {since:%-I%p} ({unread} unread). Generated by rules, no AI."
    text, html = render.build(sections, header, footer)

    if args.dry_run:
        print(text)
        return 0
    to = cfg.get("recipient") or os.environ.get("BRIEF_TO") or g.my_address()
    g.send(to, header, text, html)
    print(f"Sent '{header}' to {to}")
    return 0


if __name__ == "__main__":
    sys.exit(run())
