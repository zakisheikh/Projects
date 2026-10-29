import re
from html import escape

def fmt_time(ev):
    return "all day" if ev.all_day else ev.start.strftime("%-I:%M%p").lower()


def event_line(ev, with_day=False):
    day = ev.start.strftime("%a %-m/%-d ") if with_day else ""
    loc = f" @ {ev.location.strip().split(',')[0]}" if ev.location.strip() else ""
    return f"{day}{fmt_time(ev)}  {ev.title.strip()}{loc}"


def course_name(tag, aliases):
    for key, short in aliases.items():
        if key.lower() in tag.lower():
            return short
    return tag[:18]


def hw_line(ev, aliases):
    when = ev.start.strftime("%a %-m/%-d")
    title = re.sub(r"\s*\((classic|new)\)\s*$", "", ev.title.strip(), flags=re.I)
    course = f" ({course_name(ev.course, aliases)})" if ev.course else ""
    hint = f"  {ev.hint}" if ev.hint else ""
    return f"{when} · {title}{course}{hint}"


def sender_name(m):
    name = m.sender.split("<")[0].strip().strip('"')
    if name and "@" not in name:
        return name
    addr = m.sender.split("<")[-1].strip("> ")      # bare address: show the company domain, not the mailbox
    domain = addr.split("@")[-1].split(".")
    return ".".join(domain[-2:]) if len(domain) >= 2 else addr


def mail_line(m, who=None):
    name = who or sender_name(m)
    extra = ""
    if m.amount:
        extra += f"  [{m.amount}]"
    if m.due:
        extra += f"  [due {m.due.strftime('%a %-m/%-d')}]"
    if m.note:
        extra += f"  [{m.note}]"
    return f"{name[:28]}: {m.subject[:80]}{extra}"


def build(paragraphs, header, footer):
    """Email version: the spoken paragraphs as plain text and simple HTML."""
    text = "\n\n".join([header] + paragraphs + [footer])
    body = "".join(f'<p style="margin:0 0 14px">{escape(p).replace(chr(10), "<br>")}</p>' for p in paragraphs)
    html = ('<div style="font:16px/1.55 -apple-system,Segoe UI,sans-serif;max-width:620px;margin:auto;color:#1c1c1e">'
            f'<h3 style="margin:0 0 14px;color:#666;font-weight:600">{escape(header)}</h3>{body}'
            f'<p style="color:#999;font-size:12px">{escape(footer)}</p></div>')
    return text, html
