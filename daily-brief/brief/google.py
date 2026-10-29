"""Minimal Google REST client (stdlib only). Read-only Calendar/Gmail plus Gmail send."""
import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from email.message import EmailMessage

TOKEN_URL = "https://oauth2.googleapis.com/token"
CAL = "https://www.googleapis.com/calendar/v3"
GMAIL = "https://gmail.googleapis.com/gmail/v1/users/me"
SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]


class Google:
    def __init__(self, client_id, client_secret, refresh_token):
        self._creds = (client_id, client_secret, refresh_token)
        self._token = None
        self._expires = 0.0

    def _access_token(self):
        if self._token and time.time() < self._expires - 60:
            return self._token
        cid, secret, refresh = self._creds
        body = urllib.parse.urlencode({
            "client_id": cid, "client_secret": secret,
            "refresh_token": refresh, "grant_type": "refresh_token",
        }).encode()
        data = _send(urllib.request.Request(TOKEN_URL, data=body))
        self._token = data["access_token"]
        self._expires = time.time() + data.get("expires_in", 3600)
        return self._token

    def _call(self, url, params=None, payload=None):
        if params:
            url += "?" + urllib.parse.urlencode(params, doseq=True)
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(url, data=data, headers={
            "Authorization": f"Bearer {self._access_token()}",
            "Content-Type": "application/json",
        })
        return _send(req)

    # --- calendar ---
    def calendars(self):
        return self._call(f"{CAL}/users/me/calendarList").get("items", [])

    def events(self, calendar_id, start, end):
        out, token = [], None
        while True:
            params = {"timeMin": start.isoformat(), "timeMax": end.isoformat(),
                      "singleEvents": "true", "orderBy": "startTime", "maxResults": 250}
            if token:
                params["pageToken"] = token
            page = self._call(f"{CAL}/calendars/{urllib.parse.quote(calendar_id)}/events", params)
            out += page.get("items", [])
            token = page.get("nextPageToken")
            if not token:
                return out

    # --- gmail ---
    def my_address(self):
        return self._call(f"{GMAIL}/profile")["emailAddress"]

    def search(self, query, limit=100):
        res = self._call(f"{GMAIL}/messages", {"q": query, "maxResults": limit})
        return [m["id"] for m in res.get("messages", [])]

    def message(self, msg_id, full=False):
        params = {"format": "full"} if full else {
            "format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]}
        return self._call(f"{GMAIL}/messages/{msg_id}", params)

    def send(self, to, subject, text, html):
        m = EmailMessage()
        m["To"], m["Subject"] = to, subject
        m.set_content(text)
        m.add_alternative(html, subtype="html")
        raw = base64.urlsafe_b64encode(m.as_bytes()).decode()
        return self._call(f"{GMAIL}/messages/send", payload={"raw": raw})


def _send(req, retries=3):
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"{e.code} from {req.full_url.split('?')[0]}: {e.read().decode()[:300]}") from None
        except urllib.error.URLError:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
