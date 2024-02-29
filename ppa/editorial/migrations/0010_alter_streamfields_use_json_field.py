# Generated by Django 4.0.10 on 2024-01-31 18:31

from django.db import migrations
import ppa.pages.models
import wagtail.blocks
import wagtail.documents.blocks
import wagtail.embeds.blocks
import wagtail.fields
import wagtail.images.blocks
import wagtail.snippets.blocks


class Migration(migrations.Migration):
    dependencies = [
        ("editorial", "0009_editorialpage_doi_pdf_editors"),
    ]

    operations = [
        migrations.AlterField(
            model_name="editorialpage",
            name="authors",
            field=wagtail.fields.StreamField(
                [
                    (
                        "author",
                        wagtail.snippets.blocks.SnippetChooserBlock(
                            ppa.pages.models.Person
                        ),
                    )
                ],
                blank=True,
                help_text="Select or create people snippets to add as authors.",
                use_json_field=True,
            ),
        ),
        migrations.AlterField(
            model_name="editorialpage",
            name="body",
            field=wagtail.fields.StreamField(
                [
                    (
                        "paragraph",
                        wagtail.blocks.RichTextBlock(
                            features=[
                                "h2",
                                "h3",
                                "bold",
                                "italic",
                                "link",
                                "ol",
                                "ul",
                                "hr",
                                "blockquote",
                                "document",
                                "superscript",
                                "subscript",
                                "strikethrough",
                                "code",
                            ]
                        ),
                    ),
                    (
                        "captioned_image",
                        wagtail.blocks.StructBlock(
                            [
                                ("image", wagtail.images.blocks.ImageChooserBlock()),
                                (
                                    "alternative_text",
                                    wagtail.blocks.TextBlock(
                                        help_text="Alternative text for visually impaired users to\nbriefly communicate the intended message of the image in this context.",
                                        required=True,
                                    ),
                                ),
                                (
                                    "caption",
                                    wagtail.blocks.RichTextBlock(
                                        features=["bold", "italic", "link"],
                                        required=False,
                                    ),
                                ),
                                (
                                    "style",
                                    wagtail.blocks.ChoiceBlock(
                                        choices=[
                                            ("full", "Full Width"),
                                            ("left", "Floated Left"),
                                            ("right", "Floated Right"),
                                        ],
                                        help_text="Controls how other content flows around the image. Note         that this will only take effect on larger screens. Float consecutive         images in opposite directions for side-by-side display.",
                                    ),
                                ),
                            ],
                            label="image",
                        ),
                    ),
                    (
                        "svg_image",
                        wagtail.blocks.StructBlock(
                            [
                                (
                                    "image",
                                    wagtail.documents.blocks.DocumentChooserBlock(),
                                ),
                                (
                                    "alternative_text",
                                    wagtail.blocks.TextBlock(
                                        help_text="Alternative text for visually impaired users to\nbriefly communicate the intended message of the image in this context.",
                                        required=True,
                                    ),
                                ),
                                (
                                    "caption",
                                    wagtail.blocks.RichTextBlock(
                                        features=["bold", "italic", "link"],
                                        required=False,
                                    ),
                                ),
                                (
                                    "extended_description",
                                    wagtail.blocks.RichTextBlock(
                                        features=["p"],
                                        help_text="This text will only be read to     non-sighted users and should describe the major insights or     takeaways from the graphic. Multiple paragraphs are allowed.",
                                        required=False,
                                    ),
                                ),
                            ]
                        ),
                    ),
                    (
                        "footnotes",
                        wagtail.blocks.RichTextBlock(
                            features=["ol", "ul", "bold", "italic", "link"],
                            form_classname="footnotes",
                        ),
                    ),
                    ("document", wagtail.documents.blocks.DocumentChooserBlock()),
                    (
                        "linkable_section",
                        wagtail.blocks.StructBlock(
                            [
                                ("title", wagtail.blocks.CharBlock()),
                                (
                                    "anchor_text",
                                    wagtail.blocks.CharBlock(
                                        help_text="Short label for anchor link"
                                    ),
                                ),
                                ("body", wagtail.blocks.RichTextBlock()),
                            ]
                        ),
                    ),
                    ("embed", wagtail.embeds.blocks.EmbedBlock()),
                ],
                use_json_field=True,
            ),
        ),
        migrations.AlterField(
            model_name="editorialpage",
            name="editors",
            field=wagtail.fields.StreamField(
                [
                    (
                        "editor",
                        wagtail.snippets.blocks.SnippetChooserBlock(
                            ppa.pages.models.Person
                        ),
                    )
                ],
                blank=True,
                help_text="Select or create people snippets to add as editors.",
                use_json_field=True,
            ),
        ),
    ]