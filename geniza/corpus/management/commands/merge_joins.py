"""
Report on or merge joins based on duplicate shelfmark combinations,
document type, and descriptions to remove redundant records needed
for data as tracked in the spreadsheet.

To generate a report of potential merges and actions to be taken::

    python manage.py. merge_joins report

"""
import csv
from collections import defaultdict
import itertools
import operator
import re

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count

from geniza.corpus.models import Document


class Command(BaseCommand):
    """Merge documents that are variations of the same joins, based on
    shelfmark, document type, and description"""

    def add_arguments(self, parser):
        parser.add_argument("mode", choices=["report", "merge"])
        parser.add_argument("path", type=str, nargs="?", default="merge-report.csv")

    def handle(self, *args, **options):
        mode = options["mode"]

        if mode == "report":
            possible_joins = self.get_merge_candidates()
            merge_groups = self.group_merge_candidates(possible_joins)
            self.generate_report(merge_groups, options["path"])

        elif mode == "merge":
            merge_groups = self.load_report(options["path"])
            success = 0
            group_count = 0
            for group_id, group in merge_groups:
                success += self.merge_group(group_id, list(group))
                group_count += 1
            self.stdout.write(
                "Successfully merged %d groups; skipped %d"
                % (success, (group_count - success))
            )

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
            # combine shelfmark with type so we don't try to join
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
        group_id = 1

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
                        group_id,
                        action,
                        status,
                        doc_status,
                        doc.id,
                        doc.description,
                    ]
                )

            group_id += 1

        self.stdout.write("%d groups with the same description" % same_desc)
        return report_rows

    def generate_report(self, report_rows, path):
        # output report of what would be done when in report mode
        with open(path, "w") as csvfile:
            csvwriter = csv.writer(csvfile)
            csvwriter.writerow(
                [
                    "merge group",
                    "group id",
                    "action",
                    "status",
                    "role",
                    "pgpid",
                    "description",
                ]
            )
            csvwriter.writerows(report_rows)
        self.stdout.write(f"Report of merge candidates output as {path}")

    def load_report(self, path):
        """Load a report .csv file and generate list of merge groups."""
        try:
            with open(path, encoding="utf8") as csvfile:
                csvreader = csv.DictReader(csvfile)
                records = [row for row in csvreader if row["action"] == "MERGE"]
        except FileNotFoundError:
            raise CommandError(f"Report file not found: {path}")

        self.stdout.write(f"Loaded {len(records)} merge rows from {path}")
        return itertools.groupby(records, lambda x: x["group id"])

    def merge_group(self, group_id, group):
        """Takes a group identifier and a list of dicts for the group;
        there should be one primary record (role = primary) and one or more
        non-primary records. Each entry should have a pgpid; the
        status from the primary record will be used as merge rationale.
        Will find and merge the documents if possible."""
        primary_rows = [row for row in group if row["role"] == "primary"]
        merge_ids = [int(row["pgpid"]) for row in group if row["role"] != "primary"]

        error_msg = None

        # check that we have sufficient group data, or bail out
        if not primary_rows or len(primary_rows) > 1:
            error_msg = "Could not identify primary document for group %s" % group_id
        elif not merge_ids:
            error_msg = "No merge documents in group %s" % group_id
        if error_msg:
            self.stderr.write(error_msg)
            return 0

        primary_row = primary_rows[0]
        primary_doc = Document.objects.filter(pk=int(primary_row["pgpid"])).first()
        merge_docs = Document.objects.filter(pk__in=merge_ids)
        # check that group data matches database records
        if not primary_doc:
            error_msg = "Primary document %s not found" % primary_row["pgpid"]
        elif len(merge_docs) != len(merge_ids):
            error_msg = (
                "Not all merge documents found for group %s (expected %d, found %d)"
                % (group_id, len(merge_ids), len(merge_docs))
            )
        if error_msg:
            self.stderr.write(error_msg)
            return 0

        primary_doc.merge_with(merge_docs, primary_row["status"])
        return 1  # successfully merged
