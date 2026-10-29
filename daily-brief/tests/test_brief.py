import base64
import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

from brief import classify
from brief.main import pick_slot, run, window_start

TZ = ZoneInfo("America/New_York")
NOW = datetime(2026, 10, 29, 12, 5, tzinfo=TZ)


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
        return [{"id": "primary", "summary": "Me"}, {"id": "b", "summary": "Birthdays"}]

    def events(self, cid, start, end):
        if cid != "primary":
            return [{"summary": "Mom bday", "start": {"date": "2026-10-29"}, "end": {"date": "2026-10-30"}}]
        return [
            {"summary": "Standup", "start": {"dateTime": "2026-10-29T09:00:00-04:00"}, "end": {"dateTime": "2026-10-29T09:30:00-04:00"}},
            {"summary": "Dentist", "location": "Main St", "start": {"dateTime": "2026-10-29T15:00:00-04:00"}, "end": {"dateTime": "2026-10-29T16:00:00-04:00"}},
            {"summary": "Bio homework due", "start": {"date": "2026-10-30"}, "end": {"date": "2026-10-31"}},
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

    def run_text(self, google):
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            run(["--force", "--dry-run"], google=google, now=NOW)
        return buf.getvalue()

    def test_single_account(self):
        text = self.run_text(FakeGoogle(MAIN))
        self.assertIn("Dentist @ Main St", text)
        self.assertNotIn("Standup", text)                       # already over
        self.assertNotIn("Mom bday", text)                      # excluded calendar
        self.assertIn("HOMEWORK", text)
        self.assertIn("DUE  Chase", text)                       # unpaid, due in 3 days
        self.assertIn("$40.00", text)
        self.assertIn("autopay OFF", text)
        self.assertIn("ALERT  Chase: Unusual activity", text)
        self.assertIn("Rent", text)
        self.assertIn("$144.18", text)                          # Conservice total
        self.assertIn("Verizon", text)
        self.assertIn("$290.01", text)
        self.assertNotIn("reward you", text)                    # marketing dropped
        self.assertNotIn("missing out", text)
        self.assertNotIn("Get reimbursed", text)
        self.assertIn("Explanation of Benefits", text)
        self.assertIn("2 receipt(s)", text)
        self.assertIn("Chase: $3,628.15 (latest)", text)        # only newest balance
        self.assertNotIn("$2,900.26", text)
        self.assertIn("lunch?", text)

    def test_paid_settles_due(self):
        paid = msg("c9", "noreplyalerts@chase.com", "We've received your Sample Visa payment", day=28)
        text = self.run_text(FakeGoogle(MAIN + [paid]))
        self.assertNotIn("DUE  Chase", text)

    def test_multi_account_and_failure_isolation(self):
        import brief.main as bm
        cfg = bm.load_config()
        cfg["accounts"] = [{"name": "main", "token_env": "X", "send_from": True}, {"name": "other", "token_env": "Y"}]
        import tempfile, os, tomllib  # write tmp config
        # emulate via direct build: accounts dict of fakes
        g = {"main": FakeGoogle(MAIN), "other": FakeGoogle(OTHER)}
        orig = bm.load_config
        bm.load_config = lambda path=None: cfg
        try:
            text = self.run_text(g)
            self.assertIn("[other]", text)
            self.assertIn("OVERDUE", text.upper())
            self.assertEqual(text.count("Dentist"), 1)          # same calendar in two logins -> once
            g2 = {"main": FakeGoogle(MAIN), "other": None}
            text = self.run_text(g2)
            self.assertIn("ACCOUNT  other", text)
            self.assertIn("Dentist", text)                      # healthy account still reported
        finally:
            bm.load_config = orig

    def test_off_slot_noop(self):
        FakeGoogle.sent = None
        run([], google=FakeGoogle(MAIN), now=datetime(2026, 10, 29, 15, 0, tzinfo=TZ))
        self.assertIsNone(FakeGoogle.sent)


if __name__ == "__main__":
    unittest.main()
