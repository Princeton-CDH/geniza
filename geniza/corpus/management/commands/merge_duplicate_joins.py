"""
To be run immediately after import_data. This script operates under the assumption
    that a user has not taken advantage of the unique features offered by the
    admin UI, but conforms to the expected format provided by the metadata spreadsheet.
"""
import csv
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db.models import Count

from geniza.corpus.models import Document


class Command(BaseCommand):
    """Merge documents that are variations of the same joins, based on
    shelfmark, document type, and description"""

    def add_arguments(self, parser):
        parser.add_argument("mode", choices=["report", "merge"])

    def get_merge_candidates(self):
        candidates = (
            Document.objects.annotate(fragment_count=Count("fragments", distinct=True))
            .filter(fragment_count__gt=1)
            .order_by("id")
        )
        print("%d documents with more than one fragment" % candidates.count())

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

        print("%d shelfmark/type groups" % len(joins.keys()))

        # remove any shelfmark groups with only one document
        joins = {key: value for (key, value) in joins.items() if len(value) > 1}
        print("%d shelfmark/type groups with at least one document" % len(joins.keys()))

        same_desc = 0
        report_rows = []

        for shelfmark_type, documents in joins.items():

            descriptions = defaultdict(list)
            for doc in documents:
                descriptions[doc.description.strip()].append(doc)
            # unique_descriptions = set([doc.description for doc in documents])
            unique_descriptions = descriptions.keys()
            primary_id = min([doc.id for doc in documents])  # maybe not
            status = action = ""

            # simple see join text without pgp id or shelfmark
            see_join = [
                "See join.",
                "See join for description.",
                "See join for description and transcription.",
            ]

            # all descriptions match; merge
            if len(unique_descriptions) == 1:
                same_desc += 1
                status = "all descriptions match"
                action = "MERGE"

            # simple see join: "see join" text without id, only
            # two unique descriptions
            elif (
                any(sj in unique_descriptions for sj in see_join)
                and len(unique_descriptions) == 2
            ):
                # get primary document based on description
                # (i.e., the one that is not "see join")
                non_join_descr = [
                    desc
                    for desc in unique_descriptions
                    if not desc.startswith("See join")
                ][0]

                non_join_docs = descriptions[non_join_descr]
                if len(non_join_docs) > 1:
                    print("### too many non-join documents")
                else:
                    primary_document = non_join_docs[0]
                    primary_id = primary_document.id
                    status = "see join"
                    action = "MERGE"

            # next: if there are fewer descriptions than documents,
            # some descriptions match; merge those?

            # next: check for "see join" / "see pgpid" wording
            # else:
            #     print([doc.id for doc in documents])
            #     print(unique_descriptions)

            for doc in documents:
                doc_status = ""
                if action == "MERGE":
                    if doc.id == primary_id:
                        doc_status = "primary"
                    else:
                        doc_status = "merge"
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

        print("\n%d groups with the same description" % same_desc)

        # output report of what would be done when mode is report
        if self.mode == "report":
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

    def merge_documents(doc_list):
        primary_doc = min(doc_list, lambda d: d.pgpid)
        merge_docs = [doc for doc in doc_list if doc != primary_doc]

        # add old ids
        for doc in merge_docs:
            primary_doc.add_old_pgpid(doc.pgpid)

        # compress description
        # confirm doctype the same
        # compress unique tags
        # confirm languages all the same
        # confirm probable_languages are fine
        # language_note
        # notes
        # drop created
        # drop last_modified
        # collapse footnotes
        # ignoring log entries, status, created, last_modified, needs_review

        # primary_doc.save()
        # for doc in merge_docs:
        #   doc.delete()

    def handle(self, *args, **options):
        self.mode = options["mode"]
        self.get_merge_candidates()
        # doc_groups = self.get_documents_with_multiple_joins()
        # for doc_list in doc_groups:
        #     merge_documents(doc_list)
