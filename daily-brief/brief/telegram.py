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


def keyboard(buttons):
    """[(label, data)] -> one Done button per row."""
    return {"inline_keyboard": [[{"text": label[:60], "callback_data": data}] for label, data in buttons]}


def updates(token, offset=None):
    """Button taps waiting since the last brief. Telegram keeps them for about a day, which covers the
    gap between briefs; reading does not consume them until we ask again with a higher offset."""
    url = f"https://api.telegram.org/bot{token}/getUpdates?timeout=0&allowed_updates=%5B%22callback_query%22%5D"
    if offset:
        url += f"&offset={int(offset)}"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"telegram {e.code}: {e.read().decode()[:200]}") from None
    return data.get("result", []) if data.get("ok") else []


def send(token, chat_id, html_text, buttons=None):
    parts = chunks(html_text)
    for n, part in enumerate(parts):
        payload = {"chat_id": chat_id, "text": part, "parse_mode": "HTML", "disable_web_page_preview": True}
        if buttons and n == len(parts) - 1:
            payload["reply_markup"] = keyboard(buttons)
        body = json.dumps(payload).encode()
        req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                if not json.load(r).get("ok"):
                    raise RuntimeError("telegram rejected the message")
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"telegram {e.code}: {e.read().decode()[:200]}") from None


def fmt(paragraphs):
    """Telegram HTML: plain spoken paragraphs, nothing fancy."""
    return "\n\n".join(escape(p) for p in paragraphs)
