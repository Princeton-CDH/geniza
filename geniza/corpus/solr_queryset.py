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
        "shelfmarks": "fragment_shelfmark_ss",
        "shelfmark_regex": "shelfmark_regex",
        "document_date": "document_date_t",  # text version for search & display
        "document_dating": "document_dating_t",  # inferred date for display
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
        "languages": "language_name_ss",
        "translation": "text_translation",
        "translation_language": "translation_languages_ss",
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
        "old_shelfmark_t": "old_shelfmark_t",
        "old_shelfmark_regex": "old_shelfmark_regex",
        "transcription_nostem": "transcription_nostem",
        "description_nostem": "description_nostem",
        "related_people": "people_count_i",
        "related_places": "places_count_i",
        "related_documents": "documents_count_i",
        "transcription_regex": "transcription_regex",
        "transcription_regex_names": "transcription_regex_names_ss",
        "description_regex": "description_regex",
        "translation_regex": "translation_regex",
        "translation_regex_names": "translation_regex_names_ss",
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

    # if search consists only of quoted phrase scoped to shelfmark, handle separately
    shelfmark_query = None

    # hebrew prefixes that should be removed to produce an additional keyword to search
    re_hebrew_prefix = re.compile(r"\b(אל|[ולבכמהשׁפ])[\u0590-\u05fe]+\b")

    def _handle_hebrew_prefixes(self, search_term):
        # if any word begins with one of the prefixes, update search to include the word
        # without that prefix as well
        prefixed_words = self.re_hebrew_prefix.finditer(search_term)
        prefixed_words = [w.group(0) for w in prefixed_words]
        if prefixed_words:
            prefixed_or_nonprefixed_query = [
                # handle two-charater prefix אל by removing 2 chars
                f"({word} OR {word[2:] if word.startswith('אל') else word[1:]})"
                for word in prefixed_words
            ]
            # use a custom delimiter to split on, since we need a capturing
            # group in the original expression, but it changes the split function's
            # behavior in an undesirable way
            delim = "!SPLITME!"
            nonprefixed_words = [
                n
                for n in re.sub(self.re_hebrew_prefix, delim, search_term).split(delim)
                if n
            ]

            # stitch the search query back together
            return "".join(
                itertools.chain.from_iterable(
                    (
                        itertools.zip_longest(
                            nonprefixed_words,
                            prefixed_or_nonprefixed_query,
                            fillvalue="",
                        )
                    )
                )
            )
        return search_term

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
                arabic_or_ja(self._handle_hebrew_prefixes(p))
                for p in self.re_exact_match.split(search_term)
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
            search_term = arabic_or_ja(self._handle_hebrew_prefixes(search_term))

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
            # special case: just a shelfmark query, in quotes
            quoted_shelfmark_query = re.fullmatch(
                rf'{re.escape(self.shelfmark_qf)}".+?"', search_term
            )
            if quoted_shelfmark_query:
                self.shelfmark_query = quoted_shelfmark_query.group(0)

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
        # if search term consists only of a shelfmark query in quotes, only search shelfmark fields
        if self.shelfmark_query:
            search = self.search(self.shelfmark_query)
        else:
            # otherwise, search all fields as usual
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

    def regex_search(self, field, search_term):
        """Build a Lucene query for searching with regular expressions.
        NOTE: this function may cause Lucene errors if input is not validated beforehand.
        """
        # surround passed query with wildcards to allow non-anchored matches,
        # and slashes so that it is interpreted as regex by Lucene;
        # except shelfmark, since shelfmark regex must match entire field
        match_any = ".*" if "shelfmark" not in field else ""
        search_term = f"/{match_any}{search_term}{match_any}/"
        # if this is shelfmark_regex, also search old_shelfmark_regex
        fields = [field] if "shelfmark" not in field else [field, f"old_{field}"]
        # match in the non-analyzed *_regex field
        search = self.search(" OR ".join([f"{f}:{search_term}" for f in fields]))
        return search

    def related_to(self, document):
        "Return documents related to the given document (i.e. shares any shelfmarks)"

        # NOTE: using a string query filter because parasolr queryset
        # currently doesn't provide any kind of not/exclude filter
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

    def get_regex_highlight(self, field, text):
        """Helper method to manually highlight and truncate a snippet for regex matches
        (automatic highlight unavailable due to solr regex search limitations)"""
        # remove solr field name and lucene-required "match all" logic to get original query
        regex_query = (
            self.search_qs[0].replace(f"{field}:/.*", "").rsplit(".*/", maxsplit=1)[0]
        )
        # get ~150 characters of context plus a word on either side of the matched portion
        pattern = r"(\b\w*.{0,150})(%s)(.{0,150}\w*\b)" % regex_query
        # find all matches in the snippet
        matches = re.findall(pattern, text, flags=re.DOTALL)
        # separate multiple matches by HTML line breaks and ellipsis
        separator = "<br />[…]<br />"
        # surround matched portion in <em> so it is visible in search results; join all into string
        joined_string = separator.join(
            [f"{m[0]}<em>{m[1]}</em>{m[-1]}" for m in matches if m]
        )
        if not matches:
            return None
        # highlight any matches in added context (excluding HTML elements <em> and <br />)
        additional_matches_query = (
            r"(?<!<em>)(?<!<)(?<!<\/)(%s)(?!>)(?!<\/em>)(?! \/>)" % regex_query
        )
        all_matches = re.sub(additional_matches_query, r"<em>\1</em>", joined_string)
        # ensure adjacent <em> elements with space between them can display properly
        return re.sub(r"<\/em> <em>", '</em> <em class="adjacent-em">', all_matches)

    def get_old_shelfmark_regex_highlight(self, doc, text):
        """Get any matches on the old_shelfmark_regex field, then join them by semicolon"""
        # extract regex query from solr query
        query = re.sub(r".*old_shelfmark_regex:/(.*)/", r"\1", text)
        # match only entire string to ensure highlight is the same as solr match
        return "; ".join(
            [s for s in doc.get("old_shelfmark_regex", []) if re.fullmatch(query, s)]
        )

    def get_highlights_and_labels(self, doc, regex_field):
        """For transcription_regex and translation_regex, which are multi-valued
        fields possibly pulling from multiple records, include citation label
        for each set of highlights."""
        return [
            {
                "text": highlight,
                "label": label,
            }
            # these fields are split by block-level annotation/group
            for (highlight, label) in (
                (
                    self.get_regex_highlight(regex_field, block),
                    # since the order of multivalued fields is stable in solr, we can
                    # map each entry of the names field to each entry of the text field
                    (
                        doc[f"{regex_field}_names"][i]
                        if f"{regex_field}_names" in doc
                        else None
                    ),
                )
                for i, block in enumerate(doc[regex_field])
            )
            # only include a block if it actually has highlights
            if highlight
        ]

    def dedupe_regex_labels(self, highlights):
        """Helper function to dedupe labels for labeled transcription and
        translation regex highlight results."""
        for field in ["transcription", "translation"]:
            last_label = None
            for snippet in highlights[field]:
                if snippet["label"] == last_label:
                    del snippet["label"]
                else:
                    last_label = snippet["label"]
        return highlights

    def get_highlighting(self):
        """highlight snippets within transcription/translation html may result in
        invalid tags that will render strangely; clean up the html before returning"""
        highlights = super().get_highlighting()
        is_regex_search = any("_regex" in q for q in self.search_qs)
        if is_regex_search:
            # highlight regex results manually due to solr limitation
            highlights = {}
            # highlighting takes place *after* solr, so use get_results()
            for doc in self.get_results():
                # highlight per document, keyed on id as expected in results
                highlights[doc["id"]] = {
                    # include labels in case of matches across multiple transcriptions
                    "transcription": (
                        self.get_highlights_and_labels(doc, "transcription_regex")
                        if "transcription_regex" in doc
                        else []
                    ),
                    "translation": (
                        self.get_highlights_and_labels(doc, "translation_regex")
                        if "translation_regex" in doc
                        else []
                    ),
                    "description": [
                        hl
                        for hl in (
                            self.get_regex_highlight("description_regex", block)
                            for block in doc.get("description_regex", [])
                        )
                        if hl
                    ],
                    "old_shelfmark": self.get_old_shelfmark_regex_highlight(
                        doc, self.search_qs[0]
                    ),
                }
                # dedupe labels
                highlights[doc["id"]] = self.dedupe_regex_labels(highlights[doc["id"]])
        else:
            is_exact_search = "hl_query" in self.raw_params
            for doc in highlights.keys():
                # _nostem fields should take precedence over stemmed fields in the case of an
                # exact search; in that case, replace highlights for stemmed fields with nostem
                if is_exact_search and "description_nostem" in highlights[doc]:
                    highlights[doc]["description"] = highlights[doc][
                        "description_nostem"
                    ]
                if is_exact_search and "transcription_nostem" in highlights[doc]:
                    highlights[doc]["transcription"] = [
                        {
                            "text": clean_html(s)
                            for s in highlights[doc]["transcription_nostem"]
                        }
                    ]
                elif "transcription" in highlights[doc]:
                    highlights[doc]["transcription"] = [
                        {
                            "text": clean_html(s)
                            for s in highlights[doc]["transcription"]
                        }
                    ]
                if "translation" in highlights[doc]:
                    highlights[doc]["translation"] = [
                        {"text": clean_html(s) for s in highlights[doc]["translation"]}
                    ]

                # handle old shelfmark highlighting; sometimes it's on one or the other
                # field, and sometimes one of the highlight results is empty
                if "old_shelfmark" in highlights[doc]:
                    highlights[doc]["old_shelfmark"] = "; ".join(
                        [h for h in highlights[doc]["old_shelfmark"] if h]
                    )
                elif "old_shelfmark_t" in highlights[doc]:
                    highlights[doc]["old_shelfmark"] = "; ".join(
                        [h for h in highlights[doc]["old_shelfmark_t"] if h]
                    )

        return highlights
