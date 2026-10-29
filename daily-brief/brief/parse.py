"""Turn raw Google API payloads into models."""
import base64
import re
from datetime import date, datetime, time, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from zoneinfo import ZoneInfo

from .models import Event, Mail


TAG = re.compile(r"\s*\[([^\]]+)\]\s*$")
HINT = re.compile(r"(?i)\b(?:by|before|due|until)\b[^.\n]{0,60}?(\d{1,2}(?::\d{2})?\s?[ap]\.?m\.?)")


MD_LINK = re.compile(r"\[([^\]]+)\]\s*\(https?://[^)]+\)")
URL = re.compile(r"https?://\S+")


def summarize(desc, title="", limit=130):
    """First readable sentence or two of a calendar description: links, markdown rules, brackets and
    lines that merely repeat the title are removed."""
    if not desc:
        return ""
    text = MD_LINK.sub(r"\1", unescape(re.sub(r"<[^>]+>", " ", desc)))
    text = URL.sub("", text).replace("[", "").replace("]", "")
    lines = [l.strip(" *-=#\t") for l in text.splitlines()]
    lines = [l for l in lines if len(l) > 3 and not re.fullmatch(r"[\W_]+", l)]
    words = set(re.findall(r"\w+", title.lower()))
    while lines and words and len(set(re.findall(r"\w+", lines[0].lower())) - words) <= 1:
        lines.pop(0)                       # "Final Project Proposal Report" under a title that already says it
    text = re.sub(r"\s+", " ", " ".join(lines)).strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(",;:") + "…"


def parse_event(raw, calendar, tz: ZoneInfo, hw_re, all_homework=False, compact=False, tag_is_homework=True):
    s, e = raw["start"], raw["end"]
    all_day = "date" in s
    if all_day:   # the API gives YYYY-MM-DD; some proxies append a time, so take the date part only
        start = datetime.combine(date.fromisoformat(s["date"][:10]), time.min, tz)
        end = datetime.combine(date.fromisoformat(e["date"][:10]), time.min, tz)
    else:
        start = datetime.fromisoformat(s["dateTime"]).astimezone(tz)
        end = datetime.fromisoformat(e["dateTime"]).astimezone(tz)
    title = raw.get("summary", "(no title)")
    desc = raw.get("description", "")
    tag = TAG.search(title)          # Canvas appends the course as a trailing [COURSE] tag
    course = tag.group(1) if tag else ""
    if tag:
        title = title[:tag.start()]
    hint = HINT.search(desc)
    homework = all_homework or bool(tag and tag_is_homework) or bool(hw_re.search(f"{title} {desc[:300]}"))
    return Event(title, start, end, all_day, calendar, raw.get("location", ""), homework, compact, course,
                 f"by {hint.group(1).upper().replace('.', '')}" if hint and homework else "",
                 (raw.get("creator") or {}).get("email", "").lower(), False, raw.get("htmlLink", ""), summarize(desc, title))


def _walk(part):
    yield part
    for p in part.get("parts", []) or []:
        yield from _walk(p)


def _decode(data):
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", "replace")


def body_text(payload):
    plain, html = "", ""
    for p in _walk(payload):
        data = p.get("body", {}).get("data")
        if not data:
            continue
        if p.get("mimeType") == "text/plain":
            plain += _decode(data)
        elif p.get("mimeType") == "text/html":
            html += _decode(data)
    if plain:
        return plain
    return unescape(re.sub(r"(?s)<(script|style).*?</\1>|<[^>]+>", " ", html))


def parse_mail(raw, tz: ZoneInfo):
    h = {x["name"].lower(): x["value"] for x in raw["payload"].get("headers", [])}
    try:
        when = parsedate_to_datetime(h["date"]).astimezone(tz)
    except (KeyError, TypeError, ValueError):
        when = datetime.fromtimestamp(int(raw["internalDate"]) / 1000, timezone.utc).astimezone(tz)
    labels = raw.get("labelIds", [])
    return Mail(raw["id"], h.get("from", ""), h.get("subject", "(no subject)"),
                unescape(raw.get("snippet", "")), when,
                unread="UNREAD" in labels, important="IMPORTANT" in labels,
                body=body_text(raw["payload"]) if raw["payload"].get("parts") or raw["payload"].get("body", {}).get("data") else "")
