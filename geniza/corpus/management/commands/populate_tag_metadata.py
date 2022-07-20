from django.core.management.base import BaseCommand, CommandError
from taggit.models import Tag

from geniza.corpus.models import Document, TagMetadata


class Command(BaseCommand):
    help = "Populate the tag metadata with tag information"

    def populate_tag_metadata(self):
        tags = Tag.objects.all()

        for tag in tags:
            print(tag.name)
            document_count = Document.objects.filter(tags__name=tag.name).count()
            TagMetadata.objects.create(tag=tag, document_count=document_count)

    def empty_tag_metadata(self):
        TagMetadata.objects.all().delete()

    # def add_arguments(self, parser):
    #     parser.add_argument('poll_ids', nargs='+', type=int)

    def handle(self, *args, **options):
        self.populate_tag_metadata()
