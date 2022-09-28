#!/usr/bin/env python

# one-off script to crawl JRL's IIIF collection of Genizah materials
# and generate a CSV to use for generating manifests for PGP


import csv

from piffle.presentation import IIIFPresentation
from ratelimit import limits
from rich.progress import Progress

# based on response headers:
# RateLimit-Limit: 5.0
# Ratelimit-Reset: 1
# looks like they don't want more than 5 requests per second


@limits(calls=5, period=1)
def get_manifest(url):
    return IIIFPresentation.from_url(url)


with open("jrl_iiif.csv", "a") as csvfile:
    csvwriter = csv.writer(csvfile)
    # if appending, don't rewrite headers (continuing interrupted run)
    # csvwriter.writerow(["shelfmark", "iiif_url", "view_url"])

    with Progress(expand=True) as progress:
        # icoll = IIIFPresentation.from_url(
        # "https://luna.manchester.ac.uk/luna/servlet/iiif/collection/s/w96uk8"
        # )
        # icoll = get_manifest(
        #     "https://luna.manchester.ac.uk/luna/servlet/iiif/collection/s/w96uk8"
        # )
        total = 27696  # set manually for re-run
        # crawl_task = progress.add_task("Gathering...", total=icoll.total)
        crawl_task = progress.add_task("Gathering...", total=total)

        # nextcoll = icoll.first

        # at some point, even with rate limiting, we get a 500 error;
        # rerun to append starting at the last page completed;

        # got a 500 error on page 520 of the collection; start up there again
        nextcoll = (
            "https://luna.manchester.ac.uk/luna/servlet/iiif/collection/s/w96uk8/520"
        )
        # appending will result in some duplicates in the csv; clean them up later
        # if doing this, use startIndex to advance progress bar to current chunk
        progress.update(crawl_task, advance=26000)  #

        while nextcoll:
            # curcoll = IIIFPresentation.from_url(nextcoll)
            curcoll = get_manifest(nextcoll)

            print("{} {}".format(curcoll.id, curcoll.label))
            # collection has a list of manifests
            for m in curcoll.manifests:
                # id is manifest uri
                # print(m.id)
                # manifest = IIIFPresentation.from_url(m.id)

                manifest = get_manifest(m.id)

                # metadata is on the first canvas; shelfmark is labeled as "Reference number"
                shelfmark = [
                    v.value
                    for v in manifest.sequences[0].canvases[0].metadata
                    if v.label == "Reference number"
                ][0]
                # view url is related link
                csvwriter.writerow([shelfmark, manifest.id, manifest.related])

                progress.update(crawl_task, advance=1)

            nextcoll = getattr(curcoll, "next", None)
