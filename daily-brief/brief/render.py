from html import escape

TITLES = {
    "attention": "Needs attention",
    "today": "Rest of today",
    "tomorrow": "Tomorrow",
    "homework": "Homework / due soon",
    "dues": "Upcoming payments (unpaid)",
    "health": "Health & medical",
    "bills": "New bills & statements",
    "paid": "Payments confirmed",
    "balances": "Card & bank balances",
    "receipts": "Receipts",
    "info": "Other account notices",
    "school": "School mail",
    "security": "Security",
    "logistics": "Deliveries & travel",
    "important": "Other important mail",
}


def fmt_time(ev):
    return "all day" if ev.all_day else ev.start.strftime("%-I:%M%p").lower()


def event_line(ev, with_day=False):
    day = ev.start.strftime("%a %-m/%-d ") if with_day else ""
    loc = f" @ {ev.location}" if ev.location else ""
    return f"{day}{fmt_time(ev)}  {ev.title}{loc}"


def sender_name(m):
    return m.sender.split("<")[0].strip().strip('"') or m.sender


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


def build(sections, header, footer):
    """sections: list of (key, [lines]). Returns (text, html)."""
    text = [header, ""]
    html = [f'<div style="font:15px/1.45 -apple-system,Segoe UI,sans-serif;max-width:640px;margin:auto;color:#1c1c1e">'
            f'<h2 style="margin:0 0 12px">{escape(header)}</h2>']
    for key, lines in sections:
        if not lines:
            continue
        title = TITLES.get(key, key)
        text += [title.upper(), *[f"  • {l}" for l in lines], ""]
        color = "#b3261e" if key == "attention" else "#444"
        html.append(f'<h3 style="margin:18px 0 6px;font-size:13px;letter-spacing:.06em;text-transform:uppercase;color:{color}">{escape(title)}</h3><ul style="margin:0;padding-left:18px">')
        html += [f"<li>{escape(l)}</li>" for l in lines]
        html.append("</ul>")
    text.append(footer)
    html.append(f'<p style="margin-top:22px;color:#888;font-size:12px">{escape(footer)}</p></div>')
    return "\n".join(text), "\n".join(html)
