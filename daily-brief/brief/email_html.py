"""The HTML email, in the Apple idiom: a calm grey canvas, soft white cards, San Francisco type with a serif voice
for Bruno, Calendar-style date marks and one accent colour. Tables + inline styles so every client renders it;
a <style> block adds dark mode, phone sizing and (in Apple Mail) a gentle fade-in. No images, fonts or scripts."""
from html import escape

SANS = "-apple-system,BlinkMacSystemFont,'SF Pro Text','Helvetica Neue',Helvetica,Arial,sans-serif"
DISPLAY = "-apple-system,BlinkMacSystemFont,'SF Pro Display','Helvetica Neue',Helvetica,Arial,sans-serif"
SERIF = "'New York','Iowan Old Style','Apple Garamond',Georgia,'Times New Roman',serif"

INK, GRAY, FAINT, HAIR, CARD, PAGE = "#1d1d1f", "#86868b", "#aeaeb2", "#ececf0", "#ffffff", "#f5f5f7"
BLUE, RED, ORANGE = "#0071e3", "#e30000", "#bf4800"
SHADOW = "0 1px 2px rgba(0,0,0,.04),0 10px 30px rgba(0,0,0,.05)"

CSS = """
<style>
  :root { color-scheme: light dark; supported-color-schemes: light dark; }
  body, table, td, p, a { -webkit-text-size-adjust:100%; -ms-text-size-adjust:100%; }
  a { color:inherit; text-decoration:none; }
  @media (prefers-reduced-motion: no-preference) {
    @keyframes rise { from { opacity:0; transform:translateY(10px); } to { opacity:1; transform:none; } }
    .fx { animation: rise .7s cubic-bezier(.2,.7,.2,1) both; }
    .d1 { animation-delay:.05s } .d2 { animation-delay:.12s } .d3 { animation-delay:.19s } .d4 { animation-delay:.26s }
    .d5 { animation-delay:.33s } .d6 { animation-delay:.40s } .d7 { animation-delay:.47s } .d8 { animation-delay:.54s }
  }
  @media (max-width: 640px) {
    .wrap { width:100% !important; } .pad { padding-left:18px !important; padding-right:18px !important; }
    .hero { font-size:36px !important; line-height:40px !important; } .voice { font-size:19px !important; line-height:28px !important; }
    .col { width:64px !important; } .num { font-size:30px !important; }
  }
  @media (prefers-color-scheme: dark) {
    .page { background:#000000 !important; } .card { background:#1c1c1e !important; box-shadow:none !important; }
    .ink { color:#f5f5f7 !important; } .gray { color:#98989d !important; } .faint { color:#636366 !important; }
    .hair { border-color:#2c2c2e !important; } .red { color:#ff453a !important; } .orange { color:#ff9f0a !important; }
    .btn { background:#1c1c1e !important; color:#2997ff !important; }
  }
</style>
"""


def e(x):
    return escape(str(x), quote=True)


def space(h):
    return f'<tr><td style="height:{h}px;line-height:{h}px;font-size:0">&nbsp;</td></tr>'


def text(t, size=17, weight=400, cls="ink", color=INK, family=SANS, extra=""):
    return f'<div class="{cls}" style="font-family:{family};font-size:{size}px;line-height:{round(size * 1.38)}px;font-weight:{weight};color:{color};letter-spacing:-.012em;{extra}">{t}</div>'


def meta(t, cls="gray", color=GRAY):
    return text(t, 14, 400, cls, color, extra="margin-top:2px;letter-spacing:-.005em") if t else ""


def row(inner, last, link="", lead_px=16):
    sep = "" if last else f"border-bottom:1px solid {HAIR};"
    chev = (f'<td width="22" valign="middle" class="faint" style="width:22px;font:300 22px/22px {SANS};color:{FAINT}">&rsaquo;</td>' if link else "")
    body = f'<a href="{e(link)}" style="display:block;color:inherit">{inner}</a>' if link else inner
    return (f'<tr><td style="padding-left:{lead_px}px"><table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" class="hair" style="{sep}"><tr>'
            f'<td style="padding:14px 6px 14px 0">{body}</td>{chev}<td width="10" style="width:10px"></td></tr></table></td></tr>')


def calendar_mark(item, today):
    """Apple Calendar's icon: the weekday in red small caps over the day number."""
    d = item.day
    soon = d and (d - today).days <= 1
    wk = f'<div class="red" style="font:600 11px/13px {SANS};letter-spacing:.06em;text-transform:uppercase;color:{RED}">{e(d.strftime("%a"))}</div>' if d else ""
    num = f'<div class="ink" style="font:{"500" if soon else "300"} 26px/30px {DISPLAY};color:{INK};letter-spacing:-.02em">{d.day}</div>' if d else ""
    return f'<td width="58" valign="top" class="col" align="left" style="width:58px;padding-top:1px">{wk}{num}</td>'


def item_row(item, today, last):
    k = item.kind
    if k in ("hw", "exam", "notice"):
        bits = [b for b in (("Exam" if k == "exam" else ""), item.course) if b]
        tail = e(" · ".join(bits))
        hint = f'<span class="red" style="color:{RED}">{e(item.hint)}</span>' if item.hint else ""
        info = " · ".join(x for x in (tail, hint) if x)
        inner = (f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr>{calendar_mark(item, today)}'
                 f'<td valign="top">{text(e(item.title), 17, 500)}{meta(info)}{meta(e(item.detail)) if item.detail else ""}</td></tr></table>')
        return row(inner, last, item.link)
    if k == "event":
        partner = next((f.split(":", 1)[1] for f in item.flags if f.startswith("partner:")), "")
        info = " · ".join(e(x) for x in (item.detail, partner) if x)
        warn = meta("Overlaps another event", "orange", ORANGE) if "overlap" in item.flags else ""
        inner = (f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr>'
                 f'<td width="86" valign="top" class="col gray" style="width:86px;font:400 15px/24px {SANS};color:{GRAY};white-space:nowrap;letter-spacing:-.01em">{e(item.label)}</td>'
                 f'<td valign="top">{text(e(item.title), 17, 500)}{meta(info)}{warn}</td></tr></table>')
        return row(inner, last, item.link)
    if k == "bill":
        due_cls, due_col = ("red", RED) if "urgent" in item.flags else ("gray", GRAY)
        parts = [f'<span class="{due_cls}" style="color:{due_col}">{e(item.due[:1].upper() + item.due[1:])}</span>' if item.due else "",
                 e(item.detail) if item.detail else "",
                 f'<span class="orange" style="color:{ORANGE}">Autopay is off</span>' if "autopay off" in item.flags else ""]
        amount = text(e(item.amount), 17, 600, extra="text-align:right;white-space:nowrap") if item.amount else ""
        inner = (f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr>'
                 f'<td valign="top">{text(e(item.who), 17, 500)}{meta(" · ".join(p for p in parts if p))}</td>'
                 f'<td valign="top" align="right" style="padding-left:12px">{amount}</td></tr></table>')
        return row(inner, last, item.link)
    if k in ("alert", "action", "account"):
        word, cls, col = {"alert": ("Alert", "red", RED), "action": ("Action needed", "orange", ORANGE), "account": ("Account problem", "red", RED)}[k]
        by = f" · by {e(item.due)}" if item.due else ""
        return row(text(e(item.title or item.text), 17, 500) + meta(f"{e(word)} · {e(item.who)}{by}", cls, col), last, item.link)
    if k == "paid":
        amount = text(e(item.amount), 17, 600, extra="text-align:right") if item.amount else ""
        inner = (f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr><td>{text(e(item.who), 17, 500)}{meta("Payment received")}</td>'
                 f'<td align="right">{amount}</td></tr></table>')
        return row(inner, last, item.link)
    if k == "more":
        return row(text(e(item.text), 15, 400, "gray", GRAY, extra="font-style:italic"), last)
    caution = f' · <span class="orange" style="color:{ORANGE}">Unknown sender</span>' if "unknown sender" in item.flags else ""
    return row(text(e(item.title or item.text), 17, 500) + (meta(e(item.detail)) if item.detail else "") + meta(e(item.who) + caution), last, item.link)


def card(title, items, today, notes=(), delay=1):
    items = [i for i in items if i.kind != "followup"]
    if not items and not notes:
        return ""
    rows = "".join(item_row(i, today, n == len(items) - 1 and not notes) for n, i in enumerate(items))
    rows += "".join(row(text(e(t), 15, 400, "orange", ORANGE), n == len(notes) - 1) for n, t in enumerate(notes))
    return (f'<tr><td class="pad fx d{min(delay, 8)}" style="padding:0 22px">'
            f'{text(e(title.rstrip(":")), 21, 600, family=DISPLAY, extra="letter-spacing:-.02em;margin:0 0 12px 2px")}'
            f'<table role="presentation" class="card" width="100%" cellspacing="0" cellpadding="0" border="0" '
            f'style="background:{CARD};border-radius:18px;box-shadow:{SHADOW}">{rows}</table></td></tr>{space(36)}')


def aside(t, delay=1):
    return (f'<tr><td class="pad fx d{min(delay, 8)}" style="padding:0 24px">'
            f'{text(e(t), 19, 400, "gray", GRAY, SERIF, "font-style:italic;letter-spacing:0")}</td></tr>{space(36)}')


def glance(cells):
    tds = "".join(f'<td align="center" width="{100 // len(cells)}%" style="padding:18px 6px">'
                  f'<div class="ink num" style="font:200 34px/38px {DISPLAY};color:{color};letter-spacing:-.03em">{n}</div>'
                  f'<div class="gray" style="font:500 12px/16px {SANS};color:{GRAY};margin-top:4px">{e(label)}</div></td>' for n, label, color in cells)
    return (f'<table role="presentation" class="card fx d1" width="100%" cellspacing="0" cellpadding="0" border="0" '
            f'style="background:{CARD};border-radius:18px;box-shadow:{SHADOW};margin-top:24px"><tr>{tds}</tr></table>')


def buttons(links):
    if not links:
        return ""
    return '<div style="margin-top:20px">' + "".join(
        f'<a class="btn" href="{e(url)}" style="display:inline-block;margin:0 8px 8px 0;padding:10px 18px;border-radius:999px;background:#ffffff;'
        f'box-shadow:{SHADOW};color:{BLUE};font:500 15px/18px {SANS};letter-spacing:-.01em;text-decoration:none">{e(label)}</a>' for label, url in links) + "</div>"


def render(blocks, header, now, footer, preheader="", links=()):
    today = now.date()
    by = {b.key: b for b in blocks}
    urgent_n = len([i for i in by["priority"].items if i.kind not in ("followup", "more")]) if "priority" in by else 0
    bills_n = len(by["followup"].items) if "followup" in by else 0
    work_n = sum(len([i for i in by[k].items if i.kind != "more"]) for k in ("homework", "exams") if k in by)
    morning = header.startswith("Morning")
    greeting = by["greeting"].notes[0] if by["greeting"].notes else by["greeting"].text
    closing = by["closing"].text if "closing" in by else ""

    body, delay = [], 2
    for key in ("priority", "allclear", "schedule", "schedule_empty", "early", "homework", "homework_none", "exams", "notices", "followup",
                "paid", "people", "school", "invites", "health", "admin", "travel", "renewals", "action", "other"):
        blk = by.get(key)
        if not blk:
            continue
        if key == "followup":
            if blk.items:
                body.append(card("Follow up with", blk.items, today, delay=delay))
        elif key in ("allclear", "schedule_empty", "homework_none", "early"):
            body.append(aside(blk.text, delay))
        else:
            body.append(card(blk.lead, blk.items, today, blk.notes, delay))
        delay += 1

    pre = escape(preheader or greeting)[:140]
    hello = "Good morning." if morning else "Good afternoon."
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark"><meta name="supported-color-schemes" content="light dark">
<meta name="x-apple-disable-message-reformatting"><meta name="format-detection" content="telephone=no,date=no,address=no,email=no">
<title>{e(header)}</title>{CSS}</head>
<body class="page" style="margin:0;padding:0;background:{PAGE}">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent">{pre}&#8199;&#847;&#8199;&#847;&#8199;&#847;&#8199;&#847;</div>
<table role="presentation" class="page" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:{PAGE}"><tr><td align="center" style="padding:44px 0 48px">
<table role="presentation" class="wrap" width="600" cellspacing="0" cellpadding="0" border="0" style="width:100%;max-width:600px">

<tr><td class="pad fx" style="padding:0 22px">
  <div style="font:600 13px/16px {SANS};letter-spacing:.06em;text-transform:uppercase"><span class="red" style="color:{RED}">{e(now.strftime("%A"))}</span>
    <span class="gray" style="color:{GRAY}">&nbsp;{e(now.strftime("%B ") + str(now.day))}</span></div>
  <div class="ink hero" style="font:700 44px/48px {DISPLAY};color:{INK};letter-spacing:-.035em;margin:8px 0 12px">{hello}</div>
  <div class="gray voice" style="font:italic 400 21px/31px {SERIF};color:{GRAY}">{e(greeting)}</div>
  {glance([(urgent_n, "Urgent", RED if urgent_n else INK), (work_n, "Due this week", INK), (bills_n, "To follow up", INK)])}
  {buttons(links)}
</td></tr>
{space(40)}

{"".join(body)}

<tr><td class="pad" align="center" style="padding:0 28px">
  <div class="gray" style="font:italic 400 19px/28px {SERIF};color:{GRAY}">{e(closing)}</div>
  <div class="faint" style="font:400 12px/18px {SANS};color:{FAINT};margin-top:16px">{e(footer)}</div>
  <div class="faint" style="font:600 11px/16px {SANS};color:{FAINT};margin-top:6px;letter-spacing:.12em;text-transform:uppercase">Bruno</div>
</td></tr>
</table></td></tr></table></body></html>"""
