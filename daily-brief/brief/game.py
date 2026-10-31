"""Gamified to-dos: coursework and bills earn XP when you tap Done in Telegram (or, for bills, when the
'payment received' email arrives). Levels, a streak of days with nothing overdue, and a weekly score.
Everything lives in state.json between briefs; nothing here needs a server."""
import hashlib
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

ROMAN = [(10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
PROJECT = re.compile(r"(?i)\b(project|proposal|report|presentation|paper)\b")


def roman(n):
    out = ""
    for v, s in ROMAN:
        while n >= v:
            out, n = out + s, n - v
    return out


def level_for(xp):
    """Level n starts at 100(n-1) + 25(n-1)(n-2) XP: 0, 100, 250, 450, 700, 1000..."""
    n = 1
    while xp >= 100 * n + 25 * n * (n - 1):
        n += 1
    return n


def next_level_at(n):
    return 100 * n + 25 * n * (n - 1)


def level_name(n):
    return f"Mark {roman(n)}"


def todo_id(*parts):
    return hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()[:10]


def event_id(e):
    return todo_id("cw", e.title.strip().lower(), e.start.date().isoformat())


def bill_id(account, who, due):
    return todo_id("bill", account, who.lower(), due.isoformat() if due else "")


def xp_for(todo, done_on):
    due = date.fromisoformat(todo["due"]) if todo.get("due") else done_on
    if todo["kind"] == "bill":
        return 15 + (5 if done_on <= due else 0)
    base = 40 if todo["kind"] == "exam" else 30 if PROJECT.search(todo["title"]) else 20
    early = (due - done_on).days
    if early < 0:
        return base // 2
    return base + (20 if early >= 3 else 10 if early >= 1 else 0)


@dataclass
class Report:
    xp: int = 0
    level: int = 1
    leveled_up: bool = False
    to_next: int = 100
    streak: int = 0
    best: int = 0
    streak_event: str = ""            # "record" | "broken" | ""
    broke_on: str = ""                # title of what broke the streak
    done_now: list = field(default_factory=list)   # [(title, xp)]
    week_done: int = 0
    week_total: int = 0
    recap: bool = False
    week_xp: int = 0
    open_ids: set = field(default_factory=set)
    done_ids: set = field(default_factory=set)


def taps(updates, chat_id):
    """Done buttons pressed since the last brief: callback data 'done:<id>' from your chat only."""
    out = []
    for u in updates:
        cq = u.get("callback_query") or {}
        chat = ((cq.get("message") or {}).get("chat") or {}).get("id")
        m = re.fullmatch(r"done:([0-9a-f]{10})", cq.get("data", ""))
        if m and str(chat) == str(chat_id):
            out.append(m.group(1))
    return out


def play(game, todos, tapped, paid_billers, now, slot_is_first):
    """game: the persisted dict (mutated). todos: [{id, kind, title, due, who?, account?}] seen in this brief.
    tapped: ids pressed Done. paid_billers: {(account, who)} with a payment-received email this brief."""
    today = now.date()
    book = game.setdefault("todos", {})
    for t in todos:
        if t["id"] not in book:
            book[t["id"]] = {**t, "added": today.isoformat(), "done": None, "xp": 0}
    rep = Report()
    before = level_for(game.get("xp", 0))

    def complete(tid, how):
        t = book.get(tid)
        if not t or t["done"]:
            return
        gained = xp_for(t, today) if how != "cleared" else 0
        t.update(done=today.isoformat(), xp=gained, how=how)
        game["xp"] = game.get("xp", 0) + gained
        if gained:
            rep.done_now.append((t["title"], gained))

    for tid in tapped:
        complete(tid, "tapped")
    for tid, t in list(book.items()):
        if t["kind"] == "bill" and not t["done"] and (t.get("account"), t.get("who")) in paid_billers:
            complete(tid, "paid")

    # streak: judged once a day, at the first brief, on what was due before today
    if slot_is_first and game.get("streak_day") != today.isoformat():
        overdue = [t for t in book.values() if not t["done"] and t.get("due") and date.fromisoformat(t["due"]) < today]
        if overdue:
            if game.get("streak", 0) > 0:
                rep.streak_event, rep.broke_on = "broken", overdue[0]["title"]
            game["streak"] = 0
        else:
            game["streak"] = game.get("streak", 0) + 1
            if game["streak"] > game.get("best", 0):
                game["best"] = game["streak"]
                if game["streak"] > 1:
                    rep.streak_event = "record"
        game["streak_day"] = today.isoformat()

    # the week runs Monday to Sunday, by due date
    monday = today - timedelta(days=today.weekday())
    week = [t for t in book.values() if t.get("due") and monday <= date.fromisoformat(t["due"]) <= monday + timedelta(days=6)]
    rep.week_total, rep.week_done = len(week), sum(1 for t in week if t["done"])
    rep.week_xp = sum(t["xp"] for t in book.values() if t["done"] and monday <= date.fromisoformat(t["done"]) <= today)
    rep.recap = slot_is_first and today.weekday() == 6

    # forget finished items after a month so the state stays small
    cutoff = (today - timedelta(days=30)).isoformat()
    for tid in [k for k, t in book.items() if (t["done"] or t.get("due") or t["added"]) < cutoff]:
        del book[tid]

    rep.xp = game.get("xp", 0)
    rep.level = level_for(rep.xp)
    rep.leveled_up = rep.level > before
    rep.to_next = next_level_at(rep.level) - rep.xp
    rep.streak, rep.best = game.get("streak", 0), game.get("best", 0)
    rep.done_ids = {k for k, t in book.items() if t["done"]}
    rep.open_ids = {k for k, t in book.items() if not t["done"]}
    return rep


def bar(done, total, width=8):
    if not total:
        return ""
    filled = round(width * done / total)
    return "▰" * filled + "▱" * (width - filled)
