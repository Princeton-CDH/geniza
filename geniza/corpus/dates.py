# methods to convert historical dates to standard dates
# will be used for reporting and automatic conversion in admin
import re
from datetime import date

import convertdate
from unidecode import unidecode

hebrew_month_aliases = {
    "Tevet": "Teveth",
    "Iyar": "Iyyar",
    "Tishrei": "Tishri",
    "Adar I": "Adar",
    "Adar II": "Adar Bet",
}


def get_hebrew_month(month_name):
    # use unidecode to simplify handling with/without accents & underdots
    month_name = unidecode(month_name)
    return (
        convertdate.hebrew.MONTHS.index(
            hebrew_month_aliases.get(month_name, month_name)
        )
        + 1
    )


# for testing
# assert get_hebrew_month("Kislev") == hebrew.KISLEV


# these seem to be the only two word month names
re_hebrew_date = re.compile(
    # for months, match any non-numeric characters
    # "(?:(?P<weekday>\w*day), )?(?:(?P<day>\d+) )?(?:(?P<month>[-\w ']+( I{1,2})?) )?(?P<year>\d{3,4})",#
    "(?:(?P<weekday>\w*day), )?(?:(?P<day>\d+) )?(?:(?P<month>[^\d]+( I{1,2})?) )?(?P<year>\d{3,4})",
    flags=re.UNICODE,
)


ignorechars = str.maketrans({val: "" for val in "[]()"})


def convert_hebrew_date(historic_date):
    """
    convert hebrew date in text format to standard date range
    """
    # some historic dates include brackets or parentheses; ignore them
    historic_date = historic_date.translate(ignorechars)

    match = re_hebrew_date.match(historic_date)
    if not match:
        print("***regex did not match for %s" % historic_date)
    if match:
        date_info = match.groupdict()
        year = int(date_info["year"])
        month = date_info["month"]

        if month:
            # ignore seasons for now
            if month.lower() in ["spring", "summer", "fall", "winter"]:
                month = None
            else:
                month = get_hebrew_month(month)

        day = date_info["day"]
        day = int(day) if day else None
        # weekday = date_info["weekday"]  # use for checking

        # convert
        cdate = get_calendar_date(convertdate.hebrew, year, month, day)
        # cdate = get_hebrew_date(year, month, day)
        # if it returned a single date, convert to a tuple for consistency
        if isinstance(cdate, date):
            # could check weekday and warn here...
            return (cdate, cdate)
        else:
            return cdate


def get_calendar_date(calendar, year, month=None, day=None):
    """ "
    Convert a date from a supported calendar and return as a :class:`datetime.date` or tuple of dates,
    if the conversion is ambiguous. Takes year and optional month and day.
    """
    # NOTE: this raises an error if conversion is out of range

    # if we know month but not day, figure out max and min
    if month and not day:
        # convertdate is inconsistent
        if hasattr(calendar, "month_days"):
            # hebrew calendar has month_days method
            month_days = calendar.month_days(year, month)
        else:
            # islamic calendar has month_length
            month_days = calendar.month_length(year, month)
        # earliest is 1, latest is month_days
        return get_calendar_date(calendar, year, month, 1), get_calendar_date(
            calendar, year, month, month_days
        )

    # if we don't know the month, check how many months (i.e. leap year or not)
    if not month:
        if hasattr(calendar, "year_months"):
            # hebrew calendar has leap years
            year_months = calendar.year_months(year)
        else:
            # number of months in islamic calendar does not vary by year
            year_months = len(calendar.MONTHS)

        # earliest is 1, latest is month_days
        # TODO: check if invalid max day causes a problem
        return get_calendar_date(calendar, year, 1, 1), get_calendar_date(
            calendar, year, year_months, 30
        )

    # all values known; convert and return
    return date(*calendar.to_gregorian(year, month, day))


def display_date_range(earliest, latest):
    """
    display a date range in a human readable format
    """
    # if both dates are the same, only display once
    if earliest == latest:
        return earliest.isoformat()
    else:
        return "%s/%s" % (earliest.isoformat(), latest.isoformat())


## islamic calendar

# generate unicode-decoded version of month list for better matching
islamic_months = [unidecode(m) for m in convertdate.islamic.MONTHS]

# local overrides for months
islamic_month_aliases = {
    "Muharram": "al-Muharram",
    "Rabi' I": "Rabi' al-`Awwal",
    "Rabi' II": "Rabi' ath-Thani,",  # is comma an error in convertdate?
    "Jumada I": "Jumada al-`Awwal",
    "Jumada II": "Jumada ath-Thaniyah,",
    "Dhu l-Qa`da": "Zu al-Qa`dah",
    "Dhu l-Hijja": "Zu al-Hijjah",
}


def get_islamic_month(month_name):
    month_name = unidecode(month_name)
    return islamic_months.index(islamic_month_aliases.get(month_name, month_name)) + 1


def convert_islamic_date(historic_date):
    # TODO: refactor to consolidate with hebrew date, nearly the same logic
    match = re_hebrew_date.match(historic_date)
    if not match:
        print("***regex did not match for %s" % historic_date)
    if match:
        date_info = match.groupdict()
        print(date_info)
        year = int(date_info["year"])
        month = date_info["month"]

        if month:
            # ignore seasons for now
            if month.lower() in ["spring", "summer", "fall", "winter"]:
                month = None
            else:
                month = get_islamic_month(month)

        day = date_info["day"]
        day = int(day) if day else None

        # convert
        cdate = get_calendar_date(convertdate.islamic, year, month, day)
        # cdate = get_hebrew_date(year, month, day)
        # if it returned a single date, convert to a tuple for consistency
        if isinstance(cdate, date):
            # could check weekday and warn here...
            return (cdate, cdate)
        else:
            return cdate
