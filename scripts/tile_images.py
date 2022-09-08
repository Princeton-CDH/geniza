#! /usr/bin/env python

# Stand-alone python script to generate IIIF Image API level 0
# image tiles for static IIIF content.
#
# Install python dependencies with pip:
#
#   pip install iiif
#
# Script requires a destination directory where tile images should be
# placed and either a source image directory or a list of source image files.
#
#   python scripts/tile_images.py -d iiif-image-dir -s source-image-dir
#   python scripts/tile_images.py -d iiif-image-dir img1.jpg img2.jpg img2.jpg


import argparse
import glob
import os.path

from iiif.static import IIIFStatic, IIIFStaticError

# FIXME: placeholder url for dev
PUBLIC_URL = "http://0.0.0.0:8001/bodleian/"

base_path = os.path.join("bodleian")
manifest_dir = os.path.join(base_path, "manifests")
image_dir = os.path.join(base_path, "images_orig")

dest_dir = os.path.join(base_path, "iiif-images")
dest_url = PUBLIC_URL + "iiif-images/"


# any non-standard sizes needed for PGP application should be listed here
extra_iiif_sizes = [
    # doc details (multiple / responsive sizes)
    "full/300,/0/default.jpg",
    "full/500,/0/default.jpg",
    "full/640,/0/default.jpg",
    "full/1000,/0/default.jpg",
    "full/,200/0/default.jpg",  # admin thumbnail
    "full/250,/0/default.jpg",  # search result thumbnail
    "full/1080,/0/default.jpg",  # social media preview image
]


def generate_static_iiif(source_dir=None, dest_dir=dest_dir, source_files=None):

    # adapted from call in iiif_static command line script
    # using defaults option
    # dest_dir = os.path.join(base_path, "iiif-images")
    dest_url = PUBLIC_URL + "iiif-images/"
    # base destination url required for generating ids in info.json
    sg = IIIFStatic(dst=dest_dir, prefix=dest_url, extras=extra_iiif_sizes)

    # assume jpg for now, since that's what we need for bodleian images

    # if a directory is specified, run on all jpegs
    if source_dir is not None:
        source_files = glob.iglob(os.path.join(image_dir, "*.jpg"))
    # otherwise, run on list of source files passed in
    for source in source_files:
        # this is slow, so only generate if needed
        if not static_iiif_exists(source, dest_dir):
            print("Generating iiif tiles for %s" % source)
            sg.generate(source)


def static_iiif_exists(image, dest_dir):
    # static image identifier is file basename without extension
    identifier = os.path.splitext(os.path.basename(image))[0]

    # check for presence of info.json file (created last)
    return os.path.exists(os.path.join(dest_dir, identifier, "info.json"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="""Generate static IIIF image tiles from source images.
    Must specify a source directory or a list of files."""
    )
    parser.add_argument(
        "-s",
        "--src",
        metavar="SRC_DIR",
        help="directory of source images to be tiled",
    )
    parser.add_argument(
        "-d",
        "--dest",
        metavar="DEST_DIR",
        help="base directory where image tiles will be placed",
        required=True,
    )
    # optional list of files (instead of source dir)
    parser.add_argument("files", nargs="*")
    args = parser.parse_args()
    # make sure we have a source; if not, bail out
    if not args.src and not args.files:
        parser.print_help()
        exit(-1)

    generate_static_iiif(
        source_dir=args.src, dest_dir=args.dest, source_files=args.files
    )
