# PGP scripts

This directory contains stand-alone scripts associated with
Princeton Geniza Project that are not part of the web application proper.

Requirements for these scripts can be found in `scripts/scripts_requirements.txt`.

## IIIF

Scripts for generating and managing static iiif content (manifests and
iiif image api level 0 images) for import and display in PGP.

-   bodleian_iiif.py : generate iiif maniests from Bodleian TEI XML
-   tile_images.py : generate static image tiles; includes extra image sizes needed for PGP application
-   gen_ptiffs.py: generate pyramidal TIFFs from image files
-   manifests_to_csv.py: generate a CSV file for importing IIIF urls into PGP
-   jrl_iiif.py: generate remixed iiif maniests from Manchester JRL manifests

### Bulk editing

If you need to make a bulk change to revise the base url for manifests or
image info files, you can use `sed` to edit in place. The syntax should look
something like this (recommend testing one or two records first):

```sh
sed -i '' 's|http://0.0.0.0:8001/bodleian/|https://princetongenizalab.github.io/iiif/bodleian/|g' manifests/*.json
```

### Steps to generating content for a iiif Bodleian repo

-   Clone the princetongenizalab/iiif and bodleian/genizah-mss repositories.

-   Follow the documentation in bodleian_iiif.py to download images.

-   Generate pyramidal TIFFs for all the images. This may take a while.

```sh
./scripts/gen_ptiffs.py -s /path/to/originals -d /path/to/tiffs
```

-   Check that you have all the images:

```sh
./scripts/bodleian_iiif.py --check-images -i /path/to/originals -t /path/to/tiffs ../genizah-mss/collections/*.xml
```

-   If any images are missing, document them in the princetongenizalab/iiif repository, in the bodleian directory readme.

-   Upload pyramidal tiffs to the IIIF image server.

-   Run the bodleian script again to generate manifests based on the response from the IIIF server.

```sh
./scripts/bodleian_iiif.py -d ../iiif/bodleian -i /path/to/originals -u https://princetongenizalab.github.io/iiif/bodleian/ ../genizah-mss/collections/*.xml
```

-   Generate a CSV for import into PGP:

```sh
./scripts/manifests_to_csv.py -s ../iiif/bodleian/ -o ../iiif/bodleian/pgp-bodleian-manifests.csv
```

-   Import the manifest and urls into the PGP database. Copy the csv to the server,
    and then load with manage command:

```sh
./manage.py add_fragment_urls -o /tmp/pgp-bodleian-manifests.csv
```

-   Check that images display on the public site using a shelfmark search, e.g. `shelfmark:"bodl ms heb a"`

#### Handling skipped folios in Bodleian TEI

Sometimes, Bodleian TEI skips folios even though they have images, such as MS Heb. c 13/3. In these cases, you can add them to `skipped_folio_shelfmarks` in `bodleian_iiif.py` and provide the range of folio numbers that should actually be included for a given Bodleian shelfmark.

In the case of MS Heb. c 13/3, that Bodleian shelfmark points to folio 4, but we also need folio 3, so its entry in `skipped_folio_shelfmarks` is `[3, 4]`.
