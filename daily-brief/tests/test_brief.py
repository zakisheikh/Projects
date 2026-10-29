import base64
import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

from brief import classify
from brief.main import assemble, collect_events, collect_mail, load_config, pick_slot, run, window_start

TZ = ZoneInfo("America/New_York")


def b64(s):
    return base64.urlsafe_b64encode(s.encode()).decode()


def msg(i, frm, subj, snip, labels=("INBOX", "UNREAD"), body=None, hour=9):
    payload = {"headers": [{"name": "From", "value": frm}, {"name": "Subject", "value": subj},
                           {"name": "Date", "value": f"Thu, 29 Oct 2026 {hour:02d}:00:00 -0400"}]}
    if body:
        payload.update(mimeType="text/plain", body={"data": b64(body)}, parts=[
            {"mimeType": "text/plain", "body": {"data": b64(body)}}])
    return {"id": i, "snippet": snip, "labelIds": list(labels), "payload": payload, "internalDate": "0"}


class FakeGoogle:
    sent = None
    MSGS = {m["id"]: m for m in [
        msg("1", "Anthem <no-reply@anthem.com>", "Explanation of Benefits ready", "Your EOB is available",
            body="Amount you owe: $182.40. Payment due Nov 2, 2026"),
        msg("2", "Chase <alerts@chase.com>", "Your statement is ready", "Statement ready",
            body="Minimum payment due $35.00 due 11/01/2026"),
        msg("3", "Chase <alerts@chase.com>", "Unusual activity on your card", "We noticed unusual activity"),
        msg("4", "Prof <prof@school.edu>", "Reminder", "see syllabus", labels=("INBOX", "UNREAD", "IMPORTANT")),
        msg("5", "Friend <f@x.com>", "lunch?", "hey", labels=("INBOX", "UNREAD", "IMPORTANT")),
    ]}

    def calendars(self):
        return [{"id": "primary", "summary": "Me"}, {"id": "h", "summary": "Birthdays"}]

    def events(self, cid, start, end):
        return [
            {"summary": "Standup", "start": {"dateTime": "2026-10-29T09:00:00-04:00"}, "end": {"dateTime": "2026-10-29T09:30:00-04:00"}},
            {"summary": "Dentist", "location": "Main St", "start": {"dateTime": "2026-10-29T15:00:00-04:00"}, "end": {"dateTime": "2026-10-29T16:00:00-04:00"}},
            {"summary": "Bio homework due", "start": {"date": "2026-10-30"}, "end": {"date": "2026-10-31"}},
            {"summary": "Essay due", "start": {"date": "2026-11-03"}, "end": {"date": "2026-11-04"}},
        ] if cid == "primary" else [{"summary": "Mom bday", "start": {"date": "2026-10-29"}, "end": {"date": "2026-10-30"}}]

    def search(self, q, limit=100):
        return list(self.MSGS)

    def message(self, mid, full=False):
        return self.MSGS[mid]

    def my_address(self):
        return "me@example.com"

    def send(self, to, subject, text, html):
        FakeGoogle.sent = (to, subject, text, html)


class Tests(unittest.TestCase):
    def test_slots(self):
        d = lambda h, m=0: datetime(2026, 10, 29, h, m, tzinfo=TZ)
        self.assertEqual(pick_slot(d(7, 20), [7, 12]), 7)
        self.assertEqual(pick_slot(d(12, 59), [7, 12]), 12)
        self.assertIsNone(pick_slot(d(10), [7, 12]))
        self.assertEqual(window_start(d(12), 12, [7, 12]).hour, 7)
        self.assertEqual(window_start(d(7), 7, [7, 12]).day, 28)

    def test_extract(self):
        t = date(2026, 10, 29)
        self.assertEqual(classify.extract_amount("Amount you owe: $1,182.40."), "$1,182.40")
        self.assertEqual(classify.extract_due("payment due Nov 2, 2026", t), date(2026, 11, 2))
        self.assertEqual(classify.extract_due("due 11/01/2026", t), date(2026, 11, 1))
        self.assertIsNone(classify.extract_due("nothing here", t))

    def test_end_to_end(self):
        now = datetime(2026, 10, 29, 12, 5, tzinfo=TZ)
        run(["--force"], google=FakeGoogle(), now=now)
        to, subject, text, html = FakeGoogle.sent
        self.assertEqual(to, "me@example.com")
        self.assertIn("Midday brief", subject)
        self.assertIn("Dentist @ Main St", text)
        self.assertNotIn("Standup", text)            # already over
        self.assertNotIn("Mom bday", text)           # excluded calendar
        self.assertIn("HOMEWORK", text)
        self.assertIn("$182.40", text)
        self.assertIn("BILL DUE", text)              # due within 3 days
        self.assertIn("ALERT", text)                 # unusual activity
        self.assertIn("lunch?", text)                # important, unread
        self.assertIn("<li>", html)

    def test_off_slot_noop(self):
        FakeGoogle.sent = None
        run([], google=FakeGoogle(), now=datetime(2026, 10, 29, 15, 0, tzinfo=TZ))
        self.assertIsNone(FakeGoogle.sent)


if __name__ == "__main__":
    unittest.main()
