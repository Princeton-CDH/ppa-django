# -*- coding: utf-8 -*-
# Generated by Django 1.11.21 on 2019-12-20 14:42
from __future__ import unicode_literals

from django.db import migrations
import wagtail.core.blocks
import wagtail.core.fields
import wagtail.documents.blocks
import wagtail.embeds.blocks
import wagtail.images.blocks


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0010_add_image_person'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contentpage',
            name='body',
            field=wagtail.core.fields.StreamField([('paragraph', wagtail.core.blocks.RichTextBlock(features=['h2', 'h3', 'bold', 'italic', 'link', 'ol', 'ul', 'hr', 'blockquote', 'document'])), ('captioned_image', wagtail.core.blocks.StructBlock([('image', wagtail.images.blocks.ImageChooserBlock()), ('alternative_text', wagtail.core.blocks.TextBlock(help_text='Alternative text for visually impaired users to\nbriefly communicate the intended message of the image in this context.', required=True)), ('caption', wagtail.core.blocks.RichTextBlock(features=['bold', 'italic', 'link'], required=False)), ('style', wagtail.core.blocks.ChoiceBlock(choices=[('full', 'Full Width'), ('left', 'Floated Left'), ('right', 'Floated Right')], help_text='Controls how other content flows around the image. Note         that this will only take effect on larger screens. Float consecutive         images in opposite directions for side-by-side display.'))], label='image')), ('footnotes', wagtail.core.blocks.RichTextBlock(classname='footnotes', features=['ol', 'ul', 'bold', 'italic', 'link'])), ('document', wagtail.documents.blocks.DocumentChooserBlock()), ('embed', wagtail.embeds.blocks.EmbedBlock())]),
        ),
        migrations.AlterField(
            model_name='contributorpage',
            name='body',
            field=wagtail.core.fields.StreamField([('paragraph', wagtail.core.blocks.RichTextBlock(features=['h2', 'h3', 'bold', 'italic', 'link', 'ol', 'ul', 'hr', 'blockquote', 'document'])), ('captioned_image', wagtail.core.blocks.StructBlock([('image', wagtail.images.blocks.ImageChooserBlock()), ('alternative_text', wagtail.core.blocks.TextBlock(help_text='Alternative text for visually impaired users to\nbriefly communicate the intended message of the image in this context.', required=True)), ('caption', wagtail.core.blocks.RichTextBlock(features=['bold', 'italic', 'link'], required=False)), ('style', wagtail.core.blocks.ChoiceBlock(choices=[('full', 'Full Width'), ('left', 'Floated Left'), ('right', 'Floated Right')], help_text='Controls how other content flows around the image. Note         that this will only take effect on larger screens. Float consecutive         images in opposite directions for side-by-side display.'))], label='image')), ('footnotes', wagtail.core.blocks.RichTextBlock(classname='footnotes', features=['ol', 'ul', 'bold', 'italic', 'link'])), ('document', wagtail.documents.blocks.DocumentChooserBlock()), ('embed', wagtail.embeds.blocks.EmbedBlock())], blank=True),
        ),
    ]
