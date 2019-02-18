# -*- coding: utf-8 -*-
# Generated by Django 1.11.16 on 2019-02-18 19:31
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
import ppa.pages.models
import wagtail.core.blocks
import wagtail.core.fields
import wagtail.documents.blocks
import wagtail.images.blocks
import wagtail.snippets.blocks


class Migration(migrations.Migration):

    dependencies = [
        ('wagtailimages', '0021_image_file_hash'),
        ('pages', '0009_content_page_image_caption_footnotes'),
    ]

    operations = [
        migrations.AddField(
            model_name='person',
            name='image',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='wagtailimages.Image'),
        ),
        migrations.AlterField(
            model_name='contentpage',
            name='body',
            field=wagtail.core.fields.StreamField([('paragraph', wagtail.core.blocks.RichTextBlock()), ('image', wagtail.images.blocks.ImageChooserBlock()), ('captioned_image', wagtail.core.blocks.StructBlock([('image', wagtail.images.blocks.ImageChooserBlock()), ('caption', wagtail.core.blocks.RichTextBlock(features=['bold', 'italic', 'link']))])), ('footnotes', wagtail.core.blocks.RichTextBlock(classname='footnotes', features=['ol', 'ul', 'bold', 'italic', 'link'])), ('document', wagtail.documents.blocks.DocumentChooserBlock())]),
        ),
        migrations.AlterField(
            model_name='contributorpage',
            name='body',
            field=wagtail.core.fields.StreamField([('paragraph', wagtail.core.blocks.RichTextBlock()), ('image', wagtail.images.blocks.ImageChooserBlock()), ('captioned_image', wagtail.core.blocks.StructBlock([('image', wagtail.images.blocks.ImageChooserBlock()), ('caption', wagtail.core.blocks.RichTextBlock(features=['bold', 'italic', 'link']))])), ('footnotes', wagtail.core.blocks.RichTextBlock(classname='footnotes', features=['ol', 'ul', 'bold', 'italic', 'link'])), ('document', wagtail.documents.blocks.DocumentChooserBlock())], blank=True),
        ),
        migrations.AlterField(
            model_name='contributorpage',
            name='contributors',
            field=wagtail.core.fields.StreamField([('person', wagtail.snippets.blocks.SnippetChooserBlock(ppa.pages.models.Person))], blank=True, help_text='Select and order people to be listed as project         contributors.'),
        ),
    ]