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

## What it reads (all read-only except sending the brief to yourself)

Scopes: `calendar.readonly`, `gmail.readonly`, `gmail.send`. It never modifies or deletes anything.

### Money without connecting banks
- **Credit cards / bills / health**: parsed from the statement and alert emails you already get
  (amount due, due date, fraud/unusual-activity alerts, EOBs). No bank login needed. Tune the senders/keywords in `config.toml`.
- If you later want balances/transactions: **Plaid** (read-only, but business-oriented onboarding), or
  **SimpleFIN Bridge** (~$15/yr, read-only token, individuals welcome) are the realistic options. Not included — email covers bills and alerts, which is what a briefing needs.

## Setup (~10 min, one time)

1. Google Cloud Console → new project → enable **Gmail API** and **Google Calendar API**.
2. OAuth consent screen: External, add yourself as a test user; then **publish to "In production"**
   (test-mode refresh tokens expire after 7 days). Personal use with unverified-app warning is fine.
3. Credentials → OAuth client ID → **Desktop app**. Copy the client ID/secret.
4. Locally: `GOOGLE_CLIENT_ID=… GOOGLE_CLIENT_SECRET=… python3 auth_setup.py` → copy the refresh token.
5. Repo → Settings → Secrets → Actions: add `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`.
6. Edit `config.toml` (timezone, slots, homework words, senders). Merge to the default branch (schedules only run there).
7. Actions → daily-brief → **Run workflow** with dry run on, check the log, then off to receive a real email.

## Run locally
```
export GOOGLE_CLIENT_ID=… GOOGLE_CLIENT_SECRET=… GOOGLE_REFRESH_TOKEN=…
python3 -m brief --force --dry-run
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
