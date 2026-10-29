"""Tiny JSON state kept on a dedicated git branch by the workflow (see daily-brief.yml)."""
import json
from datetime import datetime, timedelta


def load(path):
    if not path:
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save(path, st):
    if path:
        with open(path, "w") as f:
            json.dump(st, f, indent=1, sort_keys=True)


def last_sent(st, tz):
    try:
        return datetime.fromisoformat(st["last_sent"]).astimezone(tz)
    except (KeyError, ValueError):
        return None


def prune_seen(seen, now, days=7):
    cut = (now - timedelta(days=days)).isoformat()
    return {k: v for k, v in seen.items() if v >= cut}
