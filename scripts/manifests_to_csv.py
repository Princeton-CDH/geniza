#! /usr/bin/env python

# Stand-alone python script to generate a CSV file of IIIF manifest urls
# and shelfmarks, and optional view urls in a format suitable
# for import into PGP application using the add_fragment_urls manage command.
#
# Script requires a source directory of IIIF manifest files (currently
# assumes all json files in that directory are manifests) and a filename
# where the resulting csv file should be stored.  View urls are
# extracted from rendering attribute on the manifest, if present.
#
# Example use:
#
#   python scripts/manifests_to_csv.py -s manifests_dir -o iiif_urls.csv
#

import argparse
import csv
import glob
import json
import os.path
import re


def parse_manifests(source_dir, outfile):
    with open(outfile, "w") as f:
        csvwriter = csv.writer(f)
        csvwriter.writerow(["shelfmark", "iiif_url", "url", "orig_shelfmark"])

        for manifest_file in glob.iglob(
            os.path.join(source_dir, "**/*.json"), recursive=True
        ):
            with open(manifest_file) as mfile:
                manifest = json.load(mfile)
                iiif_url = manifest["@id"]
                # for bodleian manifests, we're putting it in the label;
                # in cudl it's in the metadata as a classmark (handle later if needed)
                shelfmark = manifest["label"]
                view_url = ""
                if "rendering" in manifest:
                    # NOTE: could be multiple; assume simple case for now
                    view_url = manifest["rendering"]["@id"]
                csvwriter.writerow(
                    [pgpize_shelfmark(shelfmark), iiif_url, view_url, shelfmark]
                )


bodl_shelfmark_re = re.compile(r"^MS\. (?P<group>Heb|Georg|Syr)\. (?P<letter>[a-g])\.")


def pgpize_shelfmark(shelfmark):
    bodl_prefixes = ["MS. Heb.", "MS. Georg.", "MS. Syr."]
    # convert bodleian shelfmark to PGP format
    if any([shelfmark.startswith(prefix) for prefix in bodl_prefixes]):
        # in PGP Bodleian shelfmarks have a Bodl. prefix,
        # MS heb portion is slightly different, and we don't use dots
        # after volume/series letter
        return bodl_shelfmark_re.sub(
            lambda m: f"Bodl. MS {m.group('group').lower()}. {m.group('letter')}",
            shelfmark,
        )

    # this JRL manifest series was labeled incorrectly when generated
    if shelfmark.startswith("JRL SERIES Ar. "):
        return shelfmark.replace("JRL SERIES Ar. ", "JRL Gaster Ar. ")

    return shelfmark


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="""Generate a CSV file from IIIF manifests suitable for import into PGP.
    Must specify a source directory."""
    )
    parser.add_argument(
        "-s",
        "--src",
        metavar="SRC_DIR",
        help="directory of manifests to be used as input",
        required=True,
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="CSVFILE",
        help="filename for CSV output",
        required=True,
    )
    args = parser.parse_args()
    parse_manifests(args.src, args.output)
