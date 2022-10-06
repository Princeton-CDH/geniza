#! /usr/bin/env python

# Conviience script to generate pyramidal tiffs with vips
# for use in IIIF image server.
#
# Must have vips command line tool installed.
#
# Script requires a destination directory where tile images should be
# placed and either a source image directory or a list of source image files.
#
#   python scripts/tile_images.py -d iiif-image-dir -s source-image-dir
#   python scripts/tile_images.py -d iiif-image-dir img1.jpg img2.jpg img2.jpg


import argparse
import glob
import os.path
from os import system

from rich.progress import MofNCompleteColumn, Progress


def generate_ptiffs(dest_dir, source_dir=None, source_files=None):

    # if a directory is specified, run on all jpegs
    if source_dir is not None:
        source_files = glob.glob(os.path.join(source_dir, "**.jpg"), recursive=True)

    # make sure dest dir exists
    if not os.path.isdir(dest_dir):
        print("Destination does not exist, creating %s" % dest_dir)
        os.mkdir(dest_dir)

    # otherwise, run on list of source files passed in
    with Progress(
        MofNCompleteColumn(), *Progress.get_default_columns(), expand=True
    ) as progress:
        task = progress.add_task("Converting...", total=len(source_files))

        for source in source_files:
            basename = os.path.splitext(os.path.basename(source))[0]
            # print(basename)

            dest_file = os.path.join(dest_dir, "%s.tif" % basename)
            # this is slow, so only generate if needed
            if not os.path.exists(dest_file):
                # NOTE: using quotes to escape parens in some filenames
                cmd = (
                    "env VIPS_WARNING=0 vips tiffsave '%s' '%s' --tile --pyramid --compression jpeg --tile-width 256 --tile-height 256"
                    % (source, dest_file)
                )
                system(cmd)

            progress.update(task, advance=1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="""Generate pyramidal tiff images images.
    Must specify a source directory or a list of files."""
    )
    parser.add_argument(
        "-d",
        "--dest",
        metavar="DEST_DIR",
        help="base directory where image tiles will be placed",
        default="tiff",
        required=True,
    )
    parser.add_argument(
        "-s",
        "--src",
        metavar="SRC_DIR",
        help="directory of source images to be tiled",
    )
    # optional list of files (instead of source dir)
    parser.add_argument("files", nargs="*")
    args = parser.parse_args()
    # make sure we have a source; if not, bail out
    if not args.src and not args.files:
        parser.print_help()
        exit(-1)

    generate_ptiffs(
        dest_dir=args.dest,
        source_dir=args.src,
        source_files=args.files,
    )
