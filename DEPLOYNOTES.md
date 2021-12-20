# Deploy Notes

## 0.7

-   Update settings to configure **TEI_TRANSCRIPTIONS_LOCAL_PATH** for the deploy environment.
-   Run `python manage.py bootstrap_content -h HOSTNAME -p PORt` to create stub pages for all site content needed for main site navigation.
-   After running the boostrap content, in the Wagtail CMS, go to "Settings" -> "Locales" and choose each non-English language. Enable syncing to them from English. This should auto-populate each other locale with a new home page and set of subpages.
-   Run `python manage.py add_links` with a csv file exported from PGP v3 links database.
-   Run `python manage.py sync_transcriptions` to synchronize TEI transcription content to footnotes for search and display.
-   Solr indexing has changed significantly since the last release. All content should be reindexed: `python manage.py index`

## 0.3.0

-   Ensure that Django's default Site is configured with a valid hostname (e.g. test-geniza.cdh.princeton.edu)
-   Once the app has been deployed, execute the data import from Google Sheets using the `python manage.py import_data` command.
-   After the data import is complete, populate the search index using the `python manage.py index` command.
