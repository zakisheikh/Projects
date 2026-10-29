"""Turns the sorted day (a Bundle) into spoken-style paragraphs using the phrase bank. No AI."""
import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from . import render


@dataclass
class Bundle:
    failures: list = field(default_factory=list)
    hw_urgent: list = field(default_factory=list)
    notice_urgent: list = field(default_factory=list)
    dues_urgent: list = field(default_factory=list)
    alerts: list = field(default_factory=list)
    today: list = field(default_factory=list)
    prayer: list = field(default_factory=list)
    tomorrow: list = field(default_factory=list)
    hw_later: list = field(default_factory=list)
    notices_later: list = field(default_factory=list)
    dues_later: list = field(default_factory=list)
    health: list = field(default_factory=list)
    bills: list = field(default_factory=list)
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
    def __init__(self, voice, aliases, today, redact_health=True, compact=False, caps=None):
        self.v, self.aliases, self.today, self.redact, self.compact = voice, aliases, today, redact_health, compact
        self.caps = {"priority": 3, "events": 4, "list": 5, **(caps or {})}
        if not compact:
            self.caps.update(priority=99, events=12)

    # ---- phrase helpers
    def event_text(self, e):
        where = f" ({place(e.location)})" if place(e.location) else ""
        if e.all_day:
            return f"{e.title.strip()} (all day){where}"
        return f"{e.title.strip()} at {clock(e.start)}{where}"

    def hw_text(self, e):
        course = render.course_name(e.course, self.aliases) if e.course else ""
        title = re.sub(r"\s*\((classic|new)\)\s*$", "", e.title.strip(), flags=re.I)
        return title + (f" for {course}" if course else "")

    def mail_text(self, m):
        return f"{m.biller or render.sender_name(m)} (\"{m.subject[:60].strip()}\")"

    def capped(self, items, key="list"):
        n = self.caps[key]
        if len(items) <= n:
            return items
        k = len(items) - n
        return items[:n] + [self.v.say("more_items", k=k)]

    # ---- sentences for individual items
    def hw_sentence(self, e, notice=False):
        d = e.start.date()
        return self.v.say("notice_urgent" if notice else "hw_urgent", item=self.hw_text(e),
                          when=when(d, self.today), hint=f" {e.hint}" if e.hint else "")

    def bill_sentence(self, m):
        who = m.biller or render.sender_name(m)
        auto = ""
        if m.note == "autopay OFF":
            auto = self.v.say("autopay_off")
        elif m.note == "autopay on":
            auto = self.v.say("autopay_on")
        amount = m.amount
        if m.due < self.today:
            return self.v.say("bill_late", who=who, when=when(m.due, self.today), amount_part=f" ({amount})" if amount else "")
        key = "bill_due_amt" if amount else "bill_due_noamt"
        return self.v.say(key, who=who, amount=amount or "", when=when(m.due, self.today), auto=auto)

    def alert_sentence(self, m):
        return self.v.say("alert_item", who=m.biller or render.sender_name(m), subject=m.subject[:80].strip())

    # ---- the brief
    def paragraphs(self, b, slot, now):
        v, out = self.v, []
        out.append(v.say("greet_morning" if slot < 12 else "greet_noon"))
        aside = v.maybe(f"dow_{now.weekday()}", 0.5)
        if aside:
            out[-1] += " " + aside

        # priority items, most urgent first
        sentences = [v.say("account_fault", account=f.split(":")[0], why=f.split(":", 1)[-1].strip()[:80]) for f in b.failures]
        sentences += [self.hw_sentence(e) for e in b.hw_urgent]
        sentences += [self.hw_sentence(e, notice=True) for e in b.notice_urgent]
        sentences += [self.bill_sentence(m) for m in b.dues_urgent]
        sentences += [self.alert_sentence(m) for m in b.alerts]
        if sentences:
            shown = sentences[: self.caps["priority"]]
            out.append(v.say("priority_open") + "\n" + "\n".join(shown))
            if len(sentences) > len(shown):
                out[-1] += "\n" + v.say("more_priority", k=len(sentences) - len(shown))
        else:
            out.append(v.say("all_clear"))

        # schedule
        evs = b.today
        if evs:
            items = [self.event_text(e) for e in evs[: self.caps["events"]]]
            if len(evs) > self.caps["events"]:
                items.append(v.say("more_items", k=len(evs) - self.caps["events"]))
            para = v.say("schedule_open", items=join_list(items))
            if len(evs) >= 5 and not self.compact:
                para += " " + v.say("quip_busy")
            out.append(para)
        else:
            out.append(v.say("schedule_empty"))
        if b.prayer and not self.compact:
            out.append(v.say("prayer_line", items=join_list([f"{e.title} at {clock(e.start)}" for e in b.prayer])))
        if b.tomorrow and slot >= 12:
            items = self.capped([self.event_text(e) for e in b.tomorrow], "events" if self.compact else "list")
            out.append(v.say("tomorrow_open", items=join_list(items)))

        extras = []   # compact mode folds the minor stuff into a single closing line
        # coursework
        if self.compact:
            if b.hw_later:
                extras.append(plural(len(b.hw_later), "more assignment") + " this week")
        else:
            if b.hw_later:
                items = [f"{self.hw_text(e)} on {when(e.start.date(), self.today)}" for e in b.hw_later]
                out.append(v.say("homework_open", items=join_list(self.capped(items))))
            elif not b.any_homework:
                out.append(v.say("homework_none"))
            if b.notices_later:
                items = [f"{self.hw_text(e)}, {when(e.start.date(), self.today)}" for e in b.notices_later]
                out.append(v.say("notices_open", items=join_list(self.capped(items))))

        # money
        money = []
        if b.dues_later:
            if self.compact:
                extras.append(plural(len(b.dues_later), "other payment") + " coming up")
            else:
                items = [f"{m.biller or render.sender_name(m)}, {m.amount + ' ' if m.amount else ''}by {when(m.due, self.today)}" for m in b.dues_later]
                money.append(v.say("dues_open", items=join_list(self.capped(items))))
        if not self.compact:
            if b.bills:
                money.append(v.say("bills_open", items=join_list(self.capped([self.mail_text(m) for m in b.bills]))))
            if b.paid:
                items = [f"{m.biller or render.sender_name(m)}{', ' + m.amount if m.amount else ''}" for m in b.paid]
                money.append(v.say("paid_open", items=join_list(self.capped(items))))
            if b.balances:
                items = [f"{m.biller} at {m.amount}" for m in b.balances if m.amount]
                if items:
                    money.append(v.say("balance_line", items=join_list(items)))
        if money:
            out.append((v.maybe("transition_money", 0.6) + " " + " ".join(money)).strip())

        # health
        if b.health:
            if self.compact:
                extras.append(plural(len(b.health), "medical item") + " (details by email)")
            elif self.redact:
                out.append(v.say("health_redacted", thing=plural(len(b.health), "medical item")))
            else:
                out.append(v.say("health_open", items=join_list(self.capped([self.mail_text(m) for m in b.health]))))

        # mail
        mail = []
        if self.compact:
            n = len(b.important) + len(b.school) + len(b.logistics) + len(b.info) + len(b.bills)
            if n:
                extras.append(plural(n, "message") + " worth a look")
        else:
            for key, items in (("school_open", b.school), ("logistics_open", b.logistics), ("info_open", b.info), ("mail_open", b.important)):
                if items:
                    mail.append(v.say(key, items=join_list(self.capped([self.mail_text(m) for m in items]))))
            if b.receipts:
                sources = join_list(sorted({render.sender_name(m) for m in b.receipts})[:4])
                mail.append(v.say("receipts_line" if len(b.receipts) > 1 else "receipt_one", n=len(b.receipts), sources=sources))
        if mail:
            out.append((v.maybe("transition_mail", 0.6) + " " + " ".join(mail)).strip())

        if self.compact:
            if extras:
                out.append(v.say("also_line", items=join_list(extras)))
            out.append(v.say("see_email"))
        out.append(v.say("closing_morning" if slot < 12 else "closing_noon"))
        return out
