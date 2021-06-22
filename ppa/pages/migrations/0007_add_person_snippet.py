# -*- coding: utf-8 -*-
# Generated by Django 1.11.16 on 2018-12-03 21:32
from __future__ import unicode_literals

import wagtail.core.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pages", "0006_contentpage_description"),
    ]

    operations = [
        migrations.CreateModel(
            name="Person",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        help_text="Full name for the person as it should appear in the author list.",
                        max_length=255,
                    ),
                ),
                (
                    "url",
                    models.URLField(
                        blank=True,
                        default="",
                        help_text="Personal website, profile page, or social media profile page for this person.",
                    ),
                ),
            ],
        ),
        migrations.AlterField(
            model_name="contentpage",
            name="description",
            field=wagtail.core.fields.RichTextField(
                blank=True,
                help_text="Optional. Brief description for preview display. Will also be used for search description (without tags), if one is not entered.",
            ),
        ),
    ]
