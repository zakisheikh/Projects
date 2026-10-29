import json
import urllib.error
import urllib.request
from html import escape as _esc

def escape(x):
    return _esc(x, quote=False)


LIMIT = 3900   # Telegram caps a message at 4096 characters


def chunks(text, limit=LIMIT):
    out, cur = [], ""
    for para in text.split("\n\n"):
        if len(cur) + len(para) + 2 > limit and cur:
            out.append(cur)
            cur = ""
        while len(para) > limit:
            out.append(para[:limit])
            para = para[limit:]
        cur = f"{cur}\n\n{para}" if cur else para
    if cur:
        out.append(cur)
    return out


def send(token, chat_id, html_text):
    for part in chunks(html_text):
        body = json.dumps({"chat_id": chat_id, "text": part, "parse_mode": "HTML",
                           "disable_web_page_preview": True}).encode()
        req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                if not json.load(r).get("ok"):
                    raise RuntimeError("telegram rejected the message")
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"telegram {e.code}: {e.read().decode()[:200]}") from None


def fmt(greeting, blocks, closing, sources=""):
    """blocks: list of (title, lead, [lines]) -> Telegram HTML."""
    parts = [escape(greeting)]
    for title, lead, lines in blocks:
        head = f"<b>{escape(title)}</b>" + (f"\n<i>{escape(lead)}</i>" if lead else "")
        parts.append(head + ("\n" + "\n".join(f"• {escape(l)}" for l in lines) if lines else ""))
    parts.append(f"<i>{escape(closing)}</i>" + (f"\n\n{escape(sources)}" if sources else ""))
    return "\n\n".join(parts)
