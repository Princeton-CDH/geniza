import codecs
import csv
import os

from django.conf import settings
from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.contrib.sites.models import Site
from django.http import StreamingHttpResponse
from django.utils import timezone
from rich.progress import track

from geniza.common.utils import Echo, Timerable


class Exporter(Timerable):
    """
    Base class for data exports. See DocumentExporter `geniza/corpus/metadata_export.py` for an example of a subclass implementation of Exporter.

    For initializing:

    :param queryset: Limit this export to a given queryset?, defaults to None
    :type queryset: QuerySet, optional
    :param progress: Use a progress bar?, defaults to False
    :type progress: bool, optional
    """

    model = None
    csv_fields = []
    sep_within_cells = " ; "
    true_false = {True: "Y", False: "N"}

    def __init__(self, queryset=None, progress=False):
        self.queryset = queryset
        self.progress = progress
        self.script_user = settings.SCRIPT_USERNAME
        self.site_domain = Site.objects.get_current().domain.rstrip("/")
        self.url_scheme = "https://"

    def __iter__(self):
        yield from self.iter_dicts()

    def csv_filename(self):
        """Generate the appropriate CSV filename for model and time

        :return: Filename string
        :rtype: str
        """
        str_plural = self.model._meta.verbose_name_plural
        str_time = timezone.now().strftime("%Y%m%dT%H%M%S")
        return f"geniza-{str_plural}-{str_time}.csv"

    def get_queryset(self):
        """Get the queryset in use. If not set at init, this will be all objects from the given model.

        :return: QuerySet of documents to export
        :rtype: QuerySet
        """
        return self.queryset or self.model.objects.all()

    def get_export_data_dict(self, obj):
        """A given Exporter class (DocumentExporter, FootnoteExporter, etc) must implement this function. It ought to return a dictionary of exported information for a given object.

        :param obj: Model object (document, footnote, etc)
        :type obj: object
        :raises NotImplementedError: This method must be implemented by subclasses
        """
        raise NotImplementedError

    def iter_dicts(self, desc="Iterating rows"):
        """Iterate over the exportable data, one dictionary per row

        :yield: Dictionary of information for each object
        :rtype: Generator[dict]
        """
        # get queryset
        queryset = self.get_queryset()

        # progress bar?
        iterr = queryset if not self.progress else track(queryset, description=desc)

        # save
        yield from (self.get_export_data_dict(obj) for obj in iterr)

    def serialize_value(self, value):
        """A quick serialize method to transform a value into a CSV-friendly string.

        :param value: Any value
        :type value: object

        :return: Stringified value
        :rtype: str
        """
        valtype = type(value)
        if type(value) is bool:
            return self.true_false[value]
        elif value is None:
            return ""
        elif type(value) in {list, tuple, set}:
            # don't sort here since order may be meaningful
            valstrs = [self.serialize_value(subval) for subval in value]
            valstrs = [vstr for vstr in valstrs if vstr]
            if not valstrs:
                return ""
            else:
                if type(value) is set:
                    valstrs.sort()
                return self.sep_within_cells.join(valstrs)
        else:
            return str(value)

    def serialize_dict(self, data):
        """Return a new dictionary whose keys and values are safe, serialized string versions of the keys and values in input dictionary `data`.

        :param data: Dictionary of keys and values
        :type data: dict

        :return: Dictionary with keys and values safely serialized as strings
        :rtype: dict
        """
        return {k: self.serialize_value(v) for k, v in data.items()}

    def iter_csv(self, fn=None, pseudo_buffer=False, **kwargs):
        """Iterate over the string lines of a CSV file as it's being written, either to file or a string buffer.

        :param fn: Filename to save CSV to (if pseudo_buffer is False), defaults to None
        :type fn: str, optional

        :param pseudo_buffer: Save to string buffer instead of file?, defaults to False
        :type pseudo_buffer: bool, optional

        :yield: String of current line in CSV
        :rtype: Generator[str]
        """
        csv_filename = fn or self.csv_filename()
        filelike_obj = (
            Echo()
            if pseudo_buffer
            else open(csv_filename, "w", newline="", encoding="utf-8-sig")
        )
        with filelike_obj as of:
            # start with byte-order mark so Excel will read unicode properly
            yield codecs.BOM_UTF8
            writer = csv.DictWriter(
                of,
                fieldnames=self.csv_fields,
                extrasaction="ignore",
                lineterminator=os.linesep,
                skipinitialspace=True,
            )
            yield writer.writeheader()
            yield from (
                writer.writerow(self.serialize_dict(docd))
                for docd in self.iter_dicts(**kwargs)
            )

    def write_export_data_csv(self, fn=None):
        """Save CSV of exportable data to file.

        :param fn: Filename to save CSV to, defaults to None
        :type fn: str, optional
        """
        if not fn:
            fn = self.csv_filename()
        for row in self.iter_csv(
            fn=fn, pseudo_buffer=False, desc=f"Writing {os.path.basename(fn)}"
        ):
            pass

    def http_export_data_csv(self, fn=None):
        """Download CSV of exportable data to file.

        :param fn: Filename to download CSV as, defaults to None
        :type fn: str, optional

        :return: Django implementation of StreamingHttpResponse which can be downloaded via web client or programmatically.
        :rtype: StreamingHttpResponse
        """
        if not fn:
            fn = self.csv_filename()
        iterr = self.iter_csv(pseudo_buffer=True)
        response = StreamingHttpResponse(iterr, content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f"attachment; filename={fn}"
        return response


class LogEntryExporter(Exporter):
    model = LogEntry
    csv_fields = [
        "action_time",
        "user",
        "content_type",
        "content_type_app",
        "object_id",
        "change_message",
        "action",
    ]

    #: map log entry action flags to text labels
    action_label = {ADDITION: "addition", CHANGE: "change", DELETION: "deletion"}

    def get_queryset(self):
        return super().get_queryset().select_related("content_type", "user")

    def get_export_data_dict(self, log):
        return {
            "action_time": log.action_time,
            "user": log.user,
            "content_type": log.content_type.name,
            "content_type_app": log.content_type.app_label,
            "object_id": log.object_id,
            "change_message": log.change_message,
            "action": self.action_label[log.action_flag],
        }
