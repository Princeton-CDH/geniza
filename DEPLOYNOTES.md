# Deploy Notes

## 0.3.0

* Ensure that Django's default Site is configured with a valid hostname (e.g. test-geniza.cdh.princeton.edu)
* Once the app has been deployed, execute the data import from Google Sheets using the `python manage.py import_data` command.
* After the data import is complete, populate the search index using the `python manage.py index` command.
