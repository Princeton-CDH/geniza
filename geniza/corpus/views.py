import csv

from django.shortcuts import render
from django.http import Http404, StreamingHttpResponse
from django.views.generic.detail import DetailView

from geniza.corpus.models import Document
from geniza.corpus.admin import DocumentAdmin


class DocumentDetailView(DetailView):

    model = Document

    context_object_name = "document"

    def get_queryset(self, *args, **kwargs):
        """Don't show document if it isn't public"""
        queryset = super().get_queryset(*args, **kwargs)
        return queryset.filter(status=Document.PUBLIC)


# class Publish


#     def view(request):
#         # Create the HttpResponse object with the appropriate CSV header.
#         response = HttpResponse(
#             content_type='text/csv',
#             headers={'Content-Disposition': f'attachment; filename="{csv_filename()}"'},
#         )

#         return response


class Echo:
    """An object that implements just the write method of the file-like
    interface.
    """

    def write(self, value):
        """Write the value by returning it, instead of storing in a buffer."""
        return value


def some_streaming_csv_view(request):
    """A view that streams a large CSV file."""
    # Generate a sequence of rows. The range is based on the maximum number of
    # rows that can be handled by a single sheet in most spreadsheet
    # applications.
    rows = (["Row {}".format(idx), str(idx)] for idx in range(65536))
    pseudo_buffer = Echo()
    writer = csv.writer(pseudo_buffer)
    response = StreamingHttpResponse(
        (writer.writerow(row) for row in rows), content_type="text/csv"
    )
    response["Content-Disposition"] = 'attachment; filename="somefilename.csv"'
    return response
