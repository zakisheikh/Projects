# daily-brief

A 7am + noon email digest: rest of today's calendar, homework/due dates, health bills,
credit-card statements and alerts, security notices, and other important mail.
Pure rules and regexes (`config.toml`) — no AI, no third-party dependencies (Python 3.11+ stdlib).

## Why this stack

| Option | Verdict |
|---|---|
| **GitHub Actions cron** | **Chosen.** Free, runs in the cloud, secrets built in, logs, manual "run now" button, code already lives here. Caveats: cron is UTC and may lag a few minutes (handled by a slot + grace window), and schedules pause after 60 days of repo inactivity on public repos (use a private repo, or any commit/dispatch re-enables). |
| Vercel Cron | Fine, but needs a deployed HTTP function + `CRON_SECRET`; Hobby plan crons run only once/day with ±1h precision. Overkill here. |
| Cloudflare Workers cron / AWS EventBridge | Excellent reliability, but more setup for no gain at this scale. |
| Home server / laptop | Defeats the purpose (must be awake). |

Python because the work is string parsing + a few REST calls; stdlib alone is enough, so there's nothing to patch or break.

## What it reads (read-only except sending the brief)

Scopes: `calendar.readonly`, `gmail.readonly`, `gmail.send`. It never modifies or deletes anything.
Delivery: a Telegram bot (short, in "Bruno's" voice) plus the full brief by email. Wording comes from `phrases.toml`
(no AI); the persona name is `[persona]` in `config.toml`.

## Setup (one time)

1. **Google**: Cloud Console project, enable Gmail API + Google Calendar API, OAuth consent screen **In production**, Desktop-app OAuth client.
   Run `GOOGLE_CLIENT_ID=… GOOGLE_CLIENT_SECRET=… python3 auth_setup.py` once per Gmail account (after publishing).
2. **Telegram**: talk to @BotFather → `/newbot` → copy the token; message your new bot once; run
   `TELEGRAM_BOT_TOKEN=… python3 telegram_setup.py` to get your chat id.
3. **Repo** (must be private) → Settings → Secrets → Actions: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`
   (+ `_2`, `_3` for more accounts), `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
4. Merge to the default branch (schedules only run there). Actions → daily-brief → Run workflow with dry run on, read the log, then off.

The workflow runs at 7:17 and 12:17 America/Los_Angeles (cron fires at both the PDT and PST UTC hours; the off-season run exits).
State (last send time, reported mail ids, last phrases, run lateness) lives in `state.json` on the `brief-state` branch, which the workflow creates.

## Run locally
```
export GOOGLE_CLIENT_ID=… GOOGLE_CLIENT_SECRET=… GOOGLE_REFRESH_TOKEN=…
python3 -m brief --force --dry-run --state /tmp/state.json
python3 -m brief --force --dry-run --explain --state /tmp/state.json   # shows where every input went
python3 -m unittest discover -s tests -t .
```

## Multiple Gmail accounts
List each login under `[[accounts]]` in `config.toml` with its own `token_env`. Use the same OAuth client for all: run
`auth_setup.py` once per account (sign in as that account), then add a secret per account (`GOOGLE_REFRESH_TOKEN`, `GOOGLE_REFRESH_TOKEN_2`, …;
the workflow already forwards `_2` and `_3`). Mail, calendars and bills from all accounts are merged and tagged `[name]`;
a calendar shared between logins appears once; one broken login is reported under *Needs attention* instead of killing the brief.

## Bills
`[[billers]]` in `config.toml` are sender + subject templates learned from real notices (Chase, Synchrony, rent, utilities, insurance, health, …).
Each notice becomes an event (due / statement / paid / balance / alert / receipt / ignore). A "payment due" notice stays on the
*Upcoming payments* list for `lookback_days` until a later "payment received" notice from the same biller settles it; autopay-off is flagged.
To add a biller, copy a block and replay it against a real subject line.

## Notes / limits
- Homework is inferred from calendar event titles/descriptions matching `homework_pattern`, plus school-sender mail.
- Classification looks at subject + Gmail snippet; amounts/due dates for bills are read from the full body.
- Promotions/Social tabs and spam are excluded from "new mail".
