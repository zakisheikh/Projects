"""One-time local helper: obtain a Google refresh token.

  GOOGLE_CLIENT_ID=... GOOGLE_CLIENT_SECRET=... python3 auth_setup.py

Opens a browser consent screen (loopback redirect) and prints the refresh token.
"""
import json
import os
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

from brief.google import SCOPES, TOKEN_URL

PORT = 8765
REDIRECT = f"http://127.0.0.1:{PORT}"
cid, secret = os.environ["GOOGLE_CLIENT_ID"], os.environ["GOOGLE_CLIENT_SECRET"]
url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
    "client_id": cid, "redirect_uri": REDIRECT, "response_type": "code",
    "scope": " ".join(SCOPES), "access_type": "offline", "prompt": "consent"})
got = {}


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        got.update(urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Done. You can close this tab.")

    def log_message(self, *a):
        pass


print("Opening browser...\n", url)
webbrowser.open(url)
HTTPServer(("127.0.0.1", PORT), H).handle_request()
body = urllib.parse.urlencode({"code": got["code"][0], "client_id": cid, "client_secret": secret,
                               "redirect_uri": REDIRECT, "grant_type": "authorization_code"}).encode()
tok = json.load(urllib.request.urlopen(urllib.request.Request(TOKEN_URL, data=body)))
print("\nGOOGLE_REFRESH_TOKEN =", tok["refresh_token"])
