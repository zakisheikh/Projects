"""Turns the sorted day (a Bundle) into spoken-style paragraphs using the phrase bank. No AI."""
import re
from dataclasses import dataclass, field
from datetime import timedelta

from . import render


@dataclass
class Bundle:
    failures: list = field(default_factory=list)
    notice_urgent: list = field(default_factory=list)
    dues_urgent: list = field(default_factory=list)
    dues_later: list = field(default_factory=list)
    bills: list = field(default_factory=list)
    statements: list = field(default_factory=list)   # new statements that state no due date
    alerts: list = field(default_factory=list)
    action_urgent: list = field(default_factory=list)
    today: list = field(default_factory=list)        # events for the window this brief covers
    overlaps: list = field(default_factory=list)     # pairs of timed events that collide
    hw_week: list = field(default_factory=list)
    exams: list = field(default_factory=list)
    notices_later: list = field(default_factory=list)
    paid: list = field(default_factory=list)
    health: list = field(default_factory=list)
    admin: list = field(default_factory=list)
    travel: list = field(default_factory=list)
    renewals: list = field(default_factory=list)
    action: list = field(default_factory=list)
    other: list = field(default_factory=list)
    any_homework: bool = False


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
    return d.strftime("%B ") + str(d.day)


def join_list(items, conj="and"):
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    if len(items) == 2:
        return f"{items[0]} {conj} {items[1]}"
    return ", ".join(items[:-1]) + f", {conj} {items[-1]}"


def bullets(lead, items):
    return lead + "\n" + "\n".join(f"• {i}" for i in items)


class Narrator:
    def __init__(self, voice, aliases, today, compact=False, caps=None, partner=(frozenset(), "")):
        self.v, self.aliases, self.today, self.compact = voice, aliases, today, compact
        self.partner_emails, self.partner_label = {e.lower() for e in partner[0]}, partner[1]
        self.caps = {"priority": 3, "events": 6, "list": 8, "week": 8, **(caps or {})}
        if not compact:
            self.caps.update(priority=99, events=12)

    def capped(self, items, key="list"):
        n = self.caps[key]
        if len(items) <= n:
            return items
        return items[:n] + [self.v.say("more_items", k=len(items) - n)]

    def event_text(self, e):
        stamp = "all day" if e.all_day else e.start.strftime("%-I:%M%p").lower()
        mine = (f" ({self.partner_label})" if self.partner_label and e.creator in self.partner_emails
                and self.partner_label.lower() not in e.title.lower() else "")
        return f"{stamp} · {e.title.strip()}{mine}"

    def mail_line(self, m):
        return f"{m.biller or render.sender_name(m)}: {m.subject[:70].strip()}"

    def action_line(self, m):
        return self.mail_line(m) + (f" (by {m.due.strftime('%a %-m/%-d')})" if m.due else "")

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
        names = [w for w, _ in items] if self.compact else [w + (f" ({', '.join(bits)})" if bits else "") for w, bits in items]
        return self.v.say("follow_up", who=join_list(self.capped(names)))

    def paragraphs(self, b, slot, now):
        v, out = self.v, []
        out.append(v.say("greet_morning" if slot < 12 else "greet_noon"))
        aside = v.maybe(f"dow_{now.weekday()}", 0.5)
        if aside:
            out[-1] += " " + aside

        # urgent: things with a deadline in the next day or three, alerts, broken accounts
        follow = self.followup_sentence(b)
        urgent = [f"Account problem, {f.split(':')[0]}: {f.split(':', 1)[-1].strip()[:80]}" for f in b.failures]
        urgent += [render.hw_line(e, self.aliases) for e in b.notice_urgent]
        if follow and b.dues_urgent:
            urgent.append(follow)
        urgent += [f"Action needed, {self.action_line(m)}" for m in b.action_urgent]
        urgent += [f"Alert, {self.mail_line(m)}" for m in b.alerts]
        if urgent:
            shown = urgent[: self.caps["priority"]]
            if len(urgent) > len(shown):
                shown.append(v.say("more_priority", k=len(urgent) - len(shown)))
            out.append(bullets(v.say("priority_open"), shown))
        else:
            out.append(v.say("all_clear"))

        # the schedule window this brief is responsible for
        if b.today:
            items = [self.event_text(e) for e in b.today[: self.caps["events"]]]
            if len(b.today) > self.caps["events"]:
                items.append(v.say("more_items", k=len(b.today) - self.caps["events"]))
            para = bullets(v.say("schedule_morning_open" if slot < 12 else "schedule_open"), items)
            for x, y in b.overlaps:
                para += "\n" + v.say("overlap_warning", a=x.title.strip(), b=y.title.strip(), t=y.start.strftime("%-I:%M %p").replace(":00 ", " "))
            if len(b.today) >= 5 and not self.compact:
                para += "\n" + v.say("quip_busy")
            out.append(para)
        else:
            out.append(v.say("schedule_morning_empty" if slot < 12 else "schedule_empty"))

        # coursework for the week, dated, soonest first (the same in both briefs)
        if b.hw_week:
            items = [render.hw_line(e, self.aliases) for e in sorted(b.hw_week, key=lambda e: e.start)]
            out.append(bullets(v.say("homework_week"), self.capped(items, "week")))
        elif not b.any_homework:
            out.append(v.say("homework_none"))
        if b.exams:
            items = [render.hw_line(e, self.aliases) for e in sorted(b.exams, key=lambda e: e.start)]
            out.append(bullets(v.say("exams_open"), self.capped(items, "week")))
        if b.notices_later:
            items = [render.hw_line(e, self.aliases) for e in sorted(b.notices_later, key=lambda e: e.start)]
            out.append(bullets(v.say("notices_open"), self.capped(items, "week")))

        # bills: one follow-up line wherever it belongs
        if follow and not b.dues_urgent:
            out.append(follow)

        if self.compact:
            out.append(v.say("see_email"))
        else:
            if b.statements:
                out.append(v.say("statements_no_due", items=join_list(sorted({m.biller or render.sender_name(m) for m in b.statements}))))
            for key, items in (("paid_open", [f"{m.biller or render.sender_name(m)}{' · ' + m.amount if m.amount else ''}" for m in b.paid]),
                               ("health_open", [self.mail_line(m) for m in b.health]),
                               ("admin_open", [self.mail_line(m) for m in b.admin]),
                               ("logistics_open", [self.mail_line(m) for m in b.travel]),
                               ("renewals_open", [self.mail_line(m) for m in b.renewals]),
                               ("action_open", [self.action_line(m) for m in b.action]),
                               ("mail_open", [self.mail_line(m) for m in b.other])):
                if items:
                    out.append(bullets(v.say(key), self.capped(items)))
        out.append(v.say("closing_morning" if slot < 12 else "closing_noon"))
        return out
