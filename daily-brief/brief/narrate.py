"""Turns the sorted day (a Bundle) into spoken-style paragraphs using the phrase bank. No AI."""
import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from . import render


@dataclass
class Bundle:
    failures: list = field(default_factory=list)
    hw_week: list = field(default_factory=list)
    notice_urgent: list = field(default_factory=list)
    dues_urgent: list = field(default_factory=list)
    alerts: list = field(default_factory=list)
    today: list = field(default_factory=list)
    prayer: list = field(default_factory=list)
    tomorrow: list = field(default_factory=list)
    notices_later: list = field(default_factory=list)
    dues_later: list = field(default_factory=list)
    health: list = field(default_factory=list)
    bills: list = field(default_factory=list)
    statements: list = field(default_factory=list)   # new statements that state no due date
    paid: list = field(default_factory=list)
    balances: list = field(default_factory=list)
    receipts: list = field(default_factory=list)
    school: list = field(default_factory=list)
    logistics: list = field(default_factory=list)
    info: list = field(default_factory=list)
    important: list = field(default_factory=list)
    any_homework: bool = False


def ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def when(d, today):
    delta = (d - today).days
    if delta == 0:
        return "today"
    if delta == 1:
        return "tomorrow"
    if delta == -1:
        return "yesterday"
    if delta < 0:
        return f"{-delta} days ago"
    if delta < 7:
        return d.strftime("%A")
    return f"{d.strftime('%B')} {ordinal(d.day)}"


def clock(dt):
    s = dt.strftime("%-I:%M %p")
    return s.replace(":00 ", " ")


def join_list(items, conj="and"):
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    if len(items) == 2:
        return f"{items[0]} {conj} {items[1]}"
    return ", ".join(items[:-1]) + f", {conj} {items[-1]}"


def plural(n, noun):
    return f"{n} {noun}" + ("" if n == 1 else "s")


def bullets(lead, items):
    return lead + "\n" + "\n".join(f"• {i}" for i in items)


def place(loc):
    """A short spoken place: the parenthetical abbreviation if there is one, else the first part cut at a word."""
    if not loc or not loc.strip():
        return ""
    m = re.search(r"\(([A-Za-z0-9]{2,10})\)", loc)
    if m:
        return m.group(1)
    first = loc.strip().split(",")[0].split("\n")[0]
    if len(first) <= 30:
        return first
    return first[:30].rsplit(" ", 1)[0]


class Narrator:
    def __init__(self, voice, aliases, today, redact_health=True, compact=False, caps=None, show_tomorrow=False):
        self.v, self.aliases, self.today, self.redact, self.compact = voice, aliases, today, redact_health, compact
        self.show_tomorrow = show_tomorrow
        self.caps = {"priority": 3, "events": 6, "list": 5, "week": 8, **(caps or {})}
        if not compact:
            self.caps.update(priority=99, events=12)

    # ---- phrase helpers
    def event_text(self, e):
        where = f" ({place(e.location)})" if place(e.location) else ""
        stamp = "all day" if e.all_day else e.start.strftime("%-I:%M%p").lower()
        return f"{stamp} · {e.title.strip()}{where}"

    def mail_line(self, m):
        return f"{m.biller or render.sender_name(m)}: {m.subject[:70].strip()}"

    def capped(self, items, key="list"):
        n = self.caps[key]
        if len(items) <= n:
            return items
        k = len(items) - n
        return items[:n] + [self.v.say("more_items", k=k)]

    # ---- sentences for individual items
    def notice_bullet(self, e):
        return render.hw_line(e, self.aliases)

    def followups(self, b):
        """One entry per biller needing action, most urgent first: dues soon, dues later, newly arrived bills."""
        seen, out = set(), []
        for m in list(b.dues_urgent) + list(b.dues_later) + list(b.bills):
            who = m.biller or render.sender_name(m)
            if who in seen:
                continue
            seen.add(who)
            bits = []
            if m.amount:
                bits.append(m.amount)
            if m.due:
                bits.append(("overdue since " if m.due < self.today else "due ") + when(m.due, self.today))
            if m.note == "autopay OFF":
                bits.append("autopay off")
            out.append((who, bits))
        return out

    def followup_sentence(self, b):
        items = self.followups(b)
        if not items:
            return ""
        if self.compact:
            names = [w for w, _ in items]
        else:
            names = [w + (f" ({', '.join(bits)})" if bits else "") for w, bits in items]
        return self.v.say("follow_up", who=join_list(self.capped(names)))

    def alert_bullet(self, m):
        return f"{m.biller or render.sender_name(m)}: {m.subject[:80].strip()}"

    # ---- the brief
    def paragraphs(self, b, slot, now):
        v, out = self.v, []
        out.append(v.say("greet_morning" if slot < 12 else "greet_noon"))
        aside = v.maybe(f"dow_{now.weekday()}", 0.5)
        if aside:
            out[-1] += " " + aside

        # priority items, most urgent first
        follow = self.followup_sentence(b)
        urgent = [f"Account problem, {f.split(':')[0]}: {f.split(':', 1)[-1].strip()[:80]}" for f in b.failures]
        urgent += [self.notice_bullet(e) for e in b.notice_urgent]
        if follow and b.dues_urgent:
            urgent.append(follow)
        urgent += [f"Alert, {self.alert_bullet(m)}" for m in b.alerts]
        if urgent:
            shown = urgent[: self.caps["priority"]]
            if len(urgent) > len(shown):
                shown.append(v.say("more_priority", k=len(urgent) - len(shown)))
            out.append(bullets(v.say("priority_open"), shown))
        else:
            out.append(v.say("all_clear"))

        # schedule
        evs = b.today
        if evs:
            items = [self.event_text(e) for e in evs[: self.caps["events"]]]
            if len(evs) > self.caps["events"]:
                items.append(v.say("more_items", k=len(evs) - self.caps["events"]))
            para = bullets(v.say("schedule_morning_open" if slot < 12 else "schedule_open"), items)
            if len(evs) >= 5 and not self.compact:
                para += "\n" + v.say("quip_busy")
            out.append(para)
        else:
            out.append(v.say("schedule_morning_empty" if slot < 12 else "schedule_empty"))
        if b.prayer and not self.compact:
            out.append(v.say("prayer_line", items=join_list([f"{e.title} at {clock(e.start)}" for e in b.prayer])))
        if b.tomorrow and slot >= 12 and self.show_tomorrow:
            items = self.capped([self.event_text(e) for e in b.tomorrow], "events" if self.compact else "list")
            out.append(bullets(v.say("tomorrow_open"), items))

        extras = []   # compact mode folds the minor stuff into a single closing line
        # coursework for the week, soonest first (the same in both briefs)
        if b.hw_week:
            items = [render.hw_line(e, self.aliases) for e in sorted(b.hw_week, key=lambda e: e.start)]
            out.append(bullets(v.say("homework_week"), self.capped(items, "week")))
        elif not b.any_homework:
            out.append(v.say("homework_none"))
        if b.notices_later and not self.compact:
            items = [render.hw_line(e, self.aliases) for e in b.notices_later]
            out.append(bullets(v.say("notices_open"), self.capped(items)))

        # money: bills are one follow-up line, wherever it belongs
        if follow and not b.dues_urgent:
            out.append(follow)
        if not self.compact:
            if b.statements:
                names = sorted({m.biller or render.sender_name(m) for m in b.statements})
                out.append(v.say("statements_no_due", items=join_list(names)))
            if b.paid:
                items = [f"{m.biller or render.sender_name(m)}{' · ' + m.amount if m.amount else ''}" for m in b.paid]
                out.append(bullets(v.say("paid_open"), self.capped(items)))
            items = [f"{m.biller} · {m.amount}" for m in b.balances if m.amount]
            if items:
                out.append(bullets(v.say("balance_line"), items))

        # health
        if b.health:
            if self.compact:
                extras.append(plural(len(b.health), "medical item") + " (details by email)")
            elif self.redact:
                out.append(v.say("health_redacted", thing=plural(len(b.health), "medical item")))
            else:
                out.append(bullets(v.say("health_open"), self.capped([self.mail_line(m) for m in b.health])))

        # mail
        if self.compact:
            n_other = len(b.important) + len(b.school) + len(b.logistics) + len(b.info)
            if n_other:
                extras.append(plural(n_other, "message") + " worth a look")
        else:
            for key, items in (("school_open", b.school), ("logistics_open", b.logistics), ("info_open", b.info), ("mail_open", b.important)):
                if items:
                    out.append(bullets(v.say(key), self.capped([self.mail_line(m) for m in items])))
            if b.receipts:
                sources = join_list(sorted({render.sender_name(m) for m in b.receipts})[:4])
                out.append(v.say("receipts_line" if len(b.receipts) > 1 else "receipt_one", n=len(b.receipts), sources=sources))

        if self.compact:
            if extras:
                out.append(v.say("also_line", items=join_list(extras)))
            out.append(v.say("see_email"))
        out.append(v.say("closing_morning" if slot < 12 else "closing_noon"))
        return out
