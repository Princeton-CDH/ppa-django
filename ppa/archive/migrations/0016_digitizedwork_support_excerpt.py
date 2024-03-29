# Generated by Django 2.2.19 on 2021-07-06 16:11

from django.db import migrations, models

import ppa.archive.models


class Migration(migrations.Migration):

    dependencies = [
        ("archive", "0015_digwork_gale_labels_helptext"),
    ]

    operations = [
        migrations.AddField(
            model_name="digitizedwork",
            name="book_journal",
            field=models.TextField(
                blank=True,
                help_text="title of the book or journal that includes this content (excerpt/article only)",
                verbose_name="Book/Journal title",
            ),
        ),
        migrations.AddField(
            model_name="digitizedwork",
            name="item_type",
            field=models.CharField(
                choices=[("F", "Full work"), ("E", "Excerpt"), ("A", "Article")],
                default="F",
                help_text="Portion of the work that is included; used to determine icon for public display.",
                max_length=1,
            ),
        ),
        migrations.AddField(
            model_name="digitizedwork",
            name="pages_digital",
            field=models.CharField(
                blank=True,
                help_text="Sequence of pages in the digital edition. Use full digits for start and end separated by a dash (##-##); for multiple sequences, separate ranges by a comma (##-##, ##-##).NOTE: removing page range may have unexpected results.",
                max_length=255,
                validators=[ppa.archive.models.validate_page_range],
                verbose_name="Page range (digital edition)",
            ),
        ),
        migrations.AddField(
            model_name="digitizedwork",
            name="pages_orig",
            field=models.CharField(
                blank=True,
                help_text="Page range in the original work (for display and citation).",
                max_length=255,
                verbose_name="Page range (original)",
            ),
        ),
    ]
