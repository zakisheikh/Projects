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
