# -*- coding: utf-8 -*-
# Generated by Django 1.11.16 on 2019-02-22 18:12
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("archive", "0011_add_protected_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="digitizedwork",
            name="publisher",
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name="digitizedwork",
            name="source_id",
            field=models.CharField(
                help_text="Source identifier. Unique identifier without spaces; used for site URL. (HT id for HathiTrust materials.)",
                max_length=255,
                unique=True,
                verbose_name="Source ID",
            ),
        ),
        migrations.AlterField(
            model_name="digitizedwork",
            name="source_url",
            field=models.URLField(
                blank=True,
                help_text="URL where the source item can be accessed",
                max_length=255,
                verbose_name="Source URL",
            ),
        ),
    ]
