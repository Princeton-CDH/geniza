import itertools
import re

from bs4 import BeautifulSoup
from django.apps import apps
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from parasolr.django import AliasedSolrQuerySet
from piffle.image import IIIFImageClient

from geniza.corpus.ja import arabic_or_ja


def clean_html(html_snippet):
    """utility method to clean up html, since solr snippets of html content
    may result in non-valid content"""

    # if this snippet starts with a line that includes a closing </li> but no opening,
    # try to append the opening <li> (and an ellipsis to show incompleteness)
    incomplete_line = re.match(r"^(?!<li).+<\/li>$", html_snippet, flags=re.MULTILINE)
    incomplete_line_with_p = re.match(r"^<p>.*?</p>\n</li>", html_snippet)
    if incomplete_line or incomplete_line_with_p:
        ellipsis = "..." if incomplete_line else ""
        line_number = re.search(r'<li value="(\d+)"', html_snippet, flags=re.MULTILINE)
        if line_number:
            # try to include the line number with the malformed <li>:
            # use the line number of the first displayed numbered line, and subtract 1
            html_snippet = (
                f'<li value="{int(line_number.group(1)) - 1}">{ellipsis}{html_snippet}'
            )
        else:
            html_snippet = f"<li>{ellipsis}{html_snippet}"

    return BeautifulSoup(
        html_snippet,
        "html.parser",
        # ensure li and em tags don't get extra whitespace, as this may break display
        preserve_whitespace_tags=["li", "em"],
    ).prettify(formatter="minimal")


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
        "iiif_rotations": "iiif_rotations_is",
        "has_image": "has_image_b",
        "has_digital_edition": "has_digital_edition_b",
        "has_digital_translation": "has_digital_translation_b",
        "has_discussion": "has_discussion_b",
        "old_shelfmark": "old_shelfmark_bigram",
        "transcription_nostem": "transcription_nostem",
        "description_nostem": "description_nostem",
        "transcription_regex": "transcription_regex",
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
    re_exact_match = re.compile(r'(?<!:)\B".+?"\B(?!~)')

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

        # look for exact search, indicated by double quotes
        exact_queries = self.re_exact_match.findall(search_term)
        if exact_queries:
            # store unmodified query for highlighting
            self.highlight_query = search_term
            # limit any exact phrase searches to non-stemmed field
            exact_phrases = [
                f"(description_nostem:{m} OR transcription_nostem:{m})"
                for m in self.re_exact_match.findall(search_term)
            ]
            # add in judaeo-arabic conversion for the rest (double-quoted phrase should NOT be
            # converted to JA, as this breaks if any brackets or other sigla are in doublequotes)
            remaining_phrases = [
                arabic_or_ja(p) for p in self.re_exact_match.split(search_term)
            ]
            # stitch the search query back together, in order, so that boolean operators
            # and phrase order are preserved
            search_term = "".join(
                itertools.chain.from_iterable(
                    (
                        itertools.zip_longest(
                            remaining_phrases, exact_phrases, fillvalue=""
                        )
                    )
                )
            )
        else:
            search_term = arabic_or_ja(search_term)

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
        doc_query = self._search_term_cleanup(search_term)
        query_params = {"doc_query": doc_query}
        # nested edismax query no longer works since solr 7.2
        # https://solr.apache.org/guide/7_2/solr-upgrade-notes.html#solr-7-2
        if "{!type=edismax" in doc_query:
            query_params.update({"uf": "* _query_"})

        return self.search(self.admin_doc_qf).raw_query_parameters(**query_params)

    keyword_search_qf = "{!type=edismax qf=$keyword_qf pf=$keyword_pf v=$keyword_query}"

    def keyword_search(self, search_term):
        keyword_query = self._search_term_cleanup(search_term)
        query_params = {"keyword_query": keyword_query}
        # nested edismax query no longer works since solr 7.2 (see above)
        if "{!type=edismax" in keyword_query:
            query_params.update({"uf": "* _query_"})
        search = self.search(self.keyword_search_qf).raw_query_parameters(
            **query_params
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

    def regex_search(self, search_term):
        """Build a Lucene query for searching with regex."""
        # store original regex query
        original_regex = search_term
        # surround passed query with wildcards to allow non-anchored matches,
        # and slashes so that it is interpreted as regex by Lucene
        search_term = f"/.*{search_term}.*/"
        # match in the non-analyzed transcription_regex field
        search = self.search(f"transcription_regex:{search_term}").raw_query_parameters(
            regex_query=original_regex
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
        # zip images, associated labels, and rotation overrides into (img, label, rotation) tuples
        # in result doc
        labels = doc.get("iiif_labels", [])
        # NOTE: if/when piffle supports full image urls, revise to remove any rotation related code
        # from here and search results template, as it will be applied at index time instead
        rotations = [int(rot) for rot in doc.get("iiif_rotations", [0 for _ in labels])]
        doc["iiif_images"] = list(zip(doc["iiif_images"], labels, rotations))

        # for multilingual support, set doctype to matched DocumentType object
        doctype_str = doc.get("type")
        # apps.get_model is required to avoid circular import
        doc["type"] = apps.get_model("corpus.DocumentType").objects_by_label.get(
            doctype_str,
            # "Unknown type" is not an actual doctype obj, so need to gettext for translation
            _("Unknown type"),
        )

        return doc

    def get_regex_highlight(self, text):
        """Helper method to manually highlight and truncate a snippet for regex matches
        (automatic highlight unavailable due to solr regex search limitations)"""
        pattern = f"({self.raw_params['regex_query']})"
        # attempt split on first regex match
        split_text = re.split(pattern, text, maxsplit=1, flags=re.DOTALL)
        if len(split_text) > 1:
            # found a match, truncate text down to just context around match
            # using word boundary as start, get <=150 characters of context before match
            before = split_text[0]
            start_boundary_regex = re.search(r"\b(.{1,150}$)", before, flags=re.DOTALL)
            before = start_boundary_regex.group(1) if start_boundary_regex else before

            # add highlight to matching portion
            match = re.sub(pattern, lambda m: f"<em>{m.group(1)}</em>", split_text[1])

            # get <=150 characters of context after match, using word boundary as end
            after = split_text[2]
            end_boundary_regex = re.search(r"^(.{1,150})\b", after, flags=re.DOTALL)
            after = end_boundary_regex.group(1) if end_boundary_regex else after

            # combine truncated context with highlighted match
            return before + match + after
        else:
            # no match = no highlight
            return None

    def get_highlighting(self):
        """highlight snippets within transcription/translation html may result in
        invalid tags that will render strangely; clean up the html before returning"""
        highlights = super().get_highlighting()
        is_regex_search = "regex_query" in self.raw_params
        if is_regex_search:
            # highlight regex results manually due to solr limitation
            highlights = {}
            for doc in self.get_results():
                highlights[doc["id"]] = {"transcription": []}
                for block in doc["transcription_regex"]:
                    highlight_snippet = self.get_regex_highlight(block)
                    if highlight_snippet:
                        highlights[doc["id"]]["transcription"].append(highlight_snippet)

        is_exact_search = "hl_query" in self.raw_params
        for doc in highlights.keys():
            # _nostem fields should take precedence over stemmed fields in the case of an
            # exact search; in that case, replace highlights for stemmed fields with nostem
            if is_exact_search and "description_nostem" in highlights[doc]:
                highlights[doc]["description"] = highlights[doc]["description_nostem"]
            if is_exact_search and "transcription_nostem" in highlights[doc]:
                highlights[doc]["transcription"] = [
                    clean_html(s) for s in highlights[doc]["transcription_nostem"]
                ]
            elif "transcription" in highlights[doc]:
                highlights[doc]["transcription"] = [
                    clean_html(s) for s in highlights[doc]["transcription"]
                ]
            if "translation" in highlights[doc]:
                highlights[doc]["translation"] = [
                    clean_html(s) for s in highlights[doc]["translation"]
                ]
        return highlights
