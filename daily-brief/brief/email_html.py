"""The HTML email, designed in the Apple idiom: quiet grey page, inset grouped lists, system type,
generous space, one accent colour. Table layout + inline styles for every client; dark mode via a <style> block.
No images, no web fonts, no JavaScript."""
from html import escape

FONT = "-apple-system,BlinkMacSystemFont,'SF Pro Text','SF Pro Display','Helvetica Neue',Helvetica,Arial,sans-serif"

# light palette (dark overrides live in CSS below) -- after iOS system colours
INK, GRAY, FAINT, HAIR, GROUP, PAGE = "#1d1d1f", "#6e6e73", "#a1a1a6", "#e5e5ea", "#ffffff", "#f5f5f7"
BLUE, RED, ORANGE = "#0071e3", "#d70015", "#c93400"

CSS = """
<style>
  :root { color-scheme: light dark; supported-color-schemes: light dark; }
  body, table, td, p, a { -webkit-text-size-adjust:100%; -ms-text-size-adjust:100%; }
  a { color:inherit; text-decoration:none; }
  @media (max-width: 640px) {
    .wrap { width:100% !important; } .pad { padding-left:14px !important; padding-right:14px !important; }
    .big { font-size:34px !important; line-height:38px !important; }
    .col { width:72px !important; font-size:14px !important; }
    .btn { display:inline-block !important; margin:0 6px 8px 0 !important; }
  }
  @media (prefers-color-scheme: dark) {
    .page { background:#000000 !important; } .group { background:#1c1c1e !important; }
    .ink { color:#f5f5f7 !important; } .gray { color:#98989d !important; } .faint { color:#636366 !important; }
    .hair { border-color:#38383a !important; } .red { color:#ff453a !important; } .orange { color:#ff9f0a !important; } .blue { color:#2997ff !important; } .btn { background:#2c2c2e !important; color:#2997ff !important; }
  }
</style>
"""


def e(x):
    return escape(str(x), quote=True)


def gap(h=24):
    return f'<tr><td style="height:{h}px;line-height:{h}px;font-size:0">&nbsp;</td></tr>'


def cell(inner, last=False, link=""):
    border = "" if last else f"border-bottom:1px solid {HAIR};"
    chevron = (f'<td width="14" valign="middle" class="faint" style="font:400 20px/20px {FONT};color:{FAINT};padding-left:8px">&rsaquo;</td>' if link else "")
    body = (f'<a href="{e(link)}" style="display:block">{inner}</a>' if link else inner)
    return (f'<tr><td class="hair" style="padding:0 0 0 16px;{border}"><table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr>'
            f'<td style="padding:12px 16px 12px 0">{body}</td>{chevron.replace("padding-left:8px", "padding:0 14px 0 0")}</tr></table></td></tr>')


def line(text, size=17, weight=400, cls="ink", color=INK, extra=""):
    return f'<div class="{cls}" style="font:{weight} {size}px/{size + 6}px {FONT};color:{color};letter-spacing:-.01em;{extra}">{e(text)}</div>'


def sub(text, cls="gray", color=GRAY):
    return f'<div class="{cls}" style="font:400 13px/18px {FONT};color:{color};margin-top:1px">{text}</div>'


def detail(text):
    return f'<div class="gray" style="font:400 14px/20px {FONT};color:{GRAY};margin-top:3px">{e(text)}</div>' if text else ""


def due_color(item, today):
    d = item.day
    if not d:
        return "gray", GRAY
    return ("red", RED) if (d - today).days <= 1 else ("gray", GRAY)


def item_cell(item, today, last):
    k = item.kind
    if k in ("hw", "exam", "notice"):
        cls, col = due_color(item, today)
        left = (f'<td width="92" valign="top" class="col {cls}" style="width:92px;font:500 15px/22px {FONT};color:{col};padding-top:1px;white-space:nowrap">{e(item.label)}</td>')
        bits = [x for x in (("Exam" if k == "exam" else ""), item.course) if x]
        tail = e(" · ".join(bits))
        hint = (f'<span class="red" style="color:{RED}">{e(item.hint)}</span>' if item.hint else "")
        meta = " · ".join(x for x in (tail, hint) if x)
        inner = (f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr>{left}<td valign="top">'
                 f'{line(item.title)}{sub(meta) if meta else ""}{detail(item.detail)}</td></tr></table>')
        return cell(inner, last, item.link)
    if k == "event":
        partner = next((f.split(":", 1)[1] for f in item.flags if f.startswith("partner:")), "")
        meta = " · ".join(e(x) for x in (item.detail, partner) if x)
        warn = f'<div class="orange" style="font:500 13px/18px {FONT};color:{ORANGE};margin-top:1px">Overlaps another event</div>' if "overlap" in item.flags else ""
        inner = (f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr>'
                 f'<td width="92" valign="top" class="col gray" style="width:92px;font:500 15px/22px {FONT};color:{GRAY};padding-top:1px;white-space:nowrap">{e(item.label)}</td>'
                 f'<td valign="top">{line(item.title)}{sub(meta) if meta else ""}{warn}</td></tr></table>')
        return cell(inner, last, item.link)
    if k == "bill":
        urgent = "urgent" in item.flags
        cls, col = ("red", RED) if urgent else ("gray", GRAY)
        due = f'<span class="{cls}" style="color:{col}">{e(item.due)}</span>' if item.due else ""
        auto = f'<span class="orange" style="color:{ORANGE}">Autopay is off</span>' if "autopay off" in item.flags else ""
        meta = " · ".join(x for x in (due, e(item.detail) if item.detail else "", auto) if x)
        amount = f'<div class="ink" style="font:600 17px/23px {FONT};color:{INK};text-align:right;white-space:nowrap">{e(item.amount)}</div>' if item.amount else ""
        inner = (f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr><td valign="top">{line(item.who)}{sub(meta) if meta else ""}</td>'
                 f'<td valign="top" align="right">{amount}</td></tr></table>')
        return cell(inner, last, item.link)
    if k in ("alert", "action", "account"):
        word, cls, col = {"alert": ("Alert", "red", RED), "action": ("Action needed", "orange", ORANGE), "account": ("Account problem", "red", RED)}[k]
        by = f" · by {e(item.due)}" if item.due else ""
        return cell(f'{line(item.title or item.text)}<div class="{cls}" style="font:500 13px/18px {FONT};color:{col};margin-top:1px">{e(word)} · {e(item.who)}{by}</div>',
                    last, item.link)
    if k == "paid":
        amount = f'<div class="ink" style="font:600 17px/23px {FONT};color:{INK};text-align:right">{e(item.amount)}</div>' if item.amount else ""
        inner = (f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr><td>{line(item.who)}{sub("Payment received")}</td>'
                 f'<td align="right">{amount}</td></tr></table>')
        return cell(inner, last, item.link)
    if k == "more":
        return cell(f'<div class="gray" style="font:italic 400 15px/22px {FONT};color:{GRAY}">{e(item.text)}</div>', last)
    caution = "Unknown sender" if "unknown sender" in item.flags else ""
    meta = e(item.who) + (f' · <span class="orange" style="color:{ORANGE}">{caution}</span>' if caution else "")
    return cell(f'{line(item.title or item.text, 16, 500)}{detail(item.detail)}{sub(meta)}', last, item.link)


def group(block, today):
    items = [i for i in block.items if not (block.key == "priority" and i.kind == "followup")]
    if not items and not block.notes:
        return ""
    rows = "".join(item_cell(i, today, n == len(items) - 1 and not block.notes) for n, i in enumerate(items))
    for n, text in enumerate(block.notes):
        rows += cell(f'<div class="orange" style="font:400 15px/22px {FONT};color:{ORANGE}">{e(text)}</div>', n == len(block.notes) - 1)
    return (f'<tr><td class="pad" style="padding:0 20px 6px"><div class="gray" style="font:400 13px/18px {FONT};color:{GRAY};text-transform:uppercase;letter-spacing:.04em">{e(block.lead.rstrip(":"))}</div></td></tr>'
            f'<tr><td class="pad" style="padding:0 20px"><table role="presentation" class="group" width="100%" cellspacing="0" cellpadding="0" border="0" '
            f'style="background:{GROUP};border-radius:12px;overflow:hidden">{rows}</table></td></tr>{gap(28)}')


def sentence(text):
    return (f'<tr><td class="pad" style="padding:0 20px"><div class="gray" style="font:400 17px/25px {FONT};color:{GRAY};letter-spacing:-.01em">{e(text)}</div></td></tr>{gap(28)}')


def buttons(links):
    if not links:
        return ""
    out = "".join(f'<a class="btn" href="{e(url)}" style="display:inline-block;margin:0 8px 8px 0;padding:9px 16px;border-radius:18px;'
                  f'background:#e8e8ed;color:{BLUE};font:500 15px/18px {FONT};text-decoration:none">{e(label)}</a>' for label, url in links)
    return f'<div style="margin-top:18px">{out}</div>'


def render(blocks, header, now, footer, preheader="", links=()):
    today = now.date()
    by = {b.key: b for b in blocks}
    urgent_n = len([i for i in by["priority"].items if i.kind not in ("followup", "more")]) if "priority" in by else 0
    bills_n = len(by["followup"].items) if "followup" in by else 0
    work_n = sum(len(by[k].items) for k in ("homework", "exams") if k in by)
    bits = [f"{urgent_n} urgent" if urgent_n else "", f"{work_n} due this week" if work_n else "", f"{bills_n} to follow up" if bills_n else ""]
    summary = " · ".join(b for b in bits if b) or "All clear"
    greeting = by["greeting"].text
    closing = by["closing"].text if "closing" in by else ""

    body = []
    for key in ("priority", "allclear", "schedule", "schedule_empty", "early", "homework", "homework_none", "exams", "notices", "followup",
                "paid", "people", "school", "invites", "health", "admin", "travel", "renewals", "action", "other"):
        blk = by.get(key)
        if not blk:
            continue
        if key == "followup":
            if blk.items:
                blk = type(blk)("followup", "Follow up with", blk.items)
                body.append(group(blk, today))
        elif key in ("allclear", "schedule_empty", "homework_none", "early"):
            body.append(sentence(blk.text))
        else:
            body.append(group(blk, today))
    pre = escape(preheader or greeting)[:140]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark"><meta name="supported-color-schemes" content="light dark">
<meta name="x-apple-disable-message-reformatting"><meta name="format-detection" content="telephone=no,date=no,address=no,email=no">
<title>{e(header)}</title>{CSS}</head>
<body class="page" style="margin:0;padding:0;background:{PAGE}">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent">{pre}&#8199;&#847;&#8199;&#847;&#8199;&#847;&#8199;&#847;</div>
<table role="presentation" class="page" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:{PAGE}"><tr><td align="center" style="padding:36px 0 40px">
<table role="presentation" class="wrap" width="600" cellspacing="0" cellpadding="0" border="0" style="width:600px;max-width:600px">

<tr><td class="pad" style="padding:0 20px">
  <div class="gray" style="font:500 15px/20px {FONT};color:{GRAY}">{e(now.strftime("%B ") + str(now.day))} &nbsp;·&nbsp; {e(header.split(" — ")[0])}</div>
  <div class="big ink" style="font:700 40px/44px {FONT};color:{INK};letter-spacing:-.03em;margin:4px 0 10px">{e(now.strftime("%A"))}</div>
  <div class="gray" style="font:400 19px/27px {FONT};color:{GRAY};letter-spacing:-.01em">{e(greeting)}</div>
  <div class="ink" style="font:500 15px/22px {FONT};color:{INK};margin-top:14px">{e(summary)}</div>
  {buttons(links)}
</td></tr>
{gap(32)}

{"".join(body)}

<tr><td class="pad" align="center" style="padding:4px 20px 0">
  <div class="gray" style="font:400 17px/25px {FONT};color:{GRAY};letter-spacing:-.01em">{e(closing)}</div>
  <div class="faint" style="font:400 12px/18px {FONT};color:{FAINT};margin-top:14px">{e(footer)}</div>
</td></tr>
</table></td></tr></table></body></html>"""
