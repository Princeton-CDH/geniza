from django.conf import settings
from django.contrib.sites.models import Site
from import_export.fields import Field
from import_export.resources import ModelResource

from geniza.corpus.models import Document, Fragment


class DocumentResource(ModelResource):
    id = Field(attribute="id", column_name="pgpid")
    url = Field(column_name="url")
    iiif_urls = Field()
    fragment_urls = Field()
    shelfmark = Field()
    multifragment = Field()
    side = Field()
    region = Field()
    type = Field()
    tags = Field()
    description = Field(attribute="description")
    shelfmarks_historic = Field()
    languages_primary = Field()
    languages_secondary = Field()
    language_note = Field(attribute="language_note")
    doc_date_original = Field(attribute="doc_date_original")
    doc_date_calendar = Field(attribute="doc_date_calendar")
    doc_date_standard = Field(attribute="doc_date_standard")
    notes = Field(attribute="notes")
    needs_review = Field(attribute="needs_review")
    url_admin = Field()
    initial_entry = Field()
    last_modified = Field(attribute="last_modified")
    input_by = Field()
    status = Field()
    library = Field()
    collection = Field()

    class Meta:
        model = Document
        fields = (
            "id",
            "url",
            "iiif_urls",
            "fragment_urls",
            "shelfmark",
            "multifragment",
            "side",
            "region",
            "type",
            "tags",
            "description",
            "shelfmarks_historic",
            "languages_primary",
            "languages_secondary",
            "language_note",
            "doc_date_original",
            "doc_date_calendar",
            "doc_date_standard",
            "notes",
            "needs_review",
            "url_admin",
            "initial_entry",
            "last_modified",
            "input_by",
            "status",
            "library",
            "collection",
        )

    def dehydrate_id(self, doc):
        return int(doc.id)

    def dehydrate_url(self, doc):
        site_domain = Site.objects.get_current().domain.rstrip("/")
        url_scheme = "https://"
        return f"{url_scheme}{site_domain}/documents/{doc.id}/"  # public site url

    def dehydrate_iiif_urls(self, doc):
        all_textblocks = doc.textblock_set.all()
        all_fragments = [tb.fragment for tb in all_textblocks]
        iiif_urls = [fr.iiif_url for fr in all_fragments]
        return ";".join(iiif_urls) if any(iiif_urls) else ""

    def dehydrate_fragment_urls(self, doc):
        all_textblocks = doc.textblock_set.all()
        all_fragments = [tb.fragment for tb in all_textblocks]
        fragment_urls = [fr.url for fr in all_fragments]
        return ";".join(fragment_urls) if any(fragment_urls) else ""

    def dehydrate_shelfmark(self, doc):
        return doc.shelfmark

    def dehydrate_multifragment(self, doc):
        all_textblocks = doc.textblock_set.all()
        multifrag = [tb.multifragment for tb in all_textblocks]
        return ";".join([s for s in multifrag if s])

    def dehydrate_side(self, doc):
        all_textblocks = doc.textblock_set.all()
        sides = [tb.side for tb in all_textblocks]
        return ";".join([s for s in sides if s])

    def dehydrate_region(self, doc):
        all_textblocks = doc.textblock_set.all()
        regions = [tb.region for tb in all_textblocks]
        return ";".join([s for s in regions if s])

    def dehydrate_type(self, doc):
        return doc.doctype.name if doc.doctype else ""

    def dehydrate_tags(self, doc):
        return doc.all_tags()

    # description (standard)

    def dehydrate_shelfmarks_historic(self, doc):
        all_textblocks = doc.textblock_set.all()
        all_fragments = [tb.fragment for tb in all_textblocks]
        old_shelfmarks = [fr.old_shelfmarks for fr in all_fragments]
        return ";".join([os for os in old_shelfmarks if os])

    def dehydrate_languages_primary(self, doc):
        return doc.all_languages()

    def dehydrate_languages_secondary(self, doc):
        return doc.all_secondary_languages()

    # standard ...
    # def dehydrate_doc_date_original(self, doc):
    # def dehydrate_doc_date_calendar(self, doc):
    # def dehydrate_doc_date_standard(self, doc):
    # def dehydrate_notes(self, doc):
    # def dehydrate_needs_review(self, doc):

    def dehydrate_url_admin(self, doc):
        site_domain = Site.objects.get_current().domain.rstrip("/")
        url_scheme = "https://"
        return f"{url_scheme}{site_domain}/admin/corpus/document/{doc.id}/change/"

    def dehydrate_initial_entry(self, doc):
        all_log_entries = doc.log_entries.all()
        return all_log_entries.last().action_time if all_log_entries else ""

    # def dehydrate_last_modified(self, doc):

    def dehydrate_input_by(self, doc):
        all_log_entries = doc.log_entries.all()
        script_user = settings.SCRIPT_USERNAME
        input_users = set(
            [
                log_entry.user
                for log_entry in all_log_entries
                if log_entry.user.username != script_user
            ]
        )
        return ";".join(
            set([user.get_full_name() or user.username for user in input_users])
        )

    def dehydrate_status(self, doc):
        return doc.get_status_display()

    def dehydrate_library(self, doc):
        all_textblocks = doc.textblock_set.all()
        all_fragments = [tb.fragment for tb in all_textblocks]
        libraries = set(
            [
                fragment.collection.lib_abbrev or fragment.collection.library
                if fragment.collection
                else ""
                for fragment in all_fragments
            ]
        ) - {
            ""
        }  # exclude empty string for any fragments with no library
        return ";".join(libraries) if any(libraries) else ""

    def dehydrate_collection(self, doc):
        all_textblocks = doc.textblock_set.all()
        all_fragments = [tb.fragment for tb in all_textblocks]
        collections = set(
            [
                fragment.collection.abbrev or fragment.collection.name
                if fragment.collection
                else ""
                for fragment in all_fragments
            ]
        ) - {
            ""
        }  # exclude empty string for any with no collection
        return ";".join(collections) if any(collections) else ""


class PublicDocumentResource(ModelResource):
    class Meta:
        model = Document
        exclude = ("old_pgpids", "log_entries")


class FragmentResource(ModelResource):
    class Meta:
        model = Fragment
