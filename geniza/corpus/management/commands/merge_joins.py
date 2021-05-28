"""
Report on or merge joins based on duplicate shelfmark combinations,
document type, and descriptions to remove redundant records needed
for data as tracked in the spreadsheet.

To generate a report of potential merges and actions to be taken::

    python manage.py. merge_joins report

"""
import csv
from collections import defaultdict
import re

from django.core.management.base import BaseCommand
from django.db.models import Count

from geniza.corpus.models import Document


class Command(BaseCommand):
    """Merge documents that are variations of the same joins, based on
    shelfmark, document type, and description"""

    def add_arguments(self, parser):
        parser.add_argument("mode", choices=["report", "merge"])

    def get_merge_candidates(self):
        """identify merge candidates from the database. Looks for documents
        associated with multiple fragments, and then groups documents by
        combination of sorted shelfmarks and document type. Returns a dictionary
        of candidates. Key is sorted shelfmark + type, value is list of
        documents in that group."""
        candidates = (
            Document.objects.annotate(fragment_count=Count("fragments", distinct=True))
            .filter(fragment_count__gt=1)
            .order_by("id")
        )
        self.stdout.write(
            "%d documents with more than one fragment" % candidates.count()
        )

        # make a dictionary to group documents by possible joins
        joins = defaultdict(list)
        for doc in candidates:
            # get a sorted version of the combined shelfmark
            sorted_shelfmark = " + ".join(
                sorted([fr.shelfmark for fr in doc.fragments.all()])
            )
            # combinie shelfmark with type so we don't try to join
            # documents with the same shelfmark but different types
            shelfmark_type = " / ".join(
                [sorted_shelfmark, (doc.doctype.name if doc.doctype else "Unknown")]
            )
            # add this document to the list for that shelfmark
            joins[shelfmark_type].append(doc)

        # remove any shelfmark groups with only one document
        joins = {key: value for (key, value) in joins.items() if len(value) > 1}
        self.stdout.write(
            "%d shelfmark/type groups with at least two documents" % len(joins.keys())
        )

        return joins

    # simple see join text without pgp id or shelfmark
    see_join = [
        "See join.",
        "See join for description.",
        "See join for description and transcription.",
        "See join. (Join is from FGP cataloguing information.)",
    ]

    # some join descriptions reference primary document by PGPID
    # (may include other information)
    re_see_pgpid = re.compile(r"See .*PGPID (?P<pgpid>\d+)")

    def group_merge_candidates(self, joins):
        """process candidates identified in :meth:`get_merge_candidates`
        to determine which ones should be merged"""
        same_desc = 0

        # TODO: group documents to merge into a structure that can be
        # used for reporting OR to do the actual merge
        # should include primary document, merge rationale, merge documents
        report_rows = []
        for shelfmark_type, documents in joins.items():

            descriptions = defaultdict(list)
            for doc in documents:
                descriptions[doc.description.strip()].append(doc)
            # unique_descriptions = set([doc.description for doc in documents])
            unique_descriptions = descriptions.keys()
            primary_id = min([doc.id for doc in documents])  # maybe not
            status = action = ""

            # all descriptions match; merge
            # FIXME: some cases where all descriptions match but refer
            # to another document NOT in this shelfmark group
            if len(unique_descriptions) == 1:
                same_desc += 1
                status = "all descriptions match"
                action = "MERGE"

            # one description, with all others empty
            elif "" in unique_descriptions and len(unique_descriptions) == 2:
                print("### single description and others empty")
                primary_docs = [doc for doc in documents if doc.description]
                # if there's more than one non-join description,
                # can't identify the primary document
                if len(primary_docs) > 1:
                    print("### can't identify primary document")
                else:
                    primary_document = primary_docs[0]
                    primary_id = primary_document.id
                    status = "one description, others empty"
                    action = "MERGE"

            # simple see join: one description matches "see join" text variant
            # (no PGPID/shelfmark specified), and there are only two unique
            # descriptions (i.e., primary document with description and a join)
            elif (
                any(sj in unique_descriptions for sj in self.see_join)
                and len(unique_descriptions) == 2
            ):
                # get primary document based on description
                # (i.e., the one that is not "see join")
                primary_docs = [
                    doc
                    for doc in documents
                    if not doc.description.startswith("See join")
                ]
                # if there's more than one non-join description,
                # can't identify the primary document
                if len(primary_docs) > 1:
                    print("### can't identify primary document")
                else:
                    primary_document = primary_docs[0]
                    primary_id = primary_document.id
                    status = "see join"
                    action = "MERGE"

            else:
                # check for "see join" with pgpid specified
                possible_primaries = set()
                group_ids = [doc.id for doc in documents]
                for doc in documents:
                    pgpid_match = self.re_see_pgpid.match(doc.description)
                    if pgpid_match:
                        print("*** pgpid match: %s" % pgpid_match.groupdict()["pgpid"])
                        print(doc.id, doc.description)
                        possible_primaries.add(int(pgpid_match.groupdict()["pgpid"]))

                if possible_primaries:
                    if len(possible_primaries) == 1:
                        primary = list(possible_primaries)[0]
                        if primary in group_ids:
                            primary_id = primary
                            status = "see PGPID"
                            action = "MERGE"
                        elif primary not in group_ids:
                            print(shelfmark_type)
                            print(documents)
                            print("### primary id %s not in group" % primary)

                    else:
                        print(shelfmark_type)
                        print(documents)
                        print(
                            "### more than one possible primary id: %s"
                            % possible_primaries
                        )

                # also possible: see shelfmark

            # other possibilities: if a subset of documents in a group match
            # based on description, should they be merged?
            for doc in documents:
                doc_status = ""
                if action == "MERGE":
                    if doc.id == primary_id:
                        doc_status = "primary"
                    else:
                        doc_status = "merge"

                # keep track of status / action for report output
                report_rows.append(
                    [
                        shelfmark_type,
                        action,
                        status,
                        doc_status,
                        doc.id,
                        doc.description,
                    ]
                )

        self.stdout.write("%d groups with the same description" % same_desc)

        if self.mode == "report":
            self.generate_report(report_rows)

    def generate_report(self, report_rows):
        # output report of what would be done when in report mode

        with open("merge-report.csv", "w") as csvfile:
            csvwriter = csv.writer(csvfile)
            csvwriter.writerow(
                [
                    "merge group",
                    "action",
                    "status",
                    "role",
                    "pgpid",
                    "description",
                ]
            )
            csvwriter.writerows(report_rows)
        self.stdout.write("Report of merge candidates output as merge-report.csv")

    def merge_documents(primary_doc, merge_docs, rationale):
        # takes a primary document, list of documents to merge
        # and a rationale/description for how the merge was determined
        for doc in merge_docs:
            # add merge ids to primary doc old pgpid list
            primary_doc.old_pgpids.append(doc.pgpid)
            # add any merge document tags to primary document
            primary_doc.tags.add(*doc.tags)

        # combine descriptions (if necessary)
        # confirm languages all the same
        # confirm probable_languages are fine
        # language_note
        # combine notes
        # combine needs review notes, if any
        # combine footnotes; delete any that are redundant
        # remove redundant log entries; move any unique entries to primary doc

        # primary_doc.save()
        # for doc in merge_docs:
        #   doc.delete()
        # create log entry documenting the merge; include rationale

    def handle(self, *args, **options):
        self.mode = options["mode"]
        possible_joins = self.get_merge_candidates()
        self.group_merge_candidates(possible_joins)
        # doc_groups = self.get_documents_with_multiple_joins()
        # for doc_list in doc_groups:
        #     merge_documents(doc_list)
