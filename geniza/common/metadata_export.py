import csv

from django.conf import settings
from django.contrib.sites.models import Site
from django.http import StreamingHttpResponse
from django.utils import timezone
from rich.progress import track

from geniza.common.utils import Echo


class Exporter:
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

    def iter_export_data_as_dicts(self):
        """Iterate over the exportable data, one dictionary per row

        :yield: Dictionary of information for each object
        :rtype: Generator[dict]
        """
        # get queryset
        queryset = self.get_queryset()

        # progress bar?
        iterr = (
            queryset
            if not self.progress
            else track(queryset, description=f"Writing rows to file")
        )

        # save
        yield from (self.get_export_data_dict(obj) for obj in iterr)

    def serialize_value(self, value):
        """A quick serialize method to transform a value into a CSV-friendly string.

        :param value: Any value
        :type value: object

        :return: Stringified value
        :rtype: str
        """
        if type(value) is bool:
            return self.true_false[value]
        elif value is None:
            return ""
        elif type(value) in {list, tuple, set}:
            return self.sep_within_cells.join(
                self.serialize_value(subval) for subval in sorted(list(value))
            )
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

    def iter_export_data_as_csv(self, fn=None, pseudo_buffer=False):
        """Iterate over the string lines of a CSV file as it's being written, either to file or a string buffer.

        :param fn: Filename to save CSV to (if pseudo_buffer is False), defaults to None
        :type fn: str, optional

        :param pseudo_buffer: Save to string buffer instead of file?, defaults to False
        :type pseudo_buffer: bool, optional

        :yield: String of current line in CSV
        :rtype: Generator[str]
        """
        with (
            open(self.csv_filename() if not fn else fn, "w")
            if not pseudo_buffer
            else Echo()
        ) as of:
            writer = csv.DictWriter(
                of, fieldnames=self.csv_fields, extrasaction="ignore"
            )
            yield writer.writeheader()
            yield from (
                writer.writerow(self.serialize_dict(docd))
                for docd in self.iter_export_data_as_dicts()
            )

    def write_export_data_csv(self, fn=None):
        """Save CSV of exportable data to file.

        :param fn: Filename to save CSV to, defaults to None
        :type fn: str, optional
        """
        if not fn:
            fn = self.csv_filename()
        for row in self.iter_export_data_as_csv(fn=fn, pseudo_buffer=False):
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
        iterr = self.iter_export_data_as_csv(pseudo_buffer=True)
        response = StreamingHttpResponse(iterr, content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f"attachment; filename={fn}"
        return response
