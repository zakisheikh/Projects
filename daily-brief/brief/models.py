from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


@dataclass
class Event:
    title: str
    start: datetime          # all-day events: midnight local on their date
    end: datetime
    all_day: bool
    calendar: str = ""
    location: str = ""
    homework: bool = False
    compact: bool = False
    course: str = ""
    hint: str = ""
    creator: str = ""
    exam: bool = False
    link: str = ""          # Google Calendar page for the event (holds the full Canvas description)
    about: str = ""         # first useful sentence of the description


@dataclass
class Mail:
    id: str
    sender: str
    subject: str
    snippet: str
    when: datetime
    unread: bool = False
    important: bool = False
    body: str = ""
    categories: list = field(default_factory=list)
    amount: Optional[str] = None
    due: Optional[date] = None
    account: str = ""
    biller: Optional[str] = None
    kind: str = ""
    event: Optional[str] = None   # due|statement|paid|balance|alert|receipt|info
    note: str = ""
    ignored: bool = False
    link: str = ""
    balance: Optional[str] = None   # statement balance, when a bill states it
