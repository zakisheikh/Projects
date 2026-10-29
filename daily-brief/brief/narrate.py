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
    school: list = field(default_factory=list)
    invites: list = field(default_factory=list)
    people: list = field(default_factory=list)
    other: list = field(default_factory=list)
    early: list = field(default_factory=list)       # tomorrow's first event if it starts before 8am (last brief only)
    any_homework: bool = False


@dataclass
class Item:
    """One list entry. `text` is the plain-text bullet; the other fields let the HTML email style it richly."""
    text: str
    kind: str = ""          # event | hw | exam | notice | bill | mail | alert | action | account | paid
    title: str = ""
    label: str = ""         # time ("5:00pm") or date ("Fri 10/30")
    day: object = None      # a date, for tiles
    course: str = ""
    hint: str = ""
    amount: str = ""
    due: str = ""
    who: str = ""
    link: str = ""
    detail: str = ""        # a second line of context (description snippet, statement balance, email preview)
    flags: list = field(default_factory=list)   # e.g. ["autopay off", "partner:Narjis", "overlap", "urgent"]


@dataclass
class Block:
    key: str
    lead: str = ""
    items: list = field(default_factory=list)
    text: str = ""                              # a plain sentence instead of / in addition to the list
    notes: list = field(default_factory=list)   # extra sentences under the list (overlap warnings, quips)
    in_priority: bool = False                   # followup: already shown inside the priority list


def preview(snippet, subject, limit=140):
    """The email's opening words, minus the subject if it simply repeats it."""
    text = re.sub(r"\s+", " ", (snippet or "").replace("\u034f", "").replace("\u200c", "")).strip(" \u00a0")
    if text.lower().startswith(subject.lower()[:30]):
        text = text[len(subject):].strip(" :-–")
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def to_paragraphs(blocks):
    """Spoken/plain-text rendering (Telegram and the email's text part)."""
    out = []
    for blk in blocks:
        if blk.key == "followup":
            if not blk.in_priority and blk.text:
                out.append(blk.text)
            continue
        if blk.key == "greeting":
            out.append(blk.text)
            continue
        if blk.items:
            para = bullets(blk.lead, [i.text for i in blk.items])
            if blk.notes:
                para += "\n" + "\n".join(blk.notes)
            out.append(para)
        elif blk.text:
            out.append(blk.text + ("\n" + "\n".join(blk.notes) if blk.notes else ""))
    return out


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

    def span_note(self, e):
        if not e.all_day or (e.end.date() - e.start.date()).days <= 1:
            return ""
        return " (starts today)" if e.start.date() == self.today else " (ends today)"

    def event_text(self, e):
        stamp = "all day" if e.all_day else e.start.strftime("%-I:%M%p").lower()
        mine = f" ({self.partner_label})" if self.is_partner(e) else ""
        return f"{stamp} · {e.title.strip()}{self.span_note(e)}{mine}"

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
        return to_paragraphs(self.compose(b, slot, now))

    def compose(self, b, slot, now):
        v, blocks = self.v, []
        greeting = v.say("greet_morning" if slot < 12 else "greet_noon")
        aside = v.maybe(f"dow_{now.weekday()}", 0.5)
        blocks.append(Block("greeting", text=greeting + (" " + aside if aside else ""), notes=[greeting]))   # notes[0]: greeting alone

        # bills (one entry per biller); the sentence is what Telegram says
        bills = self.followups(b)
        follow = self.followup_sentence(b)
        bill_items = []
        for m in list(b.dues_urgent) + list(b.dues_later) + list(b.bills):
            who = m.biller or render.sender_name(m)
            if any(i.who == who for i in bill_items):
                continue
            flags = (["autopay off"] if m.note == "autopay OFF" else []) + (["urgent"] if m in b.dues_urgent else [])
            bill_items.append(Item(text=who, kind="bill", who=who, amount=m.amount or "", day=m.due, link=m.link,
                                   detail=(f"Statement balance {m.balance}" if m.balance and m.balance != m.amount else ""),
                                   due=(("overdue since " if m.due and m.due < self.today else "due ") + when(m.due, self.today)) if m.due else "",
                                   flags=flags))

        # urgent: things with a deadline soon, alerts, broken accounts
        urgent = [Item(f"Account problem, {f.split(':')[0]}: {f.split(':', 1)[-1].strip()[:80]}", "account", who=f.split(':')[0]) for f in b.failures]
        urgent += [Item(render.hw_line(e, self.aliases), "notice", link=e.link, detail=e.about, title=re.sub(r"\s*\((classic|new)\)\s*$", "", e.title.strip(), flags=re.I), label=e.start.strftime("%a %-m/%-d"), day=e.start.date(),
                        course=render.course_name(e.course, self.aliases) if e.course else "", hint=e.hint, flags=["urgent"]) for e in b.notice_urgent]
        if follow and b.dues_urgent:
            urgent.append(Item(follow, "followup"))
        urgent += [Item(f"Action needed, {self.action_line(m)}", "action", title=m.subject, who=m.biller or render.sender_name(m),
                        due=m.due.strftime("%a %-m/%-d") if m.due else "", link=m.link) for m in b.action_urgent]
        urgent += [Item(f"Alert, {self.mail_line(m)}", "alert", title=m.subject, who=m.biller or render.sender_name(m), link=m.link) for m in b.alerts]
        if urgent:
            shown = urgent[: self.caps["priority"]]
            if len(urgent) > len(shown):
                shown.append(Item(v.say("more_priority", k=len(urgent) - len(shown)), "more"))
            blocks.append(Block("priority", v.say("priority_open"), shown))
        else:
            blocks.append(Block("allclear", text=v.say("all_clear")))

        # the schedule window this brief is responsible for
        if b.today:
            items = [Item(self.event_text(e), "event", title=e.title.strip() + self.span_note(e), link=e.link,
                          label="All day" if e.all_day else e.start.strftime("%-I:%M %p"), detail="" if e.all_day else "until " + e.end.strftime("%-I:%M %p"),
                          flags=([f"partner:{self.partner_label}"] if self.is_partner(e) else []) +
                                (["overlap"] if any(e in pair for pair in b.overlaps) else []))
                     for e in b.today[: self.caps["events"]]]
            if len(b.today) > self.caps["events"]:
                items.append(Item(v.say("more_items", k=len(b.today) - self.caps["events"]), "more"))
            notes = [v.say("overlap_warning", a=x.title.strip(), b=y.title.strip(), t=y.start.strftime("%-I:%M %p").replace(":00 ", " ")) for x, y in b.overlaps]
            if len(b.today) >= 5 and not self.compact:
                notes.append(v.say("quip_busy"))
            blocks.append(Block("schedule", v.say("schedule_morning_open" if slot < 12 else "schedule_open"), items, notes=notes))
        else:
            blocks.append(Block("schedule_empty", text=v.say("schedule_morning_empty" if slot < 12 else "schedule_empty")))

        for ev in b.early:
            blocks.append(Block("early", text=v.say("early_start", title=ev.title.strip(), t=ev.start.strftime("%-I:%M %p").lstrip("0"))))

        # coursework for the week, dated, soonest first (the same in both briefs)
        def hw_item(e, kind):
            return Item(render.hw_line(e, self.aliases), kind, title=re.sub(r"\s*\((classic|new)\)\s*$", "", e.title.strip(), flags=re.I),
                        label=e.start.strftime("%a %-m/%-d"), day=e.start.date(),
                        course=render.course_name(e.course, self.aliases) if e.course else "", hint=e.hint, link=e.link, detail=e.about)
        if b.hw_week:
            items = [hw_item(e, "hw") for e in sorted(b.hw_week, key=lambda e: e.start)]
            blocks.append(Block("homework", v.say("homework_week"), self.capped_items(items, "week")))
        elif not b.any_homework:
            blocks.append(Block("homework_none", text=v.say("homework_none")))
        if b.exams:
            items = [hw_item(e, "exam") for e in sorted(b.exams, key=lambda e: e.start)]
            blocks.append(Block("exams", v.say("exams_open"), self.capped_items(items, "week")))
        if b.notices_later:
            items = [hw_item(e, "notice") for e in sorted(b.notices_later, key=lambda e: e.start)]
            blocks.append(Block("notices", v.say("notices_open"), self.capped_items(items, "week")))

        blocks.append(Block("followup", text=follow, items=bill_items, in_priority=bool(follow and b.dues_urgent)))

        if self.compact:
            blocks.append(Block("see_email", text=v.say("see_email")))
        else:
            def mail_items(ms, kind="mail"):
                return [Item(self.mail_line(m), kind, title=m.subject, who=m.biller or render.sender_name(m), link=m.link,
                             detail=preview(m.snippet, m.subject)) for m in ms]
            for key, bank, items in (
                    ("paid", "paid_open", [Item(f"{m.biller or render.sender_name(m)}{' · ' + m.amount if m.amount else ''}", "paid",
                                                who=m.biller or render.sender_name(m), amount=m.amount or "", link=m.link) for m in b.paid]),
                    ("people", "people_open", mail_items(b.people)),
                    ("school", "school_open", mail_items(b.school)),
                    ("invites", "invites_open", [Item(self.mail_line(m), "mail", title=m.subject, who=m.biller or render.sender_name(m), link=m.link,
                                                      flags=["unknown sender"] if "unknown sender" in m.subject.lower() else []) for m in b.invites]),
                    ("health", "health_open", mail_items(b.health)),
                    ("admin", "admin_open", mail_items(b.admin)),
                    ("travel", "logistics_open", mail_items(b.travel)),
                    ("renewals", "renewals_open", mail_items(b.renewals)),
                    ("action", "action_open", [Item(self.action_line(m), "action", title=m.subject, who=m.biller or render.sender_name(m),
                                                    due=m.due.strftime("%a %-m/%-d") if m.due else "", link=m.link) for m in b.action]),
                    ("other", "mail_open", mail_items(b.other))):
                if items:
                    blocks.append(Block(key, v.say(bank), self.capped_items(items)))
        blocks.append(Block("closing", text=v.say("closing_morning" if slot < 12 else "closing_noon")))
        return blocks

    def is_partner(self, e):
        return bool(self.partner_label and e.creator in self.partner_emails and self.partner_label.lower() not in e.title.lower())

    def capped_items(self, items, key="list"):
        n = self.caps[key]
        if len(items) <= n:
            return items
        return items[:n] + [Item(self.v.say("more_items", k=len(items) - n), "more")]
