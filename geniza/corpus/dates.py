# methods to convert historical dates to standard dates
# will be used for reporting and automatic conversion in admin
import re
from datetime import date

import convertdate
from django.core.exceptions import ValidationError
from django.db import models
from unidecode import unidecode


class Calendar:
    """Codes for supported calendars"""

    #: Hijri calendar (Islamic)
    HIJRI = "h"
    #: Kharaji calendar
    KHARAJI = "k"
    #: Seleucide calendar
    SELEUCID = "s"
    #: Anno Mundi calendar (Hebrew)
    ANNO_MUNDI = "am"


class DocumentDateMixin(models.Model):
    """Mixin for document date fields (original and standardized),
    and related logic for displaying, converting,a nd validating dates."""

    doc_date_original = models.CharField(
        "Date on document (original)",
        help_text="explicit date on the document, in original format",
        blank=True,
        max_length=255,
    )
    CALENDAR_CHOICES = (
        (Calendar.HIJRI, "Hijrī"),
        (Calendar.KHARAJI, "Kharājī"),
        (Calendar.SELEUCID, "Seleucid"),
        (Calendar.ANNO_MUNDI, "Anno Mundi"),
    )
    doc_date_calendar = models.CharField(
        "Calendar",
        max_length=2,
        choices=CALENDAR_CHOICES,
        help_text="Calendar according to which the document gives a date: "
        + "Hijrī (AH); Kharājī (rare - mostly for fiscal docs); "
        + "Seleucid (sometimes listed as Minyan Shetarot); Anno Mundi (Hebrew calendar)",
        blank=True,
    )
    doc_date_standard = models.CharField(
        "Document date (standardized)",
        help_text="CE date (convert to Julian before 1582, Gregorian after 1582). "
        + "Use YYYY, YYYY-MM, YYYY-MM-DD format when possible",
        blank=True,
        max_length=255,
    )

    class Meta:
        abstract = True

    @property
    def original_date(self):
        """Generate formatted display for the document's original/historical date"""
        # combine date and calendar or return empty string
        return " ".join(
            [self.doc_date_original, self.get_doc_date_calendar_display()]
        ).strip()

    @property
    def document_date(self):
        """Generate formatted display of combined original and standardized dates"""
        if self.doc_date_standard:
            # append "CE" to standardized date if it exists
            standardized_date = " ".join([self.doc_date_standard, "CE"])
            # add parentheses to standardized date if original date is also present
            if self.original_date:
                standardized_date = "".join(["(", standardized_date, ")"])
            return " ".join([self.original_date, standardized_date]).strip()
        else:
            # if there's no standardized date, just display the historical date
            return self.original_date

    def clean(self):
        """
        Require doc_date_original and doc_date_calendar to be set
        if either one is present.
        """
        if self.doc_date_calendar and not self.doc_date_original:
            raise ValidationError("Original date is required when calendar is set")
        if self.doc_date_original and not self.doc_date_calendar:
            raise ValidationError("Calendar is required when original date is set")

    #: calendars that can be converted to Julian/Gregorian
    can_convert_calendar = [Calendar.ANNO_MUNDI, Calendar.HIJRI]

    def standardize_date(self):
        """
        Convert the document's original date to a standardized date, if possible.
        """
        if (
            self.doc_date_original
            and self.doc_date_calendar in self.can_convert_calendar
        ):
            pass


# Julian Thursday, 4 October 1582, being followed by Gregorian Friday, 15 October
# cut off between gregorian/julian dates, in julian days
gregorian_start_jd = convertdate.julianday.from_julian(1582, 10, 5)


# PGP month names don't match exactly those used in convertdate;
# add local aliases to map them
hebrew_month_aliases = {
    "Tevet": "Teveth",
    "Iyar": "Iyyar",
    "Tishrei": "Tishri",
    "Adar I": "Adar",
    "Adar II": "Adar Bet",
}


def get_hebrew_month(month_name):
    """Convert Hebrew month name to month number"""
    # use unidecode to simplify handling with/without accents & underdots
    month_name = unidecode(month_name)
    return (
        convertdate.hebrew.MONTHS.index(
            hebrew_month_aliases.get(month_name, month_name)
        )
        + 1
    )


#: regular expression for extracting information from original date string
re_original_date = re.compile(
    # for months, match any non-numeric characters, since some month names are multi-word
    "(?:(?P<weekday>\w+day),? )?(?:(?P<day>\d+) )?(?:(?P<month>[^\d]+( I{1,2})?) )?(?P<year>\d{3,4})",
    flags=re.UNICODE,
)

# characters to remove before applying regex to historical date
ignorechars = str.maketrans({val: "" for val in "[]()"})


def get_calendar_month(convertdate_module, month):
    if convertdate_module == convertdate.hebrew:
        return get_hebrew_month(month)
    elif convertdate_module == convertdate.islamic:
        return get_islamic_month(month)


def convert_hebrew_date(historic_date):
    return standardize_date(historic_date, Calendar.ANNO_MUNDI)


def convert_islamic_date(historic_date):
    return standardize_date(historic_date, Calendar.HIJRI)


calendar_converter = {
    Calendar.ANNO_MUNDI: convertdate.hebrew,
    Calendar.HIJRI: convertdate.islamic,
}


def standardize_date(historic_date, calendar):
    """
    convert hebrew date in text format to standard date range
    """
    # some historic dates include brackets or parentheses; ignore them
    historic_date = historic_date.translate(ignorechars)

    # get the convertdate calendar module for the specified calendar
    converter = calendar_converter[calendar]

    match = re_original_date.match(historic_date)
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
                month = get_calendar_month(converter, month)

        day = date_info["day"]
        day = int(day) if day else None
        # weekday = date_info["weekday"]  # use for checking

        # convert
        cdate = get_calendar_date(converter, year, month, day)
        # cdate = get_hebrew_date(year, month, day)
        # if it returned a single date, convert to a tuple for consistency
        if isinstance(cdate, date):
            # could check weekday and warn here...
            return (cdate, cdate)
        else:
            return cdate


def get_calendar_date(converter, year, month=None, day=None, mode=None):
    """
    Convert a date from a supported calendar and return
    as a :class:`datetime.date` or tuple of dates for a date range,
    when the conversion is ambiguous. Takes year and optional month and day.
    """
    # NOTE: this raises an error if conversion is out of range

    # if we know month but not day, determine the number of days in the month
    # then generate standard dates for max and min (earliest and latest)
    if month and not day:
        # convertdate is inconsistent; should be fixed in 2.4.1
        if hasattr(converter, "month_days"):
            # hebrew calendar has month_days method
            month_days = converter.month_days(year, month)
        else:
            # islamic calendar has month_length
            month_days = converter.month_length(year, month)
        # earliest is 1, latest is month_days

        # when mode is latest, only return the last day of the month
        if mode == "latest":
            return get_calendar_date(converter, year, month, month_days)
        # otherwise, return first and last
        return get_calendar_date(converter, year, month, 1), get_calendar_date(
            converter, year, month, month_days
        )

    # if we don't know the month, we want to calculate
    # the earliest and latest
    if not month:
        if converter == convertdate.hebrew:
            # hebrew calendar civil year starts in Tishri
            earliest_month = convertdate.hebrew.TISHRI
            # Elul is the month before Tishri
            latest_month = convertdate.hebrew.ELUL

        else:
            # fall back to the number of months;
            # In Islamic calendar, does not vary by year
            year_months = len(converter.MONTHS)
            earliest_month = 1
            latest_month = year_months

        # return the first day of the first month and the last day of the last month
        # OR: would it make more sense / be simpler to get the first day
        # of the next year and subtract one day?
        return get_calendar_date(converter, year, earliest_month, 1), get_calendar_date(
            converter, year, latest_month, mode="latest"
        )

    # year/month/day all values determined; convert and return
    # convert to julian days
    converted_jd = converter.to_jd(year, month, day)
    # if before the start of the gregorian calendar, convert to julian
    if converted_jd < gregorian_start_jd:
        converted_date = convertdate.julian.from_jd(converted_jd)
    # otherwise, convert to gregorian
    else:
        converted_date = convertdate.gregorian.from_jd(converted_jd)

    # convert tuple of year, month, day to datetime.date
    return date(*converted_date)


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
    # NOTE: trailing commas are typeod in convertdate; will be fixed in 2.4.1
    "Rabi' II": "Rabi' ath-Thani,",
    "Jumada I": "Jumada al-`Awwal,",
    "Jumada II": "Jumada ath-Thaniyah,",
    "Dhu l-Qa'da": "Zu al-Qa'dah",
    "Dhu l-Hijja": "Zu al-Hijjah",
}


def get_islamic_month(month_name):
    month_name = unidecode(month_name)
    return islamic_months.index(islamic_month_aliases.get(month_name, month_name)) + 1
