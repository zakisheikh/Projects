# daily-brief — infrastructure plan

Goal: a 7am + noon digest (calendar remainder, new/important mail, homework, health bills,
credit-card activity) that runs with no personal machine awake, uses deterministic code (no AI),
and tells me when it breaks.

## 1. Architecture

```
 GitHub Actions cron (UTC, 4 triggers/day)
        │  python -m brief
        ▼
 ┌─ slot gate ──────────────┐   not 7/12 local (DST twin) → exit 0
 │  pick_slot(now, [7,12])  │
 └────────────┬─────────────┘
              ▼
   Google REST (stdlib urllib, OAuth refresh token)
     ├─ Calendar  readonly  → events today + 7 days
     ├─ Gmail     readonly  → new mail since window start (+ full body for bills)
     └─ Gmail     send      → deliver brief to self
              ▼
   rules (config.toml regex) → categorize / extract $ and due date / homework flag
              ▼
   render text + HTML → email to self
```

Stateless by design: nothing is stored between runs, so there is no database to host or corrupt.

## 2. Hosting decision (researched)

| Option | Finding | Verdict |
|---|---|---|
| GitHub Actions `schedule` | Free for private repos within quota. Runs can start late under load ([docs](https://docs.github.com/en/enterprise-server@3.15/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows)). **Public repos have scheduled workflows auto-disabled after 60 days of no repo activity** ([ref](https://dev.to/gautamkrishnar/how-to-prevent-github-from-suspending-your-cronjob-based-triggers-knf)). | **Primary.** Use a *private* repo and the watchdog (§5). |
| Vercel Cron | Hobby: once/day max, fires anywhere in the scheduled hour ([docs](https://vercel.com/docs/cron-jobs/usage-and-pricing)); Pro gives per-minute precision. | Not on Hobby: two sends/day not allowed. Viable on Pro as an HTTP function. |
| Cloudflare Workers Cron / AWS EventBridge+Lambda | Precise and highly reliable, more setup. | **Fallback** if Actions proves flaky (§7). |

## 3. Auth & secrets
- Scopes: `calendar.readonly`, `gmail.readonly`, `gmail.send`. Nothing can modify or delete data.
- OAuth consent screen must be **In production**; Testing-mode refresh tokens die after 7 days
  ([ref](https://www.unipile.com/google-oauth-refresh-token/)). Gmail scopes are "restricted", so a
  personal-use unverified app shows a warning screen at consent but is fine for one user. Tokens issued
  *before* publishing keep the 7-day limit, so run `auth_setup.py` after publishing.
- A refresh token is also invalidated if unused for 6 months or if the Google password changes → covered by failure alerts.
- Secrets live only in GitHub Actions secrets (3 values). Rotate by re-running `auth_setup.py`.
- **Privacy:** dry-run output prints mail subjects into Actions logs → repo MUST be private, or dry-run must be removed from CI.

## 4. Scheduling & time
- Cron `5 11,12,16,17 * * *` = 7:05/12:05 America/New_York in both EDT and EST; the off-DST twin exits at the slot gate.
- 1-hour grace window absorbs GitHub queue delay; a run later than that is skipped rather than duplicated.
- Known gap: a skipped/lost run drops that window's mail. Fixed in Phase 1 (catch-up window).

## 5. Reliability & observability (Phase 1 work)
1. **Catch-up window (stateless):** window start = timestamp of the last brief sent (search Gmail for own `Morning/Midday brief` subject). Missed runs then roll into the next one; no database needed.
2. **Failure alerts:** a final `if: failure()` step emails/pushes "brief failed + run URL" (Actions also emails the repo owner on failed scheduled runs by default).
3. **Dead-man's switch:** a separate 9am-and-1pm check (a second tiny workflow, or a free healthchecks.io ping from the main job) alerts if no brief went out — this also catches the 60-day auto-disable and revoked tokens, which produce *no* run at all.
4. **Keepalive:** monthly commit-free keepalive via `workflow_dispatch` API call, or just keep the repo private/active.
5. **Tests in CI** gate every run (already: 4 unit tests with a fake Google client). Add fixture tests per rule category as real emails are tuned.

## 6. Data sources roadmap
| Phase | Add | How | Cost |
|---|---|---|---|
| 0 ✅ | Calendar, Gmail rules, homework-from-calendar, bills/EOB/card from email | built | free |
| 1 | Reliability items above; bill de-dup across days (don't repeat a bill already shown unless due date within 3 days); "bills due this week" rollup from a 14-day mail search | stdlib | free |
| 2 | Homework from the source: Canvas / Google Classroom feeds (Canvas calendar `.ics` URL; Classroom API `classroom.coursework.me.readonly`) | stdlib + iCal parser | free |
| 2 | Weather + commute-relevant alerts: National Weather Service API (no key) | stdlib | free |
| 3 | Bank/card balances, read-only: **SimpleFIN Bridge** — token-based, can't move money, ~daily refresh; published at $15/yr or ~$0.50/bank/mo, confirm on [their site](https://bridge.simplefin.org/simple). Plaid is the alternative but is developer/business-oriented. | one HTTPS GET w/ access URL secret | ~$15/yr |
| 3 | Delivery extras: push via ntfy.sh/Pushover for "needs attention" only, so the email can stay long and the phone buzz stays short | stdlib | free |
| 4 | Package tracking numbers from shipping emails; subscription renewal detection; calendar conflict detector | rules | free |

Decision for banks: skip until Phase 3. Card/bill emails already give amount, due date and fraud alerts. If added, store the
SimpleFIN access URL as a secret and treat it as read-only credentials (anyone holding it can read balances until revoked).

## 7. Risks & mitigations
| Risk | Mitigation |
|---|---|
| Actions delay/skip | grace window, catch-up window, dead-man's switch |
| Schedule auto-disabled (public, 60 days) | private repo + keepalive + dead-man's switch |
| Refresh token revoked/expired | failure alert with re-auth instructions |
| Regex misses/false positives | iterate `config.toml` against real mail; add a "Uncategorised from known senders" footer to spot gaps |
| Sensitive data in logs/emails | private repo, no body text in logs, brief only goes to self |
| Gmail snippet truncation | full-body fetch for bill categories only |
| Platform lock-in | all logic is plain Python with a thin Google client; the entry point is one command, so porting to Cloudflare/Lambda/cron on a $5 VPS is a one-file wrapper |

## 8. Build order
1. (now) merge MVP, set up OAuth + secrets, dry run, tune rules on real mail.
2. Phase 1 reliability (catch-up window, failure step, dead-man's switch).
3. Phase 2 sources (Canvas/Classroom, weather).
4. Phase 3 only if wanted (SimpleFIN, push notifications).

Estimated running cost: $0 (+ $15/yr if SimpleFIN is added).
