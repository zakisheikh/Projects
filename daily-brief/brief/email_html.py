"""The HTML email as an editorial letter: paper, ink and one accent. Typography and space do the work; there are
no boxes, cards or badges. Its one signature is the day line, a hairline that fills in where your time is taken.
Tables and inline styles so every client renders it; a <style> block adds dark mode and phone sizing.
No images, web fonts or scripts."""
from datetime import timedelta
from html import escape

SANS = "'Helvetica Neue',Helvetica,-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif"
SERIF = "'Iowan Old Style','New York','Palatino Linotype',Palatino,Georgia,serif"

PAPER, INK, SOFT, HAIR, ACCENT, ACCENT_TINT = "#faf8f5", "#141414", "#8c8a86", "#e6e2dc", "#ff4f1f", "#ffd9cc"

CSS = """
<style>
  :root { color-scheme: light dark; supported-color-schemes: light dark; }
  body, table, td, p, a { -webkit-text-size-adjust:100%; -ms-text-size-adjust:100%; }
  a { color:inherit; text-decoration:none; }
  @media (max-width: 640px) {
    .wrap { width:100% !important; } .pad { padding-left:22px !important; padding-right:22px !important; }
    .hello { font-size:44px !important; line-height:46px !important; } .voice { font-size:19px !important; line-height:28px !important; }
    .lead { font-size:21px !important; line-height:28px !important; } .col { width:62px !important; }
  }
  @media (prefers-color-scheme: dark) {
    .page { background:#121212 !important; } .ink { color:#f2efe9 !important; } .soft { color:#8f8b85 !important; }
    .hair { border-color:#2a2826 !important; } .tint { background:#5a2414 !important; } .bar { background:#2a2826 !important; }
  }
</style>
"""


def e(x):
    return escape(str(x), quote=True)


def space(h):
    return f'<tr><td style="height:{h}px;line-height:{h}px;font-size:0">&nbsp;</td></tr>'


def t(s, size=17, weight=400, cls="ink", color=INK, family=SANS, extra=""):
    return (f'<div class="{cls}" style="font-family:{family};font-size:{size}px;line-height:{round(size * 1.42)}px;'
            f'font-weight:{weight};color:{color};{extra}">{s}</div>')


def small(s, cls="soft", color=SOFT, extra=""):
    return t(s, 14, 400, cls, color, extra=f"margin-top:3px;{extra}") if s else ""


def caps(s, color=SOFT, cls="soft"):
    return f'<span class="{cls}" style="font:500 11px/14px {SANS};letter-spacing:.16em;text-transform:uppercase;color:{color}">{e(s)}</span>'


def entry(left, body, right="", link="", last=False):
    """One line of the letter: a narrow margin note on the left, the text, and on the right a figure or a quiet arrow."""
    rule = "" if last else f"border-bottom:1px solid {HAIR};"
    if not right and link:
        right = f'<span class="soft" style="color:{SOFT};font:300 18px/26px {SANS}">&rarr;</span>'
    tail = f'<td valign="top" align="right" style="padding-left:16px;white-space:nowrap">{right}</td>' if right else ""
    inner = (f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr>'
             f'<td width="78" valign="top" class="col" style="width:78px;padding-top:3px">{left}</td>'
             f'<td valign="top">{body}</td>{tail}</tr></table>')
    if link:
        inner = f'<a href="{e(link)}" style="display:block;color:inherit">{inner}</a>'
    return f'<tr><td class="hair" style="padding:16px 0;{rule}">{inner}</td></tr>'


def day_mark(item, today):
    d = item.day
    if not d:
        return ""
    soon = (d - today).days <= 1
    color, cls = (ACCENT, "") if soon else (SOFT, "soft")
    return (f'<div class="{cls}" style="font:500 11px/14px {SANS};letter-spacing:.16em;text-transform:uppercase;color:{color}">{e(d.strftime("%a"))}</div>'
            f'<div class="ink" style="font:300 26px/30px {SANS};color:{INK};letter-spacing:-.02em">{d.day}</div>')


def item_entry(item, today, last):
    k = item.kind
    title = t(e(item.title or item.text), 18, 400, extra="letter-spacing:-.01em")
    if k in ("hw", "exam", "notice"):
        bits = [x for x in (("Exam" if k == "exam" else ""), item.course) if x]
        hint = f'<span style="color:{ACCENT}">{e(item.hint)}</span>' if item.hint else ""
        info = " · ".join(x for x in (e(" · ".join(bits)), hint) if x)
        return entry(day_mark(item, today), title + small(info) + small(e(item.detail)), link=item.link, last=last)
    if k == "event":
        partner = next((f.split(":", 1)[1] for f in item.flags if f.startswith("partner:")), "")
        info = " · ".join(e(x) for x in (item.detail, partner) if x)
        warn = small("Overlaps another event", "", ACCENT) if "overlap" in item.flags else ""
        left = f'<div class="soft" style="font:400 14px/22px {SANS};color:{SOFT};white-space:nowrap">{e(item.label)}</div>'
        return entry(left, title + small(info) + warn, link=item.link, last=last)
    if k == "bill":
        soon = "urgent" in item.flags
        due = f'<span style="color:{ACCENT}">{e(item.due[:1].upper() + item.due[1:])}</span>' if (item.due and soon) else e(item.due[:1].upper() + item.due[1:]) if item.due else ""
        info = " · ".join(x for x in (due, e(item.detail), "Autopay is off" if "autopay off" in item.flags else "") if x)
        right = t(e(item.amount), 18, 400, extra="font-variant-numeric:tabular-nums;letter-spacing:-.01em") if item.amount else ""
        return entry("", t(e(item.who), 18, 400) + small(info), right, item.link, last)
    if k in ("alert", "action", "account"):
        word = {"alert": "Alert", "action": "Action needed", "account": "Account problem"}[k]
        by = f" · by {e(item.due)}" if item.due else ""
        return entry(caps(word, ACCENT, ""), title + small(e(item.who) + by), link=item.link, last=last)
    if k == "paid":
        right = t(e(item.amount), 18, 400, extra="font-variant-numeric:tabular-nums") if item.amount else ""
        return entry(caps("Paid"), t(e(item.who), 18, 400), right, item.link, last)
    if k == "more":
        return entry("", t(e(item.text), 16, 400, "soft", SOFT, SERIF, "font-style:italic"), last=last)
    caution = f' · <span style="color:{ACCENT}">Unknown sender</span>' if "unknown sender" in item.flags else ""
    return entry("", title + small(e(item.detail)) + small(e(item.who) + caution), link=item.link, last=last)


def day_line(items):
    """The signature: one hairline from the first hour to the last, filled where events are. Fluid: widths are percentages."""
    timed = [i for i in items if i.start and i.end]
    if not timed:
        return ""
    start = min(i.start for i in timed).replace(minute=0, second=0, microsecond=0)
    end = max(i.end for i in timed)
    end = (end + timedelta(minutes=59)).replace(minute=0, second=0, microsecond=0)
    if (end - start).total_seconds() < 4 * 3600:
        end = start + timedelta(hours=4)
    slots = int((end - start).total_seconds() // 900)               # quarter hours
    cells = []
    for n in range(slots):
        a = start + timedelta(minutes=15 * n)
        busy = sum(1 for i in timed if i.start < a + timedelta(minutes=15) and i.end > a)
        bg, cls = (ACCENT, "") if busy > 1 else (ACCENT_TINT, "tint") if busy else (HAIR, "bar")
        cells.append(f'<td class="{cls}" style="height:6px;line-height:6px;font-size:0;background:{bg}">&nbsp;</td>')
    fmt = lambda d: d.strftime("%-I %p").lower().replace(" ", "")
    return (f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="table-layout:fixed;border-radius:3px;overflow:hidden">'
            f'<tr>{"".join(cells)}</tr></table>'
            f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:6px"><tr>'
            f'<td>{caps(fmt(start))}</td><td align="right">{caps(fmt(end))}</td></tr></table>')


def line_block(line):
    return f'<div style="margin:18px 0 6px">{line}</div>' if line else ""


def chapter(lead, items, today, notes=(), line=""):
    items = [i for i in items if i.kind != "followup"]
    if not items and not notes:
        return ""
    rows = "".join(item_entry(i, today, n == len(items) - 1 and not notes) for n, i in enumerate(items))
    rows += "".join(f'<tr><td style="padding:14px 0 0">{t(e(x), 16, 400, "", ACCENT, SERIF, "font-style:italic")}</td></tr>' for x in notes)
    return (f'<tr><td class="pad" style="padding:0 40px">'
            f'{t(e(lead.rstrip(":")), 24, 400, family=SERIF, cls="ink lead", extra="letter-spacing:-.01em;margin:0 0 6px")}'
            f'{line_block(line)}'
            f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">{rows}</table></td></tr>{space(52)}')


def scoreboard(blk, game_rep):
    """The to-do game: three figures, the week as a filling line, and Bruno's remarks."""
    from .game import level_name
    g = game_rep

    def fig(value, label, hot=False):
        return (f'<td valign="top" style="padding-right:30px"><div class="{"" if hot else "ink"}" style="font:200 34px/36px {SANS};'
                f'color:{ACCENT if hot else INK};letter-spacing:-.03em;white-space:nowrap">{e(value)}</div><div style="margin-top:6px">{caps(label)}</div></td>')
    figures = (f'<table role="presentation" cellspacing="0" cellpadding="0" border="0"><tr>{fig(level_name(g.level), "Level")}'
               f'{fig(g.xp, "XP")}{fig(g.streak, "Day streak", g.streak_event == "record")}</tr></table>'
               f'<div style="margin-top:14px">{small(e(f"{g.to_next} XP to {level_name(g.level + 1)}"))}</div>')
    week = ""
    if g.week_total:
        cells = "".join(f'<td class="{"" if n < g.week_done else "bar"}" style="height:6px;line-height:6px;font-size:0;'
                        f'background:{ACCENT if n < g.week_done else HAIR}">&nbsp;</td>' for n in range(g.week_total))
        week = (f'<div style="margin-top:26px"><table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" '
                f'style="table-layout:fixed;border-collapse:separate;border-spacing:3px 0"><tr>{cells}</tr></table>'
                f'<div style="margin-top:8px">{caps(f"This week · {g.week_done} of {g.week_total} done")}</div></div>')
    notes = "".join(f'<div style="margin-top:18px">{t(e(n), 18, 400, "ink", INK, SERIF, "font-style:italic")}</div>' for n in blk.notes)
    hint = small("Tap Done under the Telegram brief to score an item.", extra="margin-top:18px")
    return (f'<tr><td class="pad" style="padding:0 40px">'
            f'{t(e(blk.lead.rstrip(":")), 24, 400, family=SERIF, cls="ink lead", extra="letter-spacing:-.01em;margin:0 0 20px")}'
            f'{figures}{week}{notes}{hint}</td></tr>{space(52)}')


def remark(text):
    return (f'<tr><td class="pad" style="padding:0 40px">{t(e(text), 21, 400, "soft voice", SOFT, SERIF, "font-style:italic")}</td></tr>{space(52)}')


def render(blocks, header, now, footer, preheader="", links=(), game_rep=None):
    today = now.date()
    by = {b.key: b for b in blocks}
    urgent_n = len([i for i in by["priority"].items if i.kind not in ("followup", "more")]) if "priority" in by else 0
    bills_n = len(by["followup"].items) if "followup" in by else 0
    work_n = sum(len([i for i in by[k].items if i.kind != "more"]) for k in ("homework", "exams") if k in by)
    greeting = by["greeting"].notes[0] if by["greeting"].notes else by["greeting"].text
    closing = by["closing"].text if "closing" in by else ""
    hello = "Good morning." if header.startswith("Morning") else "Good afternoon."

    def figure(n, label, hot=False):
        color = ACCENT if (hot and n) else INK
        return (f'<td valign="bottom" style="padding-right:28px"><div class="{"" if hot and n else "ink"}" style="font:200 40px/40px {SANS};color:{color};letter-spacing:-.03em">{n}</div>'
                f'<div style="margin-top:6px">{caps(label)}</div></td>')
    glance = (f'<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin-top:30px"><tr>'
              f'{figure(urgent_n, "Urgent", True)}{figure(work_n, "This week")}{figure(bills_n, "Bills")}</tr></table>')
    nav = "".join(f'<a href="{e(url)}" class="ink" style="color:{INK};font:400 14px/20px {SANS};margin-left:18px;border-bottom:1px solid {INK}">{e(label)}</a>' for label, url in links)

    body = []
    for key in ("priority", "allclear", "game", "schedule", "schedule_empty", "early", "homework", "homework_none", "exams", "notices", "followup",
                "paid", "people", "school", "invites", "health", "admin", "travel", "renewals", "action", "other"):
        blk = by.get(key)
        if not blk:
            continue
        if key == "followup":
            if blk.items:
                body.append(chapter("Follow up with", blk.items, today))
        elif key in ("allclear", "schedule_empty", "homework_none", "early"):
            body.append(remark(blk.text))
        elif key == "game":
            if game_rep:
                body.append(scoreboard(blk, game_rep))
        elif key == "schedule":
            body.append(chapter(blk.lead, blk.items, today, blk.notes, day_line(blk.items)))
        else:
            body.append(chapter(blk.lead, blk.items, today, blk.notes))

    pre = escape(preheader or greeting)[:140]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark"><meta name="supported-color-schemes" content="light dark">
<meta name="x-apple-disable-message-reformatting"><meta name="format-detection" content="telephone=no,date=no,address=no,email=no">
<title>{e(header)}</title>{CSS}</head>
<body class="page" style="margin:0;padding:0;background:{PAPER}">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent">{pre}&#8199;&#847;&#8199;&#847;&#8199;&#847;&#8199;&#847;</div>
<table role="presentation" class="page" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:{PAPER}"><tr><td align="center" style="padding:40px 0 56px">
<table role="presentation" class="wrap" width="640" cellspacing="0" cellpadding="0" border="0" style="width:100%;max-width:640px">

<tr><td class="pad" style="padding:0 40px">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" class="hair" style="border-bottom:1px solid {INK}"><tr>
    <td style="padding-bottom:12px">{caps("Bruno", INK, "ink")}</td>
    <td align="right" style="padding-bottom:12px">{caps(now.strftime("%A, %B ") + str(now.day))}</td></tr></table>
  <div class="ink hello" style="font:300 60px/60px {SANS};color:{INK};letter-spacing:-.045em;margin:44px 0 18px">{hello}</div>
  <div class="soft voice" style="font:italic 400 22px/32px {SERIF};color:{SOFT}">{e(greeting)}</div>
  {glance}
  <div style="margin-top:28px;margin-left:-18px">{nav}</div>
</td></tr>
{space(64)}

{"".join(body)}

<tr><td class="pad" style="padding:0 40px">
  <div class="hair" style="border-top:1px solid {HAIR};padding-top:28px">{t(e(closing), 21, 400, "ink", INK, SERIF, "font-style:italic")}</div>
  <div style="margin-top:22px">{caps("— Bruno")}</div>
  <div class="soft" style="font:400 12px/18px {SANS};color:{SOFT};margin-top:18px">{e(footer)}</div>
</td></tr>
</table></td></tr></table></body></html>"""
