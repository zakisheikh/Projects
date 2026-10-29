import base64
import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

from brief import classify
from brief.main import pick_slot, run, window_start

TZ = ZoneInfo("America/Los_Angeles")
NOW = datetime(2026, 10, 29, 12, 17, tzinfo=TZ)


def b64(s):
    return base64.urlsafe_b64encode(s.encode()).decode()


def msg(i, frm, subj, snip="", labels=("INBOX", "UNREAD"), body=None, day=29, hour=9):
    payload = {"headers": [{"name": "From", "value": frm}, {"name": "Subject", "value": subj},
                           {"name": "Date", "value": f"Thu, {day} Oct 2026 {hour:02d}:00:00 -0400"}]}
    if body:
        payload.update(mimeType="text/plain", body={"data": b64(body)},
                       parts=[{"mimeType": "text/plain", "body": {"data": b64(body)}}])
    return {"id": i, "snippet": snip, "labelIds": list(labels), "payload": payload, "internalDate": "0"}


# Templates modelled on real notices (amounts/accounts invented).
MAIN = [
    msg("c1", "no.reply.alerts@chase.com", "Your Sample Visa payment is due on Nov 1, 2026",
        body="Autopay Off\n| Due date | Nov 1, 2026 |\n| Minimum payment due | $40.00 |\n| Statement balance | $640.59 |", day=20),
    msg("c2", "noreplyalerts@chase.com", "Your Sample Visa balance is $3,628.15", day=28),
    msg("c3", "noreplyalerts@chase.com", "Your Sample Visa balance is $2,900.26", day=27),
    msg("c4", "noreplyalerts@chase.com", "Unusual activity on your card"),
    msg("c5", "chase@mcmap.chase.com", "We want to reward you with an up to $900 offer"),
    msg("r1", "no-reply@essex.com", "Your Rent Payment is Due Soon",
        body="this is a friendly reminder that your rent is due today, October 30th.", day=29),
    msg("u1", "ebill@conservicemail.com", "Monthly Conservice Statement for Sample Apartments",
        body="Your utility statement due on 11/1/2026 is ready.\n| Total Current Charges | | $144.18 |", day=16),
    msg("v1", "VZWMail@ecrmemail.verizonwireless.com", "Thanks! We received your payment.",
        body="Payment amount:\n$290.01"),
    msg("v2", "no-reply@customer.verizon.com", "Psst, you're missing out on some real savings."),
    msg("h1", "communications@em.aetna.com", "IT'S HERE: Your Explanation of Benefits", body="Your EOB is ready."),
    msg("h2", "communications@em.aetna.com", "Get reimbursed for your medical claims faster"),
    msg("x1", "invoice@mail.anthropic.com", "Your receipt from Anthropic, PBC #1"),
    msg("x2", "receipts@united.com", "eTicket Itinerary and Receipt for Confirmation ABC"),
    msg("p1", "Prof <prof@school.edu>", "Reminder", labels=("INBOX", "UNREAD", "IMPORTANT")),
    msg("p2", "Friend <f@x.com>", "lunch?", labels=("INBOX", "UNREAD", "IMPORTANT")),
]
OTHER = [msg("o1", "camp@gmail.com", "Reminder: 2026 Invoice - PAYMENT IS NOW OVERDUE", body="Total Registration Cost: $460")]


class FakeGoogle:
    sent = None

    def __init__(self, msgs, cal="primary"):
        self.msgs = {m["id"]: m for m in msgs}
        self.cal = cal

    def calendars(self):
        return [{"id": "primary", "summary": "Me"}, {"id": "canvas", "summary": "Zaki Sheikh Calendar (Canvas)"},
                {"id": "pray", "summary": "Prayer Times"}, {"id": "moon", "summary": "Phases of the Moon"}]

    def events(self, cid, start, end):
        canvas = [
            {"summary": "Final Project: Proposal [CS549-09-Fall2026]", "start": {"date": "2026-10-30T00:00:00Z"},
             "end": {"date": "2026-10-31T00:00:00Z"},
             "description": "Please vote by [Friday, October 30 at 7:00 PM]."},
            {"summary": "Week 10-Old Faithful Again [2267_MESA_EXSC 126B_42431]", "start": {"date": "2026-10-31"},
             "end": {"date": "2026-11-01"}},
            {"summary": "Quick Poll - Nov. 24 Class [CS549-09-Fall2026]", "start": {"date": "2026-10-30"},
             "end": {"date": "2026-10-31"}, "description": "Please submit your preference by [Friday, October 30 at 7:00 PM]."},
            {"summary": "Essay 2 [FA26: CS-157B Sec 01 - Data BS Man Sys II]", "start": {"date": "2026-11-03"},
             "end": {"date": "2026-11-04"}},
        ]
        if cid == "canvas":
            return canvas
        if cid == "pray":
            return [{"summary": "Fajr", "start": {"dateTime": "2026-10-29T05:50:00-07:00"}, "end": {"dateTime": "2026-10-29T06:10:00-07:00"}},
                    {"summary": "Zuhr", "start": {"dateTime": "2026-10-29T12:32:00-07:00"}, "end": {"dateTime": "2026-10-29T12:52:00-07:00"}},
                    {"summary": "Maghrib", "start": {"dateTime": "2026-10-29T18:16:00-07:00"}, "end": {"dateTime": "2026-10-29T18:36:00-07:00"}}]
        if cid == "moon":
            return [{"summary": "Full moon", "start": {"date": "2026-10-29"}, "end": {"date": "2026-10-30"}}]
        return [
            {"summary": "Standup", "start": {"dateTime": "2026-10-29T09:00:00-07:00"}, "end": {"dateTime": "2026-10-29T09:30:00-07:00"}},
            {"summary": "Dentist", "location": "Main St, San Diego", "start": {"dateTime": "2026-10-29T15:00:00-07:00"}, "end": {"dateTime": "2026-10-29T16:00:00-07:00"}},
            canvas[0],     # Canvas copy that also lives in the primary calendar
        ]

    def search(self, q, limit=100):
        return list(self.msgs)

    def message(self, mid, full=False):
        return self.msgs[mid]

    def my_address(self):
        return "me@example.com"

    def send(self, to, subject, text, html):
        FakeGoogle.sent = (to, subject, text, html)


def brief(google, config=None):
    FakeGoogle.sent = None
    run(["--force", "--dry-run"] + (["--config", config] if config else []), google=google, now=NOW)


class Tests(unittest.TestCase):
    def setUp(self):
        # Pin tests to one account regardless of how many logins config.toml lists.
        import brief.main as bm
        self._orig_cfg = bm.load_config
        real = self._orig_cfg

        def one_account(path=None):
            cfg = real(path)
            cfg["accounts"] = [{"name": "main", "token_env": "X", "send_from": True}]
            return cfg
        bm.load_config = one_account

    def tearDown(self):
        import brief.main as bm
        bm.load_config = self._orig_cfg

    def run_out(self, google, now=NOW, extra=()):
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            run(["--force", "--dry-run", *extra], google=google, now=now)
        return buf.getvalue()

    def run_text(self, google, now=NOW):
        return self.run_out(google, now).split("--- telegram preview ---")[0]

    def test_slots(self):
        d = lambda h, m=0: datetime(2026, 10, 29, h, m, tzinfo=TZ)
        self.assertEqual(pick_slot(d(7, 20), [7, 12]), 7)
        self.assertIsNone(pick_slot(d(8, 5), [7, 12]))       # DST twin run is skipped
        self.assertEqual(window_start(d(12), 12, [7, 12]).hour, 7)

    def test_extract(self):
        ref = date(2026, 10, 29)
        self.assertEqual(classify.extract_amount("Amount you owe: $1,182.40."), "$1,182.40")
        self.assertEqual(classify.extract_amount("| Minimum payment due | $40.00 |\n| Statement balance | $640.59 |"), "$40.00")
        self.assertEqual(classify.extract_due("| Due date | Oct 20, 2026 |", ref), date(2026, 10, 20))
        self.assertEqual(classify.extract_due("statement due on 11/1/2026", ref), date(2026, 11, 1))
        self.assertEqual(classify.extract_due("your rent is due today, October 30th.", ref), date(2026, 10, 30))
        self.assertEqual(classify.extract_due("payment is due tomorrow", ref), date(2026, 10, 30))
        self.assertEqual(classify.extract_due("due Jan 5", date(2026, 12, 20)), date(2027, 1, 5))
        self.assertIsNone(classify.extract_due("nothing", ref))
        self.assertEqual(classify.extract_autopay("Autopay Off"), "autopay OFF")
        self.assertEqual(classify.extract_autopay("Bill Due - NON auto pay"), "autopay OFF")

    def test_full_email_version(self):
        text = self.run_text(FakeGoogle(MAIN))
        for must in ("Dentist at 3 PM", "Zuhr at 12:32 PM", "for ML", "7:00 PM", "Databases", "Quick Poll", "$40.00", "autopay",
                     "Unusual activity on your card", "$144.18", "Verizon", "$290.01", "Explanation of Benefits",
                     "2 receipts", "$3,628.15", "lunch?", "Rent"):
            self.assertIn(must, text, must)
        for mustnt in ("Standup", "Full moon", "Fajr", "reward you", "missing out", "Get reimbursed", "$2,900.26"):
            self.assertNotIn(mustnt, text, mustnt)
        self.assertEqual(text.count("Final Project: Proposal"), 1)       # Canvas copy in two calendars -> once
        for heading in ("PRIORITY ITEMS", "REMAINING SCHEDULE", "NEEDS ATTENTION", "HEALTH & MEDICAL"):
            self.assertNotIn(heading, text.upper())                      # spoken prose, not a form

    def test_telegram_version_is_short(self):
        out = self.run_out(FakeGoogle(MAIN))
        tg = out.split("--- telegram preview ---")[1].strip()
        self.assertLess(len(tg), 1400)
        self.assertLessEqual(len(tg.split("\n\n")), 8)
        self.assertIn("medical item", tg)               # health folded into one line
        for hidden in ("Aetna", "Zuhr", "Explanation"):
            self.assertNotIn(hidden, tg)
        self.assertIn("email", tg.lower())               # points to the full version

    def test_muted_senders_and_bills_are_one_followup_line(self):
        noisy = [msg("t1", "TurboTax@em1.turbotax.intuit.com", "Final Notice: Your tax filing status"),
                 msg("t2", "notifications@chargepoint.com", "Quick payment update required before your next charge")]
        out = self.run_out(FakeGoogle(MAIN + noisy))
        email, tg = out.split("--- telegram preview ---")
        for gone in ("Final Notice", "tax filing", "payment update"):
            self.assertNotIn(gone, out)
        self.assertIn("Chase ($40.00", email)                  # email: who, amount and due date
        self.assertIn("Conservice", email)
        self.assertIn("Chase", tg)                             # Telegram: just who to follow up with
        self.assertIn("Conservice", tg)
        self.assertNotIn("$40.00", tg)

    def test_morning_covers_until_noon_and_noon_covers_the_rest(self):
        morning = self.run_text(FakeGoogle(MAIN), now=datetime(2026, 10, 29, 7, 17, tzinfo=TZ))
        noon = self.run_text(FakeGoogle(MAIN), now=NOW)
        self.assertIn("Standup", morning)              # 9am is before the noon check
        self.assertNotIn("Dentist", morning)           # 3pm belongs to the noon brief
        self.assertIn("Dentist", noon)
        self.assertNotIn("Standup", noon)
        for text in (morning, noon):                   # homework for the week appears in both
            self.assertIn("Essay 2 for Databases (Tuesday)", text)
            self.assertIn("Final Project: Proposal for ML (tomorrow", text)

    def test_paid_settles_due(self):
        paid = msg("c9", "noreplyalerts@chase.com", "We've received your Sample Visa payment", day=28)
        self.assertNotIn("$40.00", self.run_text(FakeGoogle(MAIN + [paid])))

    def test_stale_due_is_dropped_and_bare_sender_named(self):
        old = msg("r0", "no-reply@essex.com", "Your Rent Payment is Due Soon", day=1, body="your rent is due today, October 1st.")
        text = self.run_text(FakeGoogle(MAIN + [old]))
        for phrase in ("was due", "past due", "Overdue"):
            self.assertNotIn(phrase, text)
        from brief.models import Mail
        from brief.render import sender_name
        self.assertEqual(sender_name(Mail("x", "TurboTax@em1.turbotax.intuit.com", "s", "", NOW)), "intuit.com")
        self.assertEqual(sender_name(Mail("x", "Prof <p@school.edu>", "s", "", NOW)), "Prof")

    def test_multi_account_and_failure_isolation(self):
        import brief.main as bm
        cfg = bm.load_config()
        cfg["accounts"] = [{"name": "main", "token_env": "X", "send_from": True}, {"name": "other", "token_env": "Y"}]
        bm.load_config = lambda path=None: cfg
        text = self.run_text({"main": FakeGoogle(MAIN), "other": FakeGoogle(OTHER)})
        self.assertIn("OVERDUE", text.upper())
        self.assertEqual(text.count("Dentist"), 1)               # same calendar in two logins -> once
        text = self.run_text({"main": FakeGoogle(MAIN), "other": None})
        self.assertIn("other account", text)
        self.assertIn("Dentist", text)                           # healthy account still reported

    def test_voice_varies_and_never_repeats(self):
        from brief.voice import Voice
        last, seen = {}, []
        for day in range(30):
            v = Voice.load("Bruno", "Zaki", f"2026-10-{day}-7", last)
            seen.append(v.say("greet_morning"))
            if day:
                self.assertNotEqual(seen[-1], seen[-2])
            last.update(v.used)
        self.assertGreater(len(set(seen)), 6)
        self.assertTrue(all(x[0].isupper() for x in seen))

    def test_a_month_of_briefs_never_repeat_back_to_back(self):
        prev = None
        last = {}
        for day in range(1, 29):
            import brief.main as bm
            from brief.voice import Voice
            from brief.narrate import Narrator
            v = Voice.load("Bruno", "Zaki", f"2026-11-{day:02d}-7", last)
            b = bm.assemble([], [], [], [], datetime(2026, 11, day, 7, 17, tzinfo=TZ), 7, bm.load_config())
            out = Narrator(v, {}, date(2026, 11, day)).paragraphs(b, 7, datetime(2026, 11, day, 7, 17, tzinfo=TZ))
            last.update(v.used)
            if prev:
                self.assertNotEqual(out[0], prev[0])             # greeting differs from yesterday's
                self.assertNotEqual(out[-1], prev[-1])           # so does the sign-off
            prev = out

    def test_state_and_delivery(self):
        import json, os, tempfile
        import brief.main as bm
        import brief.telegram as tgm
        sent = []
        orig_send, orig_load = tgm.send, bm.load_config
        tgm.send = lambda tok, chat, html: sent.append(html)
        cfg = orig_load()
        cfg["delivery"]["channels"] = ["telegram", "email"]
        bm.load_config = lambda path=None: cfg
        os.environ.update(TELEGRAM_BOT_TOKEN="t", TELEGRAM_CHAT_ID="1")
        path = os.path.join(tempfile.mkdtemp(), "state.json")
        try:
            g = FakeGoogle(MAIN)
            FakeGoogle.sent = None
            self.assertEqual(run(["--force", "--state", path], google=g, now=NOW), 0)
            self.assertTrue(sent and FakeGoogle.sent)
            self.assertNotIn("Aetna", sent[0])                          # health stays off Telegram
            self.assertIn("Aetna", FakeGoogle.sent[2])                  # but present in the email
            with open(path) as f:
                st = json.load(f)
            self.assertIn("last_sent", st)
            self.assertTrue(st["seen"] and st["phrases"])
            self.assertIn("started 17m after slot", st["history"][-1])
            sent.clear()
            run(["--force", "--state", path], google=g, now=NOW.replace(minute=40))
            self.assertNotIn("lunch?", FakeGoogle.sent[2])              # already reported, not repeated

            def boom(*a):
                raise RuntimeError("down")
            tgm.send = boom
            FakeGoogle.sent = None
            self.assertEqual(run(["--force"], google=g, now=NOW), 0)
            self.assertIn("telegram: down", FakeGoogle.sent[2])         # one channel failing must not block the other
        finally:
            tgm.send, bm.load_config = orig_send, orig_load

    def test_explain_shows_where_every_input_went(self):
        out = self.run_out(FakeGoogle(MAIN), extra=["--explain"])
        for token in ("where every input went", "dropped by rule: Chase offers", "[matched: Chase/due]", "Prayer times"):
            self.assertIn(token, out)

    def test_telegram_chunking_and_escape(self):
        from brief import telegram as tgm
        self.assertIn("a &lt; b", tgm.fmt(["hi <b>", "a < b"]))
        parts = tgm.chunks("\n\n".join(["x" * 1000] * 10))
        self.assertTrue(all(len(p) <= 3900 for p in parts) and len(parts) > 1)

    def test_off_slot_noop(self):
        FakeGoogle.sent = None
        run([], google=FakeGoogle(MAIN), now=datetime(2026, 10, 29, 15, 0, tzinfo=TZ))
        self.assertIsNone(FakeGoogle.sent)


if __name__ == "__main__":
    unittest.main()
