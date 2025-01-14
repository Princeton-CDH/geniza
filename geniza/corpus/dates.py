# methods to convert historical dates to standard dates
# will be used for reporting and automatic conversion in admin
import calendar
import re
from datetime import date

import convertdate
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils.formats import date_format
from django.utils.safestring import mark_safe
from unidecode import unidecode

from geniza.common.models import TrackChangesModel


class Calendar:
    """Codes for supported calendars"""

    #: Hijri calendar (Islamic)
    HIJRI = "h"
    #: Kharaji calendar
    KHARAJI = "k"
    #: Seleucid calendar
    SELEUCID = "s"
    #: Anno Mundi calendar (Hebrew)
    ANNO_MUNDI = "am"

    #: calendars that can be converted to Julian/Gregorian
    can_convert = [ANNO_MUNDI, HIJRI, SELEUCID]

    #: offset for Seleucid calendar: Anno Mundi - 3449
    SELEUCID_OFFSET = 3449


class PartialDate:
    """Simple partial date object to handle parsing and display of
    dates in the format YYYY, YYYY-MM, or YYYY-MM-DD. Display format
    is based on known precision of year, month, or day."""

    available_precision = ["year", "month", "day"]
    #: public display format based on date precision
    display_format = {
        "year": "Y",
        "month": "F Y",
        "day": "j F Y",
    }
    #: ISO format based on date precision
    iso_format = {
        "year": "%Y",
        "month": "%Y-%m",
        "day": "%Y-%m-%d",
    }
    #: numeric format for indexing and sorting
    num_fmt = "%Y%m%d"

    def __init__(self, str):
        # TODO: probably still need more validation/error handling here
        # for real world use
        date_parts = str.split("-")
        if len(date_parts) > 3:
            raise ValueError(f"Error parsing standard date {str}")
        # since we don't currently support unknown year,
        # precision can be determined by number of date parts
        self.precision = self.available_precision[len(date_parts) - 1]
        # fill in unknown month/day as 1
        date_parts += [1] * (3 - len(date_parts))
        # cast to integer and convert to datetime.date
        self.date = date(*[int(p) for p in date_parts])

    def __str__(self):
        # format the date based on known precision
        return date_format(
            self.date, format=self.display_format[self.precision], use_l10n=True
        )

    def __repr__(self) -> str:
        return f"PartialDate({self.isoformat()})"

    def __eq__(self, other):
        if not isinstance(other, PartialDate):
            # don't attempt to compare against unrelated types
            return NotImplemented

        # equivalent if date and precision are the same
        return self.date == other.date and self.precision == other.precision

    def isoformat(self, mode="min", fmt="precision"):
        """Display partial date in ISO format. By default, will display
        YYYY, YYYY-MM, or YYYY-MM-DD according to known precision. If min
        or max is requested, will display YYYY-MM-DD for earliest or latest
        date based on known precision.

        :param mode: how to fill in unknowns: min, or max (default: min)
        :param fmt: format: precision (default), isoformat, or numeric
        """
        # determine possibly unknown parts of the date
        month = (
            self.date.month
            if self.precision in ["month", "day"] or mode == "min"
            else 12
        )
        # if we don't know the day or mode is not min, determine max day
        # by getting the number of days for this month in this year
        # (if min, use 1 which is default in init)
        day = (
            self.date.day
            if self.precision == "day" or mode == "min"
            else calendar.monthrange(self.date.year, month)[1]
        )

        display_date = date(self.date.year, month, day)
        # display only known precision
        if fmt == "precision":
            return display_date.strftime(self.iso_format[self.precision])

        if fmt == "numeric":
            return display_date.strftime(self.num_fmt)

        # display full date, unknowns filled in based on min/max
        return display_date.isoformat()

    def numeric_format(self, mode="min"):
        """ "Date in numeric format for sorting; max or min for unknowns.
        See :meth:`isoformat` for more details."""
        return self.isoformat(mode, "numeric")

    @staticmethod
    def get_date_range(old_range, new_range):
        """Compute the union (widest possible date range) between two PartialDate ranges."""
        minmax = old_range
        [start, end] = new_range

        # use numeric format to compare to current min, replace if smaller
        start_numeric = int(start.numeric_format(mode="min"))
        min = minmax[0]
        if min is None or start_numeric < int(min.numeric_format(mode="min")):
            # store as PartialDate, not numeric format
            minmax[0] = start
        # use numeric format to compare to current max, replace if larger
        end_numeric = int(end.numeric_format(mode="max"))
        max = minmax[1]
        if max is None or end_numeric > int(max.numeric_format(mode="max")):
            # store as PartialDate, not numeric format
            minmax[1] = end

        return minmax


class DocumentDateMixin(TrackChangesModel):
    """Mixin for document date fields (original and standardized),
    and related logic for displaying, converting,a nd validating dates."""

    doc_date_original = models.CharField(
        "Date on document",
        help_text="Explicit date on the document, in original format",
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
        + "\nSeleucid (sometimes listed as Minyan Shetarot); Anno Mundi (Hebrew calendar)",
        blank=True,
    )

    # supports YYYY, YYYY-MM, YYYY-MM-DD and same formats as ranges YYYY/YYYY
    re_date_format = re.compile(
        r"^\d{3,4}(-[01]\d(-[0-3]\d)?)?(/\d{3,4}(-[01]\d(-[0-3]\d)?)?)?$"
    )

    standard_date_helptext = str(
        "Convert to Julian before 1582, Gregorian after 1582. "
        + "\nUse YYYY, YYYY-MM, YYYY-MM-DD format or YYYY-MM-DD/YYYY-MM-DD for date ranges.",
    )

    doc_date_standard = models.CharField(
        "CE date",
        help_text=f"{standard_date_helptext} \nLeave blank or clear out to automatically "
        + "calculate standardized date for supported calendars.",
        blank=True,
        max_length=255,
        validators=[RegexValidator(re_date_format)],
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
            standardized_date = standard_date_display(self.doc_date_standard)
            # add parentheses to standardized date if original date is also present
            if self.original_date:
                # NOTE: we want no-wrap for individual dates when displaying as html
                # may want to split out formatted/unformatted versions
                return mark_safe(
                    "<span>%s</span> <span>(%s)</span>"
                    % (
                        self.original_date,
                        standardized_date,
                    )
                )
            # should we always use spans, or only when both dates are present?
            return standardized_date
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

    def standardize_date(self, update=False):
        """
        Convert the document's original date to a standardized date, if possible.
        If update is requested, will store the converted value on :attr:`doc_date_standard`
        """
        # if original date is set and conversion is supported for this calendar,
        # generate the standardized date
        if self.doc_date_original and self.doc_date_calendar in Calendar.can_convert:
            std_date = standardize_date(self.doc_date_original, self.doc_date_calendar)
            if std_date:
                converted_date = display_date_range(*std_date)
                # if update is requested and standard date is unset, save the converted date
                if update and not self.doc_date_standard:
                    self.doc_date_standard = converted_date
                return converted_date

    _parsed_date = {}

    @property
    def parsed_date(self):
        """Parse standard date (if set) and return as dictionary
        of start/end :class:`PartialDate` objects"""
        # for efficiency, parse and cache standard date into
        # a dictionary of start/end partial dates.
        # recalculate if not set or standard date has changed
        if (
            self.doc_date_standard
            and not self._parsed_date
            or self.has_changed("doc_date_standard")
        ):
            try:
                date_parts = self.doc_date_standard.split("/")
                start = PartialDate(date_parts[0])
                # if a single date instead of a range, start and end are the same
                if len(date_parts) == 1:
                    end = start
                else:
                    end = PartialDate(date_parts[1])

                self._parsed_date = {"start": start, "end": end}
            except ValueError:
                # ignore if it can't be parsed (records before validation added)
                pass

        return self._parsed_date

    @property
    def start_date(self):
        """
        Return the start date of the document's standardized date or date range, if set.
        """
        return self.parsed_date.get("start")

    @property
    def end_date(self):
        """
        Return the end date of the document's standardized date or date range, if set.
        """
        return self.parsed_date.get("end")

    def solr_date_range(self):
        """
        Return a Solr date range for the document's standardized date.
        """
        # only convert if standardized document date is set and passes validation
        if self.doc_date_standard and self.re_date_format.match(self.doc_date_standard):
            # if we have a single date, return it as is
            date_parts = self.doc_date_standard.split("/")
            # if a single date instead of a range, start and end are the same
            if len(date_parts) == 1:
                return date_parts[0]
            # if there's more than one date, return as a range
            return "[%s TO %s]" % tuple(date_parts)


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
    """Convert Hebrew month name to month number.
    Supports local month name aliases for alternate spellings."""
    # use unidecode to simplify handling with/without accents
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
    r"(?:(?P<weekday>\w+day),? )?(?:(?P<day>\d+) )?(?:(?P<month>[^\d]+( I{1,2})?) )?(?P<year>\d{3,4})",
    flags=re.UNICODE,
)

# characters to remove before applying regex to historical date
ignorechars = str.maketrans({val: "" for val in "[]()"})


def get_calendar_month(convertdate_module, month):
    """ "Convert month name to month number for the specified calendar.

    :param convertdate_module: `convertdate` calendar module to use
    :param month: string month name
    :return int: month number
    """
    if convertdate_module == convertdate.hebrew:
        return get_hebrew_month(month)
    elif convertdate_module == convertdate.islamic:
        return get_islamic_month(month)


def convert_hebrew_date(historic_date):
    """Convert a date in the Hebrew Anno Mundi calendar to the Julian or Gregorian calendar"""
    return standardize_date(historic_date, Calendar.ANNO_MUNDI)


def convert_seleucid_date(historic_date):
    """Convert a date in the Greek Seleucid calendar to the Julian or Gregorian calendar"""
    return standardize_date(historic_date, Calendar.SELEUCID)


def convert_islamic_date(historic_date):
    """Convert a date in the Islamic Hijri calendar to the Julian or Gregorian calendar"""
    return standardize_date(historic_date, Calendar.HIJRI)


#: mapping between supported calendars and corresponding convertdate module
calendar_converter = {
    Calendar.ANNO_MUNDI: convertdate.hebrew,
    Calendar.HIJRI: convertdate.islamic,
    # NOTE: Seleucid years cannot be passed directly into convertdate.hebrew; instead,
    # convert them to AM using the Seleucid offset first, in order to handle leap years
    Calendar.SELEUCID: convertdate.hebrew,
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
    # may want to log or debug regex mismatch for dev or reporting
    if match:
        date_info = match.groupdict()
        year = int(date_info["year"])
        if calendar == Calendar.SELEUCID:
            year = year + Calendar.SELEUCID_OFFSET
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
    display a date range or single date in a isoformat
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
    """Convert Islamic month name to month number; works
    with or without accents, and supports local month-name overrides."""
    month_name = unidecode(month_name)
    return islamic_months.index(islamic_month_aliases.get(month_name, month_name)) + 1


def standard_date_display(standard_date):
    """Display a standardized CE date in human readable format."""
    # bail out if there is nothing to display
    if not standard_date:
        return

    # currently storing in isoformat, with slash if a date range
    dates = standard_date.split("/")
    # we should always have at least one date, if date is set
    # convert to local partial date object for precision-aware string formatting
    # join dates with en-dash if more than one;
    # add CE to the end to make calendar system explicit
    try:
        return "%s CE" % "–".join(str(PartialDate(d)) for d in dates)
    except ValueError:
        # dates entered before validation was applied may not parse
        # as fallback, display as is
        return "%s CE" % standard_date
