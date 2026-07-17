from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("archive", "0027_collection_adapter_name_collection_list_view_fields_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="digitizedwork",
            name="source",
            field=models.CharField(
                choices=[
                    ("HT", "HathiTrust"),
                    ("G", "Gale"),
                    ("E", "EEBO-TCP"),
                    ("IA", "Internet Archive"),
                    ("O", "Other"),
                ],
                default="HT",
                help_text="Source of the record.",
                max_length=2,
            ),
        ),
    ]
