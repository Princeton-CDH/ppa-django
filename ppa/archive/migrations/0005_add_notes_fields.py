# -*- coding: utf-8 -*-
# Generated by Django 1.11.16 on 2018-10-12 19:16
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('archive', '0004_digitizedwork_pubdate_to_integer'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='digitizedwork',
            options={'ordering': ('title',)},
        ),
        migrations.AddField(
            model_name='digitizedwork',
            name='notes',
            field=models.TextField(blank=True, help_text='Private notes not displayed on public site.'),
        ),
        migrations.AddField(
            model_name='digitizedwork',
            name='public_notes',
            field=models.TextField(blank=True, help_text='Public edition notes displayed on site.'),
        ),
    ]