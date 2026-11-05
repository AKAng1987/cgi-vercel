"""election_calendar.py -- US federal Election Days by rule (Tuesday after the first Monday in November, every even year),
each tagged midterm or presidential. Named election_calendar, not calendar: a file called calendar.py next to a script shadows
the stdlib module that urllib and http import. Pure functions; no I/O."""
import datetime as dt


def election_day(year: int) -> dt.date:
    d = dt.date(year, 11, 1)
    first_monday = d + dt.timedelta(days=(0 - d.weekday()) % 7)
    return first_monday + dt.timedelta(days=1)


def kind(year: int) -> str:
    """Presidential years are divisible by 4 (2028, 2032, ...); the other even years are midterms (2026, 2030, ...)."""
    if year % 2:
        raise ValueError(f"{year} is not an even year")
    return "presidential" if year % 4 == 0 else "midterm"


def elections(first_year: int, last_year: int):
    """[(date, kind)] for every even year in [first_year, last_year]."""
    return [(election_day(y), kind(y)) for y in range(first_year + first_year % 2, last_year + 1, 2)]


def add_months(d: dt.date, n: int) -> dt.date:
    """Same day-of-month n months later (clamped to the month's last day)."""
    m = d.month - 1 + n
    y, m = d.year + m // 12, m % 12 + 1
    last = (dt.date(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1)).day
    return dt.date(y, m, min(d.day, last))


def latest_passed(today: dt.date, k: str):
    """The most recent election of this kind strictly before today, or None."""
    for y in range(today.year, 1950, -1):
        if y % 2 == 0 and kind(y) == k and election_day(y) < today:
            return election_day(y)
    return None


def next_upcoming(today: dt.date, k: str):
    y = today.year
    while True:
        if y % 2 == 0 and kind(y) == k and election_day(y) >= today:
            return election_day(y)
        y += 1
