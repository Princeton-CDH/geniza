"""
Rename UPenn RAR MS fragments (82.313.x, 85.126.x, A1) to CAJS RAR MS and move
them to a CAJS collection, following the library's naming.
Run before ingesting existing.csv / new_rar.csv. Run from the Django shell.

For a dry run:
    DRY_RUN=true python manage.py shell < scripts/rename_upenn_rar.py

To commit changes:
    python manage.py shell < scripts/rename_upenn_rar.py

The previous shelfmark is kept in historical shelfmarks (see Fragment.save).
Prints the CAJS collection id for: add_fragment_urls --create --collection <id>
"""

import os

from django.conf import settings
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from geniza.corpus.models import Collection, Fragment

DRY_RUN = os.environ.get("DRY_RUN", "").lower() == "true"

# constants
CAJS_LIBRARY = "Katz Center for Advanced Judaic Studies, University of Pennsylvania"
OLD_PREFIX, NEW_PREFIX = "UPenn RAR MS ", "CAJS RAR MS "

print("=== %s ===" % ("DRY RUN: no changes saved" if DRY_RUN else "RUN"))
# use "script" user
script_user = User.objects.get(username=settings.SCRIPT_USERNAME)
fragment_ctype = ContentType.objects.get_for_model(Fragment)

# create the new CAJS collection if it doesn't exist
collection = Collection.objects.filter(library=CAJS_LIBRARY, name="").first()
if collection:
    print("Using collection %s (id %d)" % (collection.full_name, collection.pk))
elif DRY_RUN:
    print("Would create collection: %s (CAJS)" % CAJS_LIBRARY)
else:
    collection = Collection.objects.create(
        library=CAJS_LIBRARY, lib_abbrev="CAJS", location="Philadelphia"
    )
    print("Created collection %s (id %d)" % (collection.full_name, collection.pk))

# rename existing fragments; case-insensitive to include "Upenn RAR MS A1"
fragments = Fragment.objects.filter(shelfmark__istartswith=OLD_PREFIX)
print("%d fragments to rename" % fragments.count())
for fragment in fragments:
    old_shelfmark = fragment.shelfmark
    new_shelfmark = NEW_PREFIX + old_shelfmark[len(OLD_PREFIX) :]
    print("%s -> %s (%s -> CAJS)" % (old_shelfmark, new_shelfmark, fragment.collection))
    if DRY_RUN:
        continue
    # atomic transaction to allow rollback
    with transaction.atomic():
        fragment.shelfmark = new_shelfmark
        fragment.collection = collection
        fragment.save()
        LogEntry.objects.log_action(
            user_id=script_user.id,
            content_type_id=fragment_ctype.pk,
            object_id=fragment.pk,
            object_repr=str(fragment),
            change_message="Renamed from %s and moved to CAJS collection"
            % old_shelfmark,
            action_flag=CHANGE,
        )

if collection:
    print("\nCAJS collection id for new_rar.csv: --collection %d" % collection.pk)
