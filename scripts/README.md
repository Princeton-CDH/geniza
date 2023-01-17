# PGP scripts

This directory contains stand-alone scripts associated with
Princeton Geniza Project that are not part of the web application proper.

Requirements for these scripts can be found in `requirements/scripts.txt`.

## IIIF

Scripts for generating and managing static iiif content (manifests and
iiif image api level 0 images) for import and display in PGP.

-   bodleian_iiif.py : generate iiif maniests from Bodleian TEI XML
-   tile_images.py : generate static image tiles; includes extra image sizes needed for PGP application
-   manifests_to_csv.py: generate a CSV file for importing IIIF urls into PGP
-   jrl_iiif.py: generate remixed iiif maniests from Manchester JRL manifests

### Bulk editing

If you need to make a bulk change to revise the base url for manifests or
image info files, you can use `sed` to edit in place. The syntax should look
something like this (recommend testing one or two records first):

```sh
sed -i '' 's|http://0.0.0.0:8001/bodleian/|https://princetongenizalab.github.io/iiif-bodleian-a/|g' manifests/*.json
```

### Steps to generating content for a iiif Bodleian repo

-   Create new repo in princetongenizalab org with iiif-bodleian-template repository.

-   If desired/feasible, get all the original images; should be added to `images-orig`

-   Generate manifests from TEI XML. If images are not present in `images-orig`, they will be downloaded.

```sh
./scripts/bodleian_iiif.py ../genizah-mss/collections/MS_Heb_b_*.xml -d ../iiif-bodleian-b/ -u https://princetongenizalab.github.io/iiif-bodleian-b/
```

-   Generate tiles for all the images. This may take a while.

```sh
./scripts/tile_images.py -s bodleian/images_orig -d ../iiif-bodleian-b/iiif/images -u https://princetongenizalab.github.io/iiif-bodleian-b/
```

-   Check that you have all the images:

```sh
./scripts/bodleian_iiif.py --check-images -d ../iiif-bodleian-b/ ../genizah-mss/collections/MS_Heb_b_*.xml
```

-   Generate tiles for specific images if some are missing:

```sh
./scripts/tile_images.py bodleian/images_orig/MS_HEB_b_4_* -d ../iiif-bodleian-b/iiif/images -u https://princetongenizalab.github.io/iiif-bodleian-b/
```

-   If any images are still missing, document it in the readme.

-   Generate a CSV for import into PGP:

```sh
./scripts/manifests_to_csv.py -s ../iiif-bodleian-a/iiif/manifests/ -o iiif-bodleian-a.csv
```

-   Import the manifest and urls into the PGP database. Copy the csv to the server,
    and then load with manage command:

```sh
./manage.py add_fragment_urls -o /tmp/iiif-bodleian-a.csv
```

-   Check that images display on the public site using a shelfmark search, e.g. `shelfmark:"bodl ms heb a"`
