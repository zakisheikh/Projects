from html import escape

TITLES = {
    "attention": "🚨 Needs attention",
    "today": "📅 Rest of today",
    "prayer": "🕌 Prayer times",
    "tomorrow": "🌅 Tomorrow",
    "homework": "📚 Homework later this week",
    "dues": "💳 Upcoming payments (unpaid)",
    "health": "🏥 Health & medical",
    "bills": "📄 New bills & statements",
    "paid": "✅ Payments confirmed",
    "balances": "🏦 Card & bank balances",
    "receipts": "🧾 Receipts",
    "info": "ℹ️ Other account notices",
    "school": "🎓 School mail",
    "logistics": "✈️ Deliveries & travel",
    "important": "✉️ Other important mail",
}


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
    course = f" ({course_name(ev.course, aliases)})" if ev.course else ""
    hint = f"  {ev.hint}" if ev.hint else ""
    return f"{when} · {ev.title.strip()}{course}{hint}"


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


def build(sections, header, greeting, closing, footer, leads):
    """sections: [(key, [lines])]; leads: {key: voice line}. Returns (text, html) for email."""
    text = [header, "", greeting, ""]
    html = ['<div style="font:15px/1.45 -apple-system,Segoe UI,sans-serif;max-width:640px;margin:auto;color:#1c1c1e">'
            f'<h2 style="margin:0 0 6px">{escape(header)}</h2><p style="margin:0 0 12px">{escape(greeting)}</p>']
    for key, lines in sections:
        lead = leads.get(key, "")
        if not lines and not (key == "attention" and lead):
            continue
        title = TITLES.get(key, key)
        text += [title.upper()] + ([f"  {lead}"] if lead else []) + [f"  • {l}" for l in lines] + [""]
        color = "#b3261e" if key == "attention" and lines else "#444"
        html.append(f'<h3 style="margin:18px 0 4px;font-size:13px;letter-spacing:.06em;text-transform:uppercase;color:{color}">{escape(title)}</h3>')
        if lead:
            html.append(f'<div style="color:#666;font-style:italic;margin-bottom:4px">{escape(lead)}</div>')
        if lines:
            html.append('<ul style="margin:0;padding-left:18px">' + "".join(f"<li>{escape(l)}</li>" for l in lines) + "</ul>")
    text += [closing, "", footer]
    html.append(f'<p style="margin-top:20px">{escape(closing)}</p><p style="color:#888;font-size:12px">{escape(footer)}</p></div>')
    return "\n".join(text), "\n".join(html)
