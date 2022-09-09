# PGP scripts

This directory contains stand-alone scripts associated with
Princeton Geniza Project that are not part of the web application proper.

## IIIF

Scripts for generating and managing static iiif content (manifests and
iiif image api level 0 images) for import and display in PGP.

-   bodleian_iiif.py : generate iiif maniests from Bodleian TEI XML
-   tile_images.py : generate static image tiles; includes extra image sizes needed for PGP application
-   manifests_to_csv.py: generate a CSV file for importing IIIF urls into PGP

http://0.0.0.0:8001/bodleian/

### Bulk editing

If you need to make a bulk change to revise the base url for manifests or
image info files, you can use `sed` to edit in place. The syntax should look
something like this (recommend testing one or two records first):

```sh
sed -i '' 's|http://0.0.0.0:8001/bodleian/|https://princetongenizalab.github.io/iiif-bodleian-abc/|g' manifests/*.json
```
