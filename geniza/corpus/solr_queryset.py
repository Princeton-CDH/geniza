import re

from bs4 import BeautifulSoup
from django.apps import apps
from django.utils.translation import gettext as _
from parasolr.django import AliasedSolrQuerySet
from piffle.image import IIIFImageClient

from geniza.corpus.ja import arabic_or_ja


def clean_html(html_snippet):
    """utility method to clean up html, since solr snippets of html content
    may result in non-valid content"""
    return BeautifulSoup(html_snippet, "html.parser").prettify(formatter="minimal")


class DocumentSolrQuerySet(AliasedSolrQuerySet):
    """':class:`~parasolr.django.AliasedSolrQuerySet` for
    :class:`~geniza.corpus.models.Document`"""

    #: always filter to item records
    filter_qs = ["item_type_s:document"]

    #: map readable field names to actual solr fields
    field_aliases = {
        "id": "id",  # needed to match results with highlighting
        "type": "type_s",
        "status": "status_s",
        "shelfmark": "shelfmark_s",  # string version for display
        "document_date": "document_date_t",  # text version for search & display
        "original_date_t": "original_date",
        "collection": "collection_ss",
        "tags": "tags_ss_lower",
        "description": "description_en_bigram",  # use stemmed version for field search & highlight
        "notes": "notes_t",
        "needs_review": "needs_review_t",
        "pgpid": "pgpid_i",
        "old_pgpids": "old_pgpids_is",
        "input_year": "input_year_i",
        "input_date": "input_date_dt",
        "num_editions": "num_editions_i",
        "num_translations": "num_translations_i",
        "num_discussions": "num_discussions_i",
        "scholarship_count": "scholarship_count_i",
        "scholarship": "scholarship_t",
        "transcription": "text_transcription",
        "language_code": "language_code_s",
        "language_script": "language_script_s",
        "translation": "text_translation",
        "translation_language_code": "translation_language_code_s",
        "translation_language_direction": "translation_language_direction_s",
        "iiif_images": "iiif_images_ss",
        "iiif_labels": "iiif_labels_ss",
        "has_image": "has_image_b",
        "has_digital_edition": "has_digital_edition_b",
        "has_digital_translation": "has_digital_translation_b",
        "has_discussion": "has_discussion_b",
    }

    # regex to convert field aliases used in search to actual solr fields
    # resulting regex will look something like: ((shelfmark|tags|decription|...):
    # adapted from https://stackoverflow.com/a/15448887
    # - start with a copy of default aliases
    # - define/override additional search aliases for site users
    search_aliases = field_aliases.copy()

    shelfmark_qf = "{!type=edismax qf=$shelfmark_qf}"

    search_aliases.update(
        {
            # when searching, singular makes more sense for tags & old pgpids
            "old_pgpid": field_aliases["old_pgpids"],
            "tag": field_aliases["tags"],
            # for shelfmark, use search field to search multiple formats
            "shelfmark": shelfmark_qf,
        }
    )

    re_solr_fields = re.compile(
        r"(%s):" % "|".join(key for key, val in search_aliases.items() if key != val),
        flags=re.DOTALL,
    )

    # handle shelfmarks that look like booleans
    re_shelfmark_nonbool = re.compile(r"\bBL\s+OR\b")

    # regex to match terms in doublequotes, but not following a colon, at the
    # beginning/end of the string or after/before a space, and not followed by a
    # tilde for fuzzy/proximity search (non-greedy to prevent matching the entire
    # string if there are multiple sets of doublequotes)
    re_exact_match = re.compile(r'(?<!:)\B(".+?")\B(?!~)')

    # if keyword search includes an exact phrase, store unmodified query
    # to use as highlighting query
    highlight_query = None

    def _search_term_cleanup(self, search_term):
        # adjust user search string before sending to solr

        # ignore " + " in search strings, so users can search on shelfmark joins
        search_term = search_term.replace(" + ", " ")
        # convert uppercase OR in BL shelfmark to lowercase
        # to avoid it being interpreted as a boolean
        search_term = self.re_shelfmark_nonbool.sub("BL or", search_term)

        search_term = arabic_or_ja(search_term)

        # look for exact search, indicated by double quotes
        exact_queries = self.re_exact_match.findall(search_term)
        if exact_queries:
            # store unmodified query for highlighting
            self.highlight_query = search_term
            # limit any exact phrase searches to non-stemmed field
            search_term = self.re_exact_match.sub(
                lambda m: f"content_nostem:{m.group(0)}",
                search_term,
            )

        # convert any field aliases used in search terms to actual solr fields
        # (i.e. "pgpid:950 shelfmark:ena" -> "pgpid_i:950 shelfmark_t:ena")
        if ":" in search_term:
            # if any of the field aliases occur with a colon, replace with actual solr field
            search_term = self.re_solr_fields.sub(
                lambda x: "%s:" % self.search_aliases[x.group(1)], search_term
            )
            # special case: shelfmark edismax query should NOT have colon
            # like other fields
            search_term = search_term.replace(
                "%s:" % self.shelfmark_qf, self.shelfmark_qf
            )

        return search_term

    # (adapted from mep)
    # edismax alias for searching on admin document pseudo-field;
    # set q.op to AND (= require all search terms by default, unless OR specified)
    admin_doc_qf = "{!edismax qf=$admin_doc_qf pf=$admin_doc_pf v=$doc_query q.op=AND}"

    def admin_search(self, search_term):
        # remove " + " from search string to allow searching on shelfmark joins
        return self.search(self.admin_doc_qf).raw_query_parameters(
            doc_query=self._search_term_cleanup(search_term)
        )

    keyword_search_qf = "{!type=edismax qf=$keyword_qf pf=$keyword_pf v=$keyword_query}"

    def keyword_search(self, search_term):
        search = self.search(self.keyword_search_qf).raw_query_parameters(
            keyword_query=self._search_term_cleanup(search_term)
        )
        # if search term cleanup identifies any exact phrase searches,
        # pass the unmodified search to Solr as a highlighting query,
        # since otherwise the highlighted fields (description/transcription)
        # have no search terms to highlight.
        if self.highlight_query:
            # NOTE: setting using raw_query_parameters, since parasolr
            # doesn't currently support setting highlighting options that are
            # not field-specific
            search = search.raw_query_parameters(
                **{
                    "hl.q": "{!type=edismax qf=$keyword_qf pf=$keyword_pf v=$hl_query}",
                    "hl_query": self.highlight_query,
                    "hl.qparser": "lucene",
                }
            )
        return search

    def related_to(self, document):
        "Return documents related to the given document (i.e. shares any shelfmarks)"

        # NOTE: using a string query filter because parasolr queryset
        # # currently doesn't provide any kind of not/exclude filter
        return (
            self.filter(status=document.PUBLIC_LABEL)
            .filter("NOT pgpid_i:%d" % document.id)
            .filter(
                fragment_shelfmark_ss__in=[
                    '"%s"' % f.shelfmark for f in document.fragments.all()
                ]
            )
        )

    def get_result_document(self, doc):
        # default implementation converts from attrdict to dict
        doc = super().get_result_document(doc)

        # convert indexed iiif image paths to IIIFImageClient objects
        images = doc.get("iiif_images", [])
        doc["iiif_images"] = [IIIFImageClient(*img.rsplit("/", 1)) for img in images]
        # zip images and associated labels into (img, label) tuples in result doc
        labels = doc.get("iiif_labels", [])
        doc["iiif_images"] = list(zip(doc["iiif_images"], labels))

        # for multilingual support, set doctype to matched DocumentType object
        doctype_str = doc.get("type")
        # apps.get_model is required to avoid circular import
        doc["type"] = apps.get_model("corpus.DocumentType").objects_by_label.get(
            doctype_str,
            # "Unknown type" is not an actual doctype obj, so need to gettext for translation
            _("Unknown type"),
        )

        return doc

    def get_highlighting(self):
        """highlight snippets within transcription/translation html may result in
        invalid tags that will render strangely; clean up the html before returning"""
        highlights = super().get_highlighting()
        for doc in highlights.keys():
            if "transcription" in highlights[doc]:
                highlights[doc]["transcription"] = [
                    clean_html(s) for s in highlights[doc]["transcription"]
                ]
            if "translation" in highlights[doc]:
                highlights[doc]["translation"] = [
                    clean_html(s) for s in highlights[doc]["translation"]
                ]
        return highlights
