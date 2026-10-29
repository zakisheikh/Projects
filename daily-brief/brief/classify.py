"""Rule-based classification. Deterministic: same input, same output."""
import re
from datetime import date, timedelta

MONTHS = "jan feb mar apr may jun jul aug sep oct nov dec".split()
AMOUNT_KEYS = ["total current charges", "amount you owe", "amount due", "total due", "balance due",
               "minimum payment due", "minimum payment", "payment amount", "current charges", "payment due"]
ANY_AMOUNT = re.compile(r"\$\s?([\d,]+\.\d{2})")
DUE = re.compile(r"(?i)\bdue(?: on| by| date)?(?:\s+is)?[:\s|]+(?:[a-z]{3,9},?\s+)?"
                 r"(?:(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?|([a-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?)")
REL = re.compile(r"(?i)\bdue (today|tomorrow)\b(?:,?\s+([a-z]{3,9})\.?\s+(\d{1,2}))?")
AUTOPAY = re.compile(r"(?i)\bnon[- ]?auto ?pay\b|\bauto-?\s?pay(?:ment)?s?\s*[:\-|]?\s*(on|off)\b")


SENDER_ONLY = {"school", "people"}   # for these, who it is from is enough


def compile_rules(cfg):
    """Generic keyword categories (health, school, security, ...). Returns (rules, n_sender)."""
    rules, n_sender = {}, {}
    for name, r in cfg["mail"]["rules"].items():
        rules[name] = [re.compile(p) for p in r.get("sender", [])] + [re.compile(p) for p in r.get("text", [])]
        n_sender[name] = len(r.get("sender", []))
    return rules, n_sender


def categorize(mail, rules, n_sender):
    """Text patterns on subject/snippet decide. A sender match alone (bank promos)
    is not enough, except for school and people, where any mail from them is relevant."""
    cats = []
    for name, pats in rules.items():
        k = n_sender[name]
        s_hit = any(p.search(mail.sender) for p in pats[:k])
        t_hit = any(p.search(f"{mail.subject} {mail.snippet}") for p in pats[k:])
        if t_hit or (s_hit and name in SENDER_ONLY):
            cats.append(name)
    if "receipt" in cats:
        cats = [c for c in cats if c != "bill"]
    return cats


def compile_billers(cfg):
    return [dict(name=b["name"], kind=b.get("kind", "bill"), frm=re.compile(b["from"]),
                 rules=[(re.compile(r["subject"]), r["event"]) for r in b["rules"]])
            for b in cfg.get("billers", [])]


def match_biller(mail, billers):
    """First biller whose sender matches AND whose subject rule matches -> (name, kind, event)."""
    for b in billers:
        if not b["frm"].search(mail.sender):
            continue
        for pat, event in b["rules"]:
            if pat.search(mail.subject):
                return b["name"], b["kind"], event
    return None


def _num(s):
    return float(s.replace(",", ""))


def extract_amount(text):
    for key in AMOUNT_KEYS:
        m = re.search(key + r"[^$]{0,80}\$\s?([\d,]+\.\d{2})", text, re.I)
        if m:
            return f"${_num(m.group(1)):,.2f}"
    return None


def first_amount(text):
    m = ANY_AMOUNT.search(text)
    return f"${_num(m.group(1)):,.2f}" if m else None


def extract_autopay(text):
    m = AUTOPAY.search(text)
    if not m:
        return None
    return "autopay on" if (m.group(1) or "").lower() == "on" else "autopay OFF"


def _month(name):
    n = name[:3].lower()
    return MONTHS.index(n) + 1 if n in MONTHS else None


def extract_due(text, ref: date):
    """ref = date the message was sent; used for 'due today/tomorrow' and missing years."""
    try:
        m = DUE.search(text)
        if m:
            if m.group(1):
                mo, d, y = int(m.group(1)), int(m.group(2)), m.group(3)
                y = (2000 + int(y) if len(y) == 2 else int(y)) if y else ref.year
            else:
                mo = _month(m.group(4))
                if mo is None:
                    raise ValueError
                d, y = int(m.group(5)), int(m.group(6) or ref.year)
            out = date(y, mo, d)
            if not (m.group(3) or m.group(6)) and (ref - out).days > 180:
                out = out.replace(year=out.year + 1)
            return out
        m = REL.search(text)
        if m:
            base = ref + timedelta(days=1 if m.group(1).lower() == "tomorrow" else 0)
            mo = _month(m.group(2)) if m.group(2) else None
            if mo:
                out = date(ref.year, mo, int(m.group(3)))
                return out.replace(year=out.year + 1) if (ref - out).days > 180 else out
            return base
    except (ValueError, IndexError):
        pass
    return None


BY = re.compile(r"(?i)\b(?:by|before|until|deadline)\b[^.\n]{0,25}?\b([a-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?")


def extract_deadline(text, ref: date):
    """'update your login by December 7th' -> that date. For 'action needed' mail."""
    for m in BY.finditer(text):
        mo = _month(m.group(1))
        if not mo:
            continue
        try:
            out = date(int(m.group(3)) if m.group(3) else ref.year, mo, int(m.group(2)))
        except ValueError:
            continue
        if not m.group(3) and (ref - out).days > 180:
            out = out.replace(year=out.year + 1)
        return out
    return None


BALANCE = re.compile(r"(?i)statement balance[^$]{0,60}\$\s?([\d,]+\.\d{2})")


def extract_balance(text):
    m = BALANCE.search(text)
    return f"${_num(m.group(1)):,.2f}" if m else None
