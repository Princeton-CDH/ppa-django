# -*- coding: utf-8 -*-
# Generated by Django 1.11.16 on 2019-02-21 20:30
from __future__ import unicode_literals

from django.db import migrations, models
import ppa.archive.models


class Migration(migrations.Migration):

    dependencies = [
        ('archive', '0010_digitizedwork_add_source'),
    ]

    operations = [
        migrations.AddField(
            model_name='digitizedwork',
            name='protected_fields',
            field=ppa.archive.models.ProtectedFlagsField(default=0, help_text='Fields protected from bulk update because they have been manually edited.'),
        ),
        migrations.AlterField(
            model_name='digitizedwork',
            name='source_id',
            field=models.CharField(help_text='Source identifier. Unique identifier without spaces; used for site URL. (HT id for HathiTrust materials.)', max_length=255, unique=True, verbose_name='Source ID'),
        ),
        migrations.AlterField(
            model_name='digitizedwork',
            name='source_url',
            field=models.URLField(blank=True, help_text='URL where the source item can be accessed', max_length=255, verbose_name='Source URL'),
        ),
    ]