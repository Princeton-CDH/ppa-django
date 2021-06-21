# Generated by Django 2.1.15 on 2020-01-09 16:51

from django.db import migrations

import ppa.archive.models


class Migration(migrations.Migration):

    dependencies = [
        ("archive", "0012_remove_publisher_character_limit"),
    ]

    operations = [
        migrations.AlterField(
            model_name="digitizedwork",
            name="protected_fields",
            field=ppa.archive.models.ProtectedWorkField(
                default=ppa.archive.models.ProtectedWorkFieldFlags,
                help_text="Fields protected from HathiTrust bulk update because they have been manually edited in the Django admin.",
            ),
        ),
    ]
