# Generated by Django 3.1 on 2021-06-15 16:07

from django.db import migrations
from django.db.models import CharField
from django.db.models import Value as V
from django.db.models.functions import StrIndex, Substr


def split_goitein_typedtexts(apps, schema_editor):
    # after import from the metadata spreadsheet,
    # there were too many footnotes associated with the generic
    # unpublished source "Goitein, typed texts"
    # To make it manageable, segment that source into volumes
    # based on shelfmark prefixes

    Source = apps.get_model("footnotes", "Source")
    Footnote = apps.get_model("footnotes", "Footnote")
    Fragment = apps.get_model("corpus", "Fragment")
    Document = apps.get_model("corpus", "Document")

    # get the source with too many footnotes
    g_typedtexts = Source.objects.filter(
        title_en="typed texts", authors__last_name="Goitein", volume=""
    ).first()

    # bail out if nothing to do
    if not g_typedtexts:
        return
    footnotes = g_typedtexts.footnote_set.all()
    if not footnotes.exists():
        return
    # we can't use our generic relation from document to footnotes in
    # migration, so work with a list of document ids
    footnote_doc_ids = footnotes.values_list("object_id", flat=True)

    # get a list of shelfmark prefixes for all fragments associated
    # with documents that are linked to our source via footnote
    # For all but T-S, use string index & substring to get shelfmark
    # portion before the first space
    shelfmark_prefixes = set(
        Fragment.objects.filter(documents__id__in=footnote_doc_ids)
        .exclude(shelfmark__startswith="T-S")
        .annotate(
            prefix=Substr(
                "shelfmark",
                1,
                StrIndex("shelfmark", V(" ")) - 1,
                output_field=CharField(),
            )
        )
        .values_list("prefix", flat=True)
    )

    ts_prefixes = set(
        # for T-S shelfmarks, get first 6 characters of shelfmark
        Fragment.objects.filter(documents__id__in=footnote_doc_ids)
        .filter(shelfmark__startswith="T-S")
        .annotate(
            prefix=Substr("shelfmark", 1, 6, output_field=CharField()),
        )
        .values_list("prefix", flat=True)
    )
    # one exception: We want T-S Misc instead of T-S Mi
    ts_prefixes.remove("T-S Mi")
    ts_prefixes.add("T-S Misc")
    shelfmark_prefixes = shelfmark_prefixes.union(ts_prefixes)

    # create sources & footnote subsets for each prefix
    for prefix in shelfmark_prefixes:
        # create a new source with prefix as volume
        vol_source = Source.objects.create(
            title_en="typed texts", volume=prefix, source_type=g_typedtexts.source_type
        )
        # associate Goitein as author of the new source
        vol_source.authors.add(g_typedtexts.authors.first())
        # move footnotes for fragments with this prefix to the new source
        doc_ids = Document.objects.filter(
            id__in=footnote_doc_ids, fragments__shelfmark__startswith=prefix
        ).values_list("id", flat=True)

        updated = footnotes.filter(object_id__in=doc_ids).update(source=vol_source)


class Migration(migrations.Migration):

    dependencies = [
        ("footnotes", "0010_add_booksection_source_type"),
        ("corpus", "0015_add_document_date"),
    ]

    operations = [
        migrations.RunPython(split_goitein_typedtexts, migrations.RunPython.noop)
    ]
