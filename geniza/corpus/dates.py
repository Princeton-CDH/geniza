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


# TODO: need to handle Adar I. (Adar / Adar Bet ?)
# these seem to be the only two word month names
re_hebrew_date = re.compile(
    "(?:(?P<weekday>\w*day), )?(?:(?P<day>\d+) )?(?:(?P<month>\w+( I{1,2})?) )?(?P<year>\d{3,4})",
    flags=re.UNICODE,
)


ignorechars = str.maketrans({val: "" for val in "[]()"})


def convert_hebrew_date(historic_date):
    """
    convert hebrew date to standard date
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
        cdate = get_hebrew_date(year, month, day)
        # if it returned a single date, convert to a tuple for consistency
        if isinstance(cdate, date):
            # could check weekday and warn here...
            return (cdate, cdate)
        else:
            return cdate


def get_hebrew_date(year, month=None, day=None):
    """ "
    Convert a Hebrew date and return as a :class:`datetime.date` or tuple of dates,
    if the conversion is ambiguous. Takes year and optional month and day.
    """
    # NOTE: this raises an error if conversion is out of range

    # if we know month but not day, figure out max and min
    if month and not day:
        month_days = convertdate.hebrew.month_days(year, month)
        # earliest is 1, latest is month_days
        return get_hebrew_date(year, month, 1), get_hebrew_date(year, month, month_days)

    # if we don't know the month, check how many months (i.e. leap year or not)
    if not month:
        year_months = convertdate.hebrew.year_months(year)
        # earliest is 1, latest is month_days
        # TODO: check if invalid max day causes a problem
        return get_hebrew_date(year, 1, 1), get_hebrew_date(year, year_months, 30)

    # all values known; convert and return
    return date(*convertdate.hebrew.to_gregorian(year, month, day))


def display_date_range(earliest, latest):
    """
    display a date range in a human readable format
    """
    # if both dates are the same, only display once
    if earliest == latest:
        return earliest.isoformat()
    else:
        return "%s/%s" % (earliest.isoformat(), latest.isoformat())
