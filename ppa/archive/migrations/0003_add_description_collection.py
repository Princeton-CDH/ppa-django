# -*- coding: utf-8 -*-
# Generated by Django 1.11.8 on 2018-01-24 20:48
from __future__ import unicode_literals

import wagtail.core.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("archive", "0002_add_collections_m2m"),
    ]

    operations = [
        migrations.AddField(
            model_name="collection",
            name="description",
            field=wagtail.core.fields.RichTextField(blank=True),
        ),
    ]
