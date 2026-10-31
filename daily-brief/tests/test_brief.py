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
    msg("a1", "noreply@creators.spotify.com", "[Action needed] Update your login by December 7th", "Update your login by December 7th."),
    msg("e1", "miramonte@essex.com", "Your Document is Ready to Sign - Unit G201"),
    msg("m1", "Fidelity.Investments.email@shareholderdocs.fidelity.com", "Vote now! MICROSOFT Annual Meeting"),
    msg("m2", "return@amazon.com", "Return request confirmed for 2Pcs Disposable Oil Splash Guard"),
    msg("h3", "reservations@emails.hertz.com", "Zaki, thanks for booking!"),
    msg("h4", "mychart@sdhealth.org", "Your lab results are available"),
    msg("i1", "syed@alkisafoundation.org", "Invitation from an unknown sender: Quick Sync @ Tue Oct 27, 2026"),
    msg("d1", "drive-shares-dm-noreply@google.com", 'Spreadsheet shared with you: "Zaki Workout Plan"'),
    msg("s2", "customerservice@servicing.synchrony.com", "You Scheduled a Payment."),
    msg("u2", "notifications@united.com", "What to know about your trip to San Diego"),
    msg("hz2", "hertznoreply@rentals.hertz.com", "Hertz Rental Agreement"),
    msg("st1", "fairwinds@member.fairwinds.org", "Your FAIRWINDS Credit Card statement is ready."),
    msg("fr", "Mom <mom@gmail.com>", "dinner sunday?"),
    msg("sub", "billing@streamco.com", "Your subscription renews on November 5"),
    msg("px", "billing@streamco.com", "Notice: price increase for your plan"),
]
OTHER = [msg("o1", "camp@gmail.com", "Reminder: 2026 Invoice - PAYMENT IS NOW OVERDUE", body="Total Registration Cost: $460")]


class FakeGoogle:
    sent = None

    def __init__(self, msgs, cal="primary"):
        self.msgs = {m["id"]: m for m in msgs}
        self.cal = cal

    def calendars(self):
        return [{"id": "primary", "summary": "Me"}, {"id": "canvas", "summary": "Zaki Sheikh Calendar (Canvas)"},
                {"id": "pray", "summary": "Prayer Times"}, {"id": "moon", "summary": "Phases of the Moon"},
                {"id": "zah", "summary": "Zaheer Calendar"}]

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
            {"summary": "Midterm Exam [CS549-09-Fall2026]", "start": {"date": "2026-11-02"}, "end": {"date": "2026-11-03"}},
            {"summary": "Spring 2027 Enrollment Appointment Viewable [College of Science]",
             "start": {"dateTime": "2026-10-30T08:00:00-07:00"}, "end": {"dateTime": "2026-10-30T08:30:00-07:00"}},
        ]
        if cid == "canvas":
            return canvas
        if cid == "pray":
            return [{"summary": "Fajr", "start": {"dateTime": "2026-10-29T05:50:00-07:00"}, "end": {"dateTime": "2026-10-29T06:10:00-07:00"}},
                    {"summary": "Zuhr", "start": {"dateTime": "2026-10-29T12:32:00-07:00"}, "end": {"dateTime": "2026-10-29T12:52:00-07:00"}},
                    {"summary": "Maghrib", "start": {"dateTime": "2026-10-29T18:16:00-07:00"}, "end": {"dateTime": "2026-10-29T18:36:00-07:00"}}]
        if cid == "zah":
            return [{"summary": "Tri valley ortho PT", "start": {"dateTime": "2026-10-29T16:00:00-07:00"}, "end": {"dateTime": "2026-10-29T17:00:00-07:00"}}]
        if cid == "moon":
            return [{"summary": "Full moon", "start": {"date": "2026-10-29"}, "end": {"date": "2026-10-30"}}]
        return [
            {"summary": "Standup", "start": {"dateTime": "2026-10-29T09:00:00-07:00"}, "end": {"dateTime": "2026-10-29T09:30:00-07:00"}},
            {"summary": "Dentist", "location": "Main St, San Diego", "start": {"dateTime": "2026-10-29T15:00:00-07:00"}, "end": {"dateTime": "2026-10-29T16:00:00-07:00"}},
            canvas[0],     # Canvas copy that also lives in the primary calendar
            {"summary": "Kazim bday party", "creator": {"email": "narjisirfan@gmail.com"},
             "start": {"dateTime": "2026-10-29T15:30:00-07:00"}, "end": {"dateTime": "2026-10-29T17:00:00-07:00"}},
        ]

    def search(self, q, limit=100):
        return list(self.msgs)

    def message(self, mid, full=False):
        return self.msgs[mid]

    def my_address(self):
        return "me@example.com"

    def send(self, to, subject, text, html):
        FakeGoogle.sent = (to, subject, text, html)


def Narr(bundle, slot, now):
    from brief.narrate import Narrator
    from brief.voice import Voice
    v = Voice.load("Bruno", "Zaki", "t", {})
    return "\n".join(Narrator(v, {}, now.date()).paragraphs(bundle, slot, now))


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
        import brief.telegram as tgm               # never touch the real Telegram API from tests
        self._orig_updates = tgm.updates
        tgm.updates = lambda token, offset=None: []

    def tearDown(self):
        import os
        import brief.main as bm
        import brief.telegram as tgm
        bm.load_config = self._orig_cfg
        tgm.updates = self._orig_updates
        for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
            os.environ.pop(k, None)

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
        self.assertEqual(classify.extract_due("Your payment due date is Dec 20, 2026.", ref), date(2026, 12, 20))
        self.assertIsNone(classify.extract_due("nothing", ref))
        self.assertEqual(classify.extract_autopay("Autopay Off"), "autopay OFF")
        self.assertEqual(classify.extract_autopay("Bill Due - NON auto pay"), "autopay OFF")

    def test_full_email_version(self):
        text = self.run_text(FakeGoogle(MAIN))
        for must in ("3:00pm · Dentist", "(ML)", "7:00 PM", "Databases", "Quick Poll", "$40.00", "autopay",
                     "Unusual activity on your card", "$144.18", "Verizon", "$290.01", "lab results",
                     "lunch?", "Rent", "United", "Hertz", "spotify.com", "Essex"):
            self.assertIn(must, text, must)
        for mustnt in ("Standup", "Full moon", "Fajr", "Zuhr", "Tri valley", "reward you", "missing out", "Get reimbursed", "$2,900.26",
                       "$3,628.15", "Fidelity", "Amazon", "Enrollment", "receipts", "Explanation of Benefits",
                       "Scheduled a Payment", "What to know about your trip", "Rental Agreement", "FAIRWINDS", "Zaki Workout Plan"):
            self.assertNotIn(mustnt, text, mustnt)
        self.assertEqual(text.count("Final Project: Proposal"), 1)       # Canvas copy in two calendars -> once
        for heading in ("PRIORITY ITEMS", "REMAINING SCHEDULE", "NEEDS ATTENTION", "HEALTH & MEDICAL"):
            self.assertNotIn(heading, text.upper())                      # spoken prose, not a form

    def test_telegram_version_is_short(self):
        out = self.run_out(FakeGoogle(MAIN))
        tg = out.split("--- telegram preview ---")[1].strip()
        self.assertLess(len(tg), 1400)
        self.assertLessEqual(len(tg.split("\n\n")), 8)
        for hidden in ("lab results", "United", "Hertz", "lunch?", "spotify.com", "Verizon", "Mom", "renews"):
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
            self.assertIn("Tue 11/3 · Essay 2 (Databases)", text)
            self.assertIn("Fri 10/30 · Final Project: Proposal (ML)", text)

    def test_bills_only_when_due_within_two_weeks(self):
        far = msg("s1", "customerservice@servicing.synchrony.com", "Don't forget, your Visa payment is due soon",
                  body="Your payment due date is Dec 20, 2026. Minimum payment due $25.00")
        nodue = msg("f1", "fairwinds@member.fairwinds.org", "Your FAIRWINDS Credit Card statement is ready.")
        out = self.run_out(FakeGoogle(MAIN + [far, nodue]))
        email, tg = out.split("--- telegram preview ---")
        self.assertNotIn("Synchrony", out)                    # due in 7 weeks: not mentioned yet
        self.assertIn("Chase", tg)                            # due in 3 days: mentioned
        self.assertNotIn("Fairwinds", out)                    # "statement ready" notices were switched off

    def test_calendar_choices(self):
        out = self.run_out(FakeGoogle(MAIN))
        email, tg = out.split("--- telegram preview ---")
        self.assertIn("Kazim bday party (Narjis)", email)                    # partner's events are tagged
        self.assertRegex(email, r"overlaps|collision|two places|clash")      # Dentist 3:00-4:00 vs party 3:30-5:00
        for gone in ("Tri valley", "Fajr", "Enrollment"):                    # Zaheer / Prayer calendars and enrollment notices are dropped
            self.assertNotIn(gone, out)
        self.assertIn("Mon 11/2 · Midterm Exam (ML)", email)                 # exams are their own list...
        self.assertIn("Midterm Exam", tg)                                    # ...and Telegram shows them too

    def test_mail_choices(self):
        out = self.run_out(FakeGoogle(MAIN))
        email, tg = out.split("--- telegram preview ---")
        for muted in ("Fidelity", "Amazon", "$3,628.15", "Final Notice"):
            self.assertNotIn(muted, out)
        self.assertIn("spotify.com: [Action needed] Update your login by December 7th (by Mon 12/7)", email)
        self.assertIn("Rent (Essex): Your Document is Ready to Sign", email)         # housing notice -> life admin
        self.assertIn("Hertz: Zaki, thanks for booking!", email)              # rental cars -> travel
        for emailonly in ("spotify.com", "Document is Ready", "Hertz", "Verizon"):
            self.assertNotIn(emailonly, tg)

    def test_html_email_is_designed_and_safe(self):
        import brief.main as bm
        FakeGoogle.sent = None
        run(["--force"], google=FakeGoogle(MAIN + [msg("x9", "Evil <b>Co</b> <evil@x.com>", "<script>alert(1)</script> Final Notice invoice")]), now=NOW)
        html = FakeGoogle.sent[3]
        self.assertIn("prefers-color-scheme: dark", html)                    # dark mode
        self.assertIn('name="viewport"', html)                               # phone friendly
        self.assertNotIn("no AI", html)                                      # you asked not to see that line
        self.assertNotIn("no AI", FakeGoogle.sent[2])
        self.assertIn("role=\"presentation\"", html)                         # table layout for old clients
        for need in ("Thursday", "October 29", "Dentist", "$144.18", "Conservice utilities", "Exam"):
            self.assertIn(need, html)
        self.assertNotIn("<script>", html)                                   # mail text is escaped, never injected
        self.assertNotIn("http://", html.replace("https://mail.google.com", ""))   # no remote resources
        self.assertNotIn("<img", html)                                       # nothing to block or track
        self.assertIn("https://mail.google.com/mail/", html)                 # mail rows link to the message
        self.assertIn(">Gmail</a>", html)                                    # quick-link buttons
        self.assertIn("max-width: 640px", html)                              # phone layout
        self.assertIn("Please vote by", html)                                # description snippet under coursework

    def test_mail_depth_choices(self):
        email = self.run_text(FakeGoogle(MAIN))
        self.assertIn("Mom: dinner sunday?", email)                       # people
        self.assertIn("Prof: Reminder", email)                            # school sender
        self.assertIn("Invitation from an unknown sender", email)         # invites
        self.assertIn("streamco.com: Your subscription renews", email)    # subscriptions
        self.assertIn("price increase", email)
        self.assertIn("United: eTicket Itinerary", email)                 # itineraries stay
        self.assertIn("Hertz: Zaki, thanks for booking!", email)          # bookings stay
        self.assertIn("lab results", email)                               # medical results stay

    def test_calendar_depth_choices(self):
        import brief.main as bm
        from brief.models import Event
        cfg = bm.load_config()
        PT_ = TZ
        D = lambda y, m, d, h=0, mi=0: datetime(y, m, d, h, mi, tzinfo=PT_)
        trip = Event("Trip", D(2026, 10, 27), D(2026, 10, 31), True, "Main")                      # Oct 27-30 inclusive
        early = Event("Dentist", D(2026, 10, 30, 6, 30), D(2026, 10, 30, 7, 30), False, "Main")
        trash = Event("Recycling Trash Night", D(2026, 10, 29, 20), D(2026, 10, 29, 21), False, "Main")
        exam = Event("Final Exam [CS549-09-Fall2026]", D(2026, 11, 20), D(2026, 11, 21), True, "Canvas", homework=True, exam=True)
        far_hw = Event("Essay 9 [CS549-09-Fall2026]", D(2026, 11, 13), D(2026, 11, 14), True, "Canvas", homework=True)
        for day, shows in ((27, True), (28, False), (29, False), (30, True)):
            now = D(2026, 10, day, 7, 17)
            b = bm.assemble([trip], [], [], [], now, 7, cfg)
            self.assertEqual(bool(b.today), shows, day)                                          # first and last day only
        b = bm.assemble([trip], [], [], [], D(2026, 10, 30, 7, 17), 7, cfg)
        self.assertIn("ends today", Narr(b, 7, D(2026, 10, 30, 7, 17)))
        b = bm.assemble([early, trash], [], [], [], D(2026, 10, 29, 12, 17), 12, cfg)
        self.assertEqual([e.title for e in b.early], ["Dentist"])                               # early-start warning at midday
        self.assertIn("6:30 AM", Narr(b, 12, D(2026, 10, 29, 12, 17)))
        b = bm.assemble([early], [], [], [], D(2026, 10, 29, 7, 17), 7, cfg)
        self.assertEqual(b.early, [])                                                            # only the last brief looks at tomorrow
        b = bm.assemble([exam, far_hw], [], [], [], D(2026, 10, 29, 7, 17), 7, cfg)
        self.assertEqual([e.title for e in b.exams], [e.title for e in [exam]])                  # exams: 30 days
        self.assertEqual(b.hw_week, [])                                                          # ordinary coursework: 7 days

    def test_trash_night_is_skipped_at_the_source(self):
        class G(FakeGoogle):
            def events(self, cid, start, end):
                return [{"summary": "Recycling Trash Night", "start": {"dateTime": "2026-10-29T20:00:00-07:00"}, "end": {"dateTime": "2026-10-29T21:00:00-07:00"}}] if cid == "primary" else []
        self.assertNotIn("Recycling", self.run_text(G(MAIN)))

    def test_description_summary(self):
        from brief.parse import summarize
        desc = ("*****\nFinal Project Proposal Report\n*****\nPlease review the [Final Project GitHub repository] (https://github.com/x/y) "
                "for the description.\nSubmit by [Friday, October 30 at 7:00 PM].")
        out = summarize(desc, "Final Project: Proposal")
        self.assertTrue(out.startswith("Please review the Final Project GitHub repository for the description."), out)
        self.assertNotIn("[", out)
        self.assertNotIn("https://", out)

    def test_game_scoring_levels_and_streaks(self):
        from brief import game
        hw = {"kind": "hw", "title": "Essay 2", "due": "2026-11-03"}
        self.assertEqual(game.xp_for(hw, date(2026, 10, 29)), 40)          # 20 + 20 for finishing 3+ days early
        self.assertEqual(game.xp_for(hw, date(2026, 11, 2)), 30)           # 20 + 10 for a day early
        self.assertEqual(game.xp_for(hw, date(2026, 11, 3)), 20)           # on the day
        self.assertEqual(game.xp_for(hw, date(2026, 11, 5)), 10)           # late: half
        self.assertEqual(game.xp_for({"kind": "exam", "title": "Midterm", "due": "2026-11-02"}, date(2026, 11, 2)), 40)
        self.assertEqual(game.xp_for({"kind": "hw", "title": "Final Project: Proposal", "due": "2026-10-30"}, date(2026, 10, 30)), 30)
        self.assertEqual(game.xp_for({"kind": "bill", "title": "Rent", "due": "2026-11-01"}, date(2026, 10, 31)), 20)
        self.assertEqual([game.level_for(x) for x in (0, 100, 250, 450)], [1, 2, 3, 4])
        self.assertEqual(game.level_name(4), "Mark IV")

        g = {}
        t1 = {"id": "a" * 10, "kind": "hw", "title": "Essay 2", "due": "2026-11-03"}
        D = lambda d, h=7: datetime(2026, 10, d, h, 17, tzinfo=TZ) if d <= 31 else datetime(2026, 11, d - 31, h, 17, tzinfo=TZ)
        r = game.play(g, [t1], [], set(), D(29), True)
        self.assertEqual((r.streak, r.xp, r.week_total), (1, 0, 0))       # Essay is due next week
        r = game.play(g, [t1], ["a" * 10], set(), D(30), True)            # tapped Done four days early
        self.assertEqual(r.done_now, [("Essay 2", 40)])
        self.assertEqual((r.streak, r.streak_event), (2, "record"))
        t2 = {"id": "b" * 10, "kind": "hw", "title": "Lab 4", "due": "2026-10-31"}
        game.play(g, [t2], [], set(), D(30, 12), False)
        r = game.play(g, [], [], set(), D(32), True)                      # Nov 1: Lab 4 went overdue
        self.assertEqual((r.streak, r.streak_event, r.broke_on), (0, "broken", "Lab 4"))
        self.assertEqual(r.best, 2)

    def test_game_bills_score_when_paid_notice_arrives(self):
        from brief import game
        g = {}
        bill = {"id": "c" * 10, "kind": "bill", "title": "Chase", "who": "Chase", "account": "main", "due": "2026-11-01"}
        game.play(g, [bill], [], set(), datetime(2026, 10, 29, 7, 17, tzinfo=TZ), True)
        r = game.play(g, [], [], {("main", "Chase")}, datetime(2026, 10, 30, 7, 17, tzinfo=TZ), True)
        self.assertEqual(r.done_now, [("Chase", 20)])

    def test_game_taps_only_from_your_chat(self):
        from brief import game, telegram as tgm
        ups = [{"update_id": 1, "callback_query": {"data": "done:" + "a" * 10, "message": {"chat": {"id": 42}}}},
               {"update_id": 2, "callback_query": {"data": "done:" + "b" * 10, "message": {"chat": {"id": 999}}}},
               {"update_id": 3, "callback_query": {"data": "rm -rf", "message": {"chat": {"id": 42}}}}]
        self.assertEqual(game.taps(ups, "42"), ["a" * 10])
        kb = tgm.keyboard([("✓ Essay", "done:" + "a" * 10)])
        self.assertEqual(kb["inline_keyboard"][0][0]["callback_data"], "done:" + "a" * 10)

    def test_game_end_to_end(self):
        import json, os, tempfile
        import brief.main as bm
        import brief.telegram as tgm
        from brief import game
        sent = []
        self._orig_send = tgm.send
        tgm.send = lambda tok, chat, html, buttons=None: sent.append((html, buttons))
        cfg = bm.load_config()
        cfg["delivery"]["channels"] = ["telegram", "email"]
        bm.load_config = lambda path=None: cfg
        os.environ.update(TELEGRAM_BOT_TOKEN="t", TELEGRAM_CHAT_ID="42")
        path = os.path.join(tempfile.mkdtemp(), "state.json")
        g = FakeGoogle(MAIN)
        run(["--force", "--state", path], google=g, now=NOW)
        html, buttons = sent[-1]
        labels = [label for label, _ in buttons]
        self.assertTrue(any("Final Project: Proposal" in x for x in labels), labels)
        self.assertTrue(any(x.startswith("✓ Paid") for x in labels), labels)
        self.assertIn("Mark I", html)
        fp = next(data for label, data in buttons if "Final Project" in label)
        tgm.updates = lambda token, offset=None: [{"update_id": 7, "callback_query": {"data": fp, "message": {"chat": {"id": 42}}}}]
        run(["--force", "--state", path], google=g, now=NOW.replace(hour=12, minute=40))
        html2, buttons2 = sent[-1]
        self.assertNotIn("Fri 10/30 · Final Project: Proposal (ML)", html2)   # done items leave the coursework list
        self.assertNotIn("Final Project", "".join(label for label, _ in buttons2))   # and lose their button
        self.assertIn("Final Project: Proposal", html2)                     # ...but Bruno acknowledges them
        self.assertIn("XP", html2)
        self.assertIn("Level", FakeGoogle.sent[3])                          # the email has the scoreboard
        tgm.send = self._orig_send
        with open(path) as f:
            st = json.load(f)
        self.assertEqual(st["tg_offset"], 8)
        self.assertGreater(st["game"]["xp"], 0)

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
        self.assertEqual(text.count("3:00pm · Dentist"), 1)      # same calendar in two logins -> once
        text = self.run_text({"main": FakeGoogle(MAIN), "other": None})
        self.assertIn("Account problem, other", text)
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
        tgm.send = lambda tok, chat, html, buttons=None: sent.append(html)
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
            self.assertNotIn("lab results", sent[0])                    # health stays off Telegram
            self.assertIn("lab results", FakeGoogle.sent[2])            # but present in the email
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
        for token in ("where every input went", "dropped by rule: Chase offers", "[matched: Chase/due]", "Travel"):
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
