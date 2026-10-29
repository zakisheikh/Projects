"""One-time helper: find your Telegram chat id.

1. In Telegram, talk to @BotFather -> /newbot -> copy the token.
2. Open your new bot and send it any message (e.g. "hi").
3. Run:  TELEGRAM_BOT_TOKEN=... python3 telegram_setup.py
"""
import json
import os
import urllib.request

token = os.environ["TELEGRAM_BOT_TOKEN"]
data = json.load(urllib.request.urlopen(f"https://api.telegram.org/bot{token}/getUpdates"))
chats = {(m["message"]["chat"]["id"], m["message"]["chat"].get("first_name", "")) for m in data["result"] if "message" in m}
if not chats:
    raise SystemExit("No messages yet: send your bot a message first, then re-run.")
for cid, name in chats:
    print(f"chat id {cid}  ({name})  -> store as secret TELEGRAM_CHAT_ID")
