import csv

from django.conf import settings
from django.contrib.sites.models import Site
from django.http import StreamingHttpResponse
from django.utils import timezone
from rich.progress import track

from geniza.common.utils import Echo, timeprint


class Exporter:
    """
    Base class for data exports.

    @TODO: init params
    """

    model = None
    csv_fields = []
    sep_within_cells = " ; "

    def __init__(self, queryset=None, progress=False):
        self.queryset = queryset
        self.progress = progress
        self.script_user = settings.SCRIPT_USERNAME
        self.site_domain = Site.objects.get_current().domain.rstrip("/")
        self.url_scheme = "https://"

    def csv_filename(self):
        str_plural = self.model._meta.verbose_name_plural
        str_time = timezone.now().strftime("%Y%m%dT%H%M%S")
        return f"geniza-{str_plural}-{str_time}.csv"

    def get_queryset(self):
        return self.queryset or self.model.objects.all()

    def get_export_data_dict(self, obj):
        # THIS NEEDS TO BE SUBCLASSED
        raise NotImplementedError

    def iter_export_data_as_dicts(self):
        timeprint("iter_export_data_as_dicts")
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

    def iter_export_data_as_csv(self, fn=None, pseudo_buffer=False):
        timeprint("iter_export_data_as_csv")
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
                writer.writerow(docd) for docd in self.iter_export_data_as_dicts()
            )

    def write_export_data_csv(self, fn=None):
        timeprint("write_export_data_csv")
        if not fn:
            fn = self.csv_filename()
        for row in self.iter_export_data_as_csv(fn=fn, pseudo_buffer=False):
            pass

    def http_export_data_csv(self, fn=None):
        timeprint("http_export_data_csv")
        if not fn:
            fn = self.csv_filename()
        iterr = self.iter_export_data_as_csv(pseudo_buffer=True)
        response = StreamingHttpResponse(iterr, content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f"attachment; filename={fn}"
        return response
