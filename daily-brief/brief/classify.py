"""Rule-based classification. Deterministic: same input, same output."""
import re
from datetime import date

MONTHS = "jan feb mar apr may jun jul aug sep oct nov dec".split()
AMOUNT = re.compile(r"(?i)(?:amount (?:due|you owe)|balance(?: due)?|total due|minimum payment(?: due)?|payment due|you owe)[^$\d]{0,40}\$\s?([\d,]+\.\d{2})")
ANY_AMOUNT = re.compile(r"\$\s?([\d,]+\.\d{2})")
DUE = re.compile(r"(?i)(?:due(?: on| by| date)?|pay by|payment date)[:\s]+(?:[a-z]{3,9},?\s+)?"
                 r"(?:(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?|([a-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?)")


def compile_rules(cfg):
    return {name: [re.compile(p) for p in r.get("sender", [])] +
                  [re.compile(p) for p in r.get("text", [])]
            for name, r in cfg["mail"]["rules"].items()}, \
           {name: len(r.get("sender", [])) for name, r in cfg["mail"]["rules"].items()}


def categorize(mail, rules, n_sender):
    """Text patterns on subject/snippet decide. A sender match alone (bank promos)
    is not enough, except for school senders where any mail is relevant."""
    cats = []
    for name, pats in rules.items():
        k = n_sender[name]
        s_hit = any(p.search(mail.sender) for p in pats[:k])
        t_hit = any(p.search(f"{mail.subject} {mail.snippet}") for p in pats[k:])
        if t_hit or (s_hit and name == "school"):
            cats.append(name)
    return cats


def _num(s):
    return float(s.replace(",", ""))


def extract_amount(text):
    m = AMOUNT.search(text)
    return f"${_num(m.group(1)):,.2f}" if m else None


def extract_due(text, today: date):
    m = DUE.search(text)
    if not m:
        return None
    try:
        if m.group(1):
            mo, d, y = int(m.group(1)), int(m.group(2)), m.group(3)
            y = (2000 + int(y) if y and len(y) == 2 else int(y)) if y else today.year
        else:
            mo = MONTHS.index(m.group(4)[:3].lower()) + 1
            d, y = int(m.group(5)), int(m.group(6) or today.year)
        out = date(y, mo, d)
        if not (m.group(3) or m.group(6)) and (today - out).days > 180:
            out = out.replace(year=out.year + 1)
        return out
    except (ValueError, IndexError):
        return None
