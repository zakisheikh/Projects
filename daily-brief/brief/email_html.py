"""The designed HTML email. Table layout + inline styles for every client, a <style> block for dark mode.
No images, no web fonts, no JavaScript: it renders the same in Gmail, Apple Mail and Outlook."""
from datetime import timedelta
from html import escape

FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif"
MONO = "SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"

# light palette (dark overrides live in CSS below)
INK, MUTED, HAIR, CARD, PAGE = "#1b1f2a", "#667085", "#e8e4da", "#ffffff", "#f3f0ea"
NAVY, CYAN, RED, AMBER, GREEN, SLATE, VIOLET = "#0b1d3a", "#38bdf8", "#e5484d", "#f59e0b", "#12a77d", "#64748b", "#7c5cff"

# each section: (eyebrow label, accent colour)
SECTIONS = {
    "priority": ("Priority", RED), "schedule": ("Schedule", CYAN), "homework": ("Coursework", VIOLET), "exams": ("Exams & presentations", RED),
    "notices": ("Class notices", SLATE), "followup": ("Bills", AMBER), "paid": ("Paid", GREEN), "health": ("Health", GREEN),
    "admin": ("Life admin", SLATE), "travel": ("Travel", CYAN), "renewals": ("Subscriptions", SLATE), "action": ("Action requested", AMBER),
    "other": ("Worth opening", SLATE),
}

CSS = f"""
<style>
  :root {{ color-scheme: light dark; supported-color-schemes: light dark; }}
  body, table, td, p, a, li {{ -webkit-text-size-adjust:100%; -ms-text-size-adjust:100%; }}
  a {{ color: inherit; }}
  @media (max-width: 640px) {{
    .wrap {{ width:100% !important; }} .pad {{ padding-left:18px !important; padding-right:18px !important; }}
    .hero-title {{ font-size:26px !important; }} .stack {{ display:block !important; width:100% !important; }}
  }}
  @media (prefers-color-scheme: dark) {{
    .page {{ background:#0a0e16 !important; }} .card {{ background:#121826 !important; border-color:#222c3f !important; }}
    .ink {{ color:#eef1f6 !important; }} .muted {{ color:#9aa6b8 !important; }} .hair {{ border-color:#222c3f !important; }}
    .tile {{ background:#1a2336 !important; }} .rowalt {{ background:#161e30 !important; }} .warnbg {{ background:#33270d !important; }}
    .chip-slate {{ background:#1f2a40 !important; color:#c6d0e0 !important; }}
  }}
</style>
"""


def e(x):
    return escape(str(x), quote=True)


def chip(text, bg, fg="#ffffff", cls=""):
    return (f'<span class="{cls}" style="display:inline-block;padding:2px 9px;margin:0 6px 0 0;border-radius:999px;background:{bg};color:{fg};'
            f'font:600 11px/18px {FONT};letter-spacing:.04em;text-transform:uppercase;white-space:nowrap">{e(text)}</span>')


def soft_chip(text, color):
    return chip(text, "#eef1f6", color, "chip-slate")


def tile(item, today):
    """Calendar-style date tile: weekday over day number. Red when due soon."""
    d = item.day
    if not d:
        return ""
    days = (d - today).days
    bg, fg = (RED, "#fff") if days <= 1 else (AMBER, "#1b1f2a") if days <= 3 else ("#eef1f6", INK)
    cls = "" if days <= 3 else "tile"
    return (f'<table role="presentation" cellspacing="0" cellpadding="0" border="0" align="left" style="margin:0 14px 0 0"><tr>'
            f'<td class="{cls}" align="center" width="52" style="width:52px;background:{bg};border-radius:10px;padding:6px 0;color:{fg};font-family:{FONT}">'
            f'<div style="font:700 10px/12px {FONT};letter-spacing:.08em;text-transform:uppercase;opacity:.85">{e(d.strftime("%a"))}</div>'
            f'<div style="font:800 20px/22px {FONT}">{d.day}</div></td></tr></table>')


def row(inner, alt=False, last=False):
    border = "" if last else f"border-bottom:1px solid {HAIR};"
    return (f'<tr><td class="hair{" rowalt" if alt else ""}" style="padding:12px 0;{border}font-family:{FONT};font-size:15px;line-height:22px;color:{INK}">'
            f'{inner}</td></tr>')


def link(text, href, bold=False):
    if not href:
        return e(text)
    return f'<a href="{e(href)}" style="color:inherit;text-decoration:none;border-bottom:1px dotted {SLATE}">{e(text)}</a>'


def item_html(item, today):
    k = item.kind
    if k in ("hw", "exam", "notice"):
        tag = ""
        if k == "exam":
            tag += chip("Exam", RED)
        if item.course:
            tag += soft_chip(item.course, VIOLET)
        hint = f'<div class="muted" style="color:{RED};font-weight:600;font-size:13px">{e(item.hint)}</div>' if item.hint else ""
        return (tile(item, today) + f'<div class="ink" style="font-weight:600;overflow:hidden">{e(item.title)}</div>'
                f'<div style="margin-top:3px">{tag}</div>{hint}<div style="clear:both"></div>')
    if k == "event":
        partner = next((f.split(":", 1)[1] for f in item.flags if f.startswith("partner:")), "")
        extra = (chip(partner, VIOLET) if partner else "") + (chip("Overlap", AMBER, INK) if "overlap" in item.flags else "")
        return (f'<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%"><tr>'
                f'<td width="84" valign="top" style="width:84px;font:700 14px/22px {MONO};color:{CYAN}">{e(item.label)}</td>'
                f'<td valign="top" class="ink" style="font-family:{FONT};font-size:15px;line-height:22px;color:{INK}">{e(item.title)}'
                f'{" " + extra if extra else ""}</td></tr></table>')
    if k == "bill":
        urgent = "urgent" in item.flags
        right = f'<span class="ink" style="font:800 18px/22px {FONT};color:{INK}">{e(item.amount)}</span>' if item.amount else ""
        tags = (chip(item.due, RED if urgent else SLATE) if item.due else "") + (chip("Autopay off", AMBER, INK) if "autopay off" in item.flags else "")
        return (f'<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%"><tr>'
                f'<td valign="top" class="ink" style="font-family:{FONT};font-size:16px;line-height:24px;font-weight:700;color:{INK}">{e(item.who)}<div style="margin-top:3px">{tags}</div></td>'
                f'<td valign="top" align="right">{right}</td></tr></table>')
    if k in ("alert", "action", "account", "followup"):
        label = {"alert": ("Alert", RED, "#fff"), "action": ("Action", AMBER, INK), "account": ("Account", RED, "#fff"), "followup": ("Bills", AMBER, INK)}[k]
        due = f' <span class="muted" style="color:{MUTED}">· by {e(item.due)}</span>' if item.due else ""
        body = link(item.text, item.link) if k not in ("followup",) else e(item.text)
        return chip(*label) + f'<span class="ink">{body}</span>{due}'
    if k == "paid":
        amt = f' <span style="font-weight:800">{e(item.amount)}</span>' if item.amount else ""
        return chip("Paid", GREEN) + f'<span class="ink">{link(item.who, item.link)}</span>{amt}'
    if k == "more":
        return f'<span class="muted" style="color:{MUTED};font-style:italic">{e(item.text)}</span>'
    # generic mail / info rows: sender in small caps, subject below
    return (f'<div class="muted" style="font:700 11px/16px {FONT};letter-spacing:.06em;text-transform:uppercase;color:{MUTED}">{e(item.who)}</div>'
            f'<div class="ink" style="font-weight:500">{link(item.title or item.text, item.link)}</div>')


def section(block, today, first=False):
    label, accent = SECTIONS.get(block.key, (block.key.title(), SLATE))
    items = [i for i in block.items if not (block.key == "priority" and i.kind == "followup")]
    if not items and not block.notes:
        return ""
    body = "".join(row(item_html(i, today), last=(n == len(items) - 1)) for n, i in enumerate(items))
    notes = "".join(
        f'<tr><td class="warnbg" style="padding:10px 12px;margin-top:8px;background:#fff6e0;border-left:3px solid {AMBER};border-radius:6px;'
        f'font:500 14px/21px {FONT};color:{INK}">{e(n)}</td></tr><tr><td style="height:6px;line-height:6px;font-size:0">&nbsp;</td></tr>'
        for n in block.notes)
    return (f'<tr><td class="card pad" style="background:{CARD};border:1px solid {HAIR};border-top:4px solid {accent};border-radius:14px;padding:20px 26px 10px">'
            f'<div style="font:700 11px/14px {FONT};letter-spacing:.14em;text-transform:uppercase;color:{accent}">{e(label)}</div>'
            f'<div class="ink" style="font:600 18px/26px {FONT};color:{INK};margin:4px 0 8px">{e(block.lead)}</div>'
            f'<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">{body}</table>'
            f'<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="margin-top:6px">{notes}</table></td></tr>'
            f'<tr><td style="height:16px;line-height:16px;font-size:0">&nbsp;</td></tr>')


def sentence_card(text, accent=GREEN):
    return (f'<tr><td class="card pad" style="background:{CARD};border:1px solid {HAIR};border-left:4px solid {accent};border-radius:14px;padding:16px 26px">'
            f'<div class="ink" style="font:500 16px/24px {FONT};color:{INK}">{e(text)}</div></td></tr>'
            f'<tr><td style="height:16px;line-height:16px;font-size:0">&nbsp;</td></tr>')


def stat(n, label, color):
    return (f'<td align="center" style="padding:0 6px"><div style="font:800 26px/28px {FONT};color:{color}">{n}</div>'
            f'<div style="font:600 10px/14px {FONT};letter-spacing:.1em;text-transform:uppercase;color:#9fb2d0">{e(label)}</div></td>')


def render(blocks, header, now, footer, preheader=""):
    today = now.date()
    by = {b.key: b for b in blocks}
    urgent_n = len([i for i in by["priority"].items if i.kind not in ("followup", "more")]) if "priority" in by else 0
    bills_n = len(by["followup"].items) if "followup" in by else 0
    events_n = len([i for i in by["schedule"].items if i.kind == "event"]) if "schedule" in by else 0
    work_n = sum(len(by[k].items) for k in ("homework", "exams") if k in by)
    stats = "".join([stat(urgent_n, "Urgent", RED if urgent_n else "#7dd3a8"), stat(events_n, "Events", CYAN),
                     stat(work_n, "Due this week", "#b9a6ff"), stat(bills_n, "Bills", AMBER if bills_n else "#7dd3a8")])
    greeting = by["greeting"].text
    closing = by["closing"].text if "closing" in by else ""

    cards = []
    for key in ("priority", "allclear", "schedule", "schedule_empty", "homework", "homework_none", "exams", "notices", "followup",
                "statements", "paid", "health", "admin", "travel", "renewals", "action", "other"):
        blk = by.get(key)
        if not blk:
            continue
        if key == "followup":
            lead = "Bills to follow up on:"
            if blk.items:
                blk = type(blk)("followup", blk.text and "Follow up with these, in order of urgency:" or lead, blk.items)
                cards.append(section(blk, today))
        elif key in ("allclear", "schedule_empty", "homework_none"):
            cards.append(sentence_card(blk.text, {"allclear": GREEN, "schedule_empty": CYAN, "homework_none": VIOLET}[key]))
        elif key == "statements":
            cards.append(sentence_card(blk.text, AMBER))
        else:
            cards.append(section(blk, today))
    pre = escape(preheader or greeting)[:140]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark"><meta name="supported-color-schemes" content="light dark">
<title>{e(header)}</title>{CSS}</head>
<body class="page" style="margin:0;padding:0;background:{PAGE}">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent">{pre}&#8199;&#847;&#8199;&#847;&#8199;&#847;&#8199;&#847;</div>
<table role="presentation" class="page" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:{PAGE}"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" class="wrap" width="640" cellspacing="0" cellpadding="0" border="0" style="width:640px;max-width:640px">

<tr><td class="pad" style="background:{NAVY};background-image:linear-gradient(135deg,#0b1d3a 0%,#12325f 100%);border-radius:18px;padding:30px 32px 26px">
  <div style="font:700 11px/14px {FONT};letter-spacing:.2em;text-transform:uppercase;color:{CYAN}">Bruno &nbsp;·&nbsp; {e(header.split(" — ")[0])}</div>
  <div class="hero-title" style="font:800 32px/38px {FONT};color:#ffffff;margin:8px 0 10px">{e(now.strftime("%A, %B ") + str(now.day))}</div>
  <div style="font:400 16px/25px {FONT};color:#d6e2f5">{e(greeting)}</div>
  <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin-top:20px"><tr>{stats}</tr></table>
</td></tr>
<tr><td style="height:16px;line-height:16px;font-size:0">&nbsp;</td></tr>

{"".join(cards)}

<tr><td class="pad" align="center" style="padding:6px 26px 4px">
  <div class="ink" style="font:italic 500 16px/24px {FONT};color:{INK}">{e(closing)}</div>
  <div class="muted" style="font:400 12px/18px {FONT};color:{MUTED};margin-top:10px">{e(footer)}</div>
</td></tr>
</table></td></tr></table></body></html>"""
