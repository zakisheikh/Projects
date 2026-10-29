"""Turn raw Google API payloads into models."""
import base64
import re
from datetime import date, datetime, time, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from zoneinfo import ZoneInfo

from .models import Event, Mail


def parse_event(raw, calendar, tz: ZoneInfo, hw_re):
    s, e = raw["start"], raw["end"]
    all_day = "date" in s
    if all_day:
        start = datetime.combine(date.fromisoformat(s["date"]), time.min, tz)
        end = datetime.combine(date.fromisoformat(e["date"]), time.min, tz)
    else:
        start = datetime.fromisoformat(s["dateTime"]).astimezone(tz)
        end = datetime.fromisoformat(e["dateTime"]).astimezone(tz)
    title = raw.get("summary", "(no title)")
    text = f"{title} {raw.get('description', '')}"
    return Event(title, start, end, all_day, calendar, raw.get("location", ""),
                 bool(hw_re.search(text)))


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
