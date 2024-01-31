import bleach
from django.db import models
from django.template.defaultfilters import striptags, truncatechars_html
from django.utils.text import slugify
from wagtail.admin.panels import FieldPanel
from wagtail import blocks
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Page
from wagtail.documents.blocks import DocumentChooserBlock
from wagtail.embeds.blocks import EmbedBlock
from wagtail.images.blocks import ImageChooserBlock
from wagtail.images.models import Image
from wagtail.snippets.blocks import SnippetChooserBlock
from wagtail.snippets.models import register_snippet

from ppa.archive.models import Collection


@register_snippet
class Person(models.Model):
    """Common model for a person, currently used to document authorship for
    instances of :class:`ppa.editorial.models.EditorialPage`."""

    #: the display name of an individual
    name = models.CharField(
        max_length=255,
        help_text="Full name for the person as it should appear in the author list.",
    )
    #: Optional profile image to be associated with a person
    photo = models.ForeignKey(
        Image,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        help_text="Image to use as a profile photo for a person, "
        "displayed on contributor list.",
    )
    #: identifying URI for a person (VIAF, ORCID iD, personal website, etc.)
    url = models.URLField(
        blank=True,
        default="",
        help_text="Personal website, profile page, or social media profile page "
        "for this person.",
    )
    #: description (affiliation, etc.)
    description = RichTextField(
        blank=True,
        features=["bold", "italic"],
        help_text="Title & affiliation, or other relevant context.",
    )

    #: project role
    project_role = models.CharField(
        max_length=255,
        blank=True,
        help_text="Project role, if any, for display on contributor list.",
    )
    #: project years
    project_years = models.CharField(
        max_length=255,
        blank=True,
        help_text="Project years, if desired for display on contributor list.",
    )
    orcid = models.URLField(
        "ORCID iD",
        max_length=255,
        blank=True,
        help_text="ORCID url, if available, to include in editorial author citation",
    )

    panels = [
        FieldPanel("name"),
        FieldPanel("photo"),
        FieldPanel("url"),
        FieldPanel("description"),
        FieldPanel("project_role"),
        FieldPanel("project_years"),
        FieldPanel("orcid"),
    ]

    def __str__(self):
        return self.name


class HomePage(Page):
    """:class:`wagtail.models.Page` model for PPA home page"""

    body = RichTextField(blank=True)

    page_preview_1 = models.ForeignKey(
        "wagtailcore.Page",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="First page to preview on the home page as a card",
    )
    page_preview_2 = models.ForeignKey(
        "wagtailcore.Page",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Second page to preview on the home page as card",
    )

    content_panels = Page.content_panels + [
        FieldPanel("page_preview_1"),
        FieldPanel("page_preview_2"),
        FieldPanel("body", classname="full"),
    ]

    # only generic parent page allowed, so homepage can be created under
    # Root but not otherwise used as a child page
    parent_page_types = [Page]

    class Meta:
        verbose_name = "homepage"

    def get_context(self, request):
        """Add collections with stats and previews for content pages to
        template context."""
        context = super().get_context(request)

        preview_pages = [
            page for page in [self.page_preview_1, self.page_preview_2] if page
        ]

        # if no preview pages are associated, look for history and prosody
        # by slug url (preliminary urls!)
        if not preview_pages:
            preview_pages = ContentPage.objects.filter(slug__in=["history", "prosody"])

        # grab collection page for displaying collection overview
        collection_page = CollectionPage.objects.live().first()

        # include 2 random collections
        # along with stats for all collections
        context.update(
            {
                "collections": Collection.objects.order_by("?")[:2],
                "stats": Collection.stats(),
                "preview_pages": preview_pages,
                "collection_page": collection_page,
            }
        )
        return context


#: help text for image alternative text
ALT_TEXT_HELP = """Alternative text for visually impaired users to
briefly communicate the intended message of the image in this context."""


class ImageWithCaption(blocks.StructBlock):
    """:class:`~wagtail.blocks.StructBlock` for an image with
    a formatted caption, so caption can be context-specific. Also allows images
    to be floated right, left, or take up the width of the page."""

    image = ImageChooserBlock()
    alternative_text = blocks.TextBlock(required=True, help_text=ALT_TEXT_HELP)
    caption = blocks.RichTextBlock(required=False, features=["bold", "italic", "link"])
    style = blocks.ChoiceBlock(
        required=True,
        default="full",
        choices=[
            ("full", "Full Width"),
            ("left", "Floated Left"),
            ("right", "Floated Right"),
        ],
        help_text="Controls how other content flows around the image. Note \
        that this will only take effect on larger screens. Float consecutive \
        images in opposite directions for side-by-side display.",
    )

    class Meta:
        icon = "image"
        template = "pages/blocks/image_caption_block.html"


class SVGImageBlock(blocks.StructBlock):
    """:class:`~wagtail.blocks.StructBlock` for an SVG image with
    alternative text and optional formatted caption. Separate from
    :class:`CaptionedImageBlock` because Wagtail image handling
    does not work with SVG."""

    extended_description_help = """This text will only be read to \
    non-sighted users and should describe the major insights or \
    takeaways from the graphic. Multiple paragraphs are allowed."""

    image = DocumentChooserBlock()
    alternative_text = blocks.TextBlock(required=True, help_text=ALT_TEXT_HELP)
    caption = blocks.RichTextBlock(features=["bold", "italic", "link"], required=False)
    extended_description = blocks.RichTextBlock(
        features=["p"], required=False, help_text=extended_description_help
    )

    class Meta:
        icon = "image"
        label = "SVG"
        template = "pages/blocks/svg_image_block.html"


class LinkableSectionBlock(blocks.StructBlock):
    """:class:`~wagtail.blocks.StructBlock` for a rich text block and an
    associated `title` that will render as an <h2>. Creates an anchor (<a>)
    so that the section can be directly linked to using a url fragment."""

    title = blocks.CharBlock()
    anchor_text = blocks.CharBlock(help_text="Short label for anchor link")
    body = blocks.RichTextBlock()
    panels = [
        FieldPanel("title"),
        FieldPanel("slug"),
        FieldPanel("body"),
    ]

    class Meta:
        icon = "form"
        label = "Linkable Section"
        template = "pages/blocks/linkable_section.html"

    def clean(self, value):
        cleaned_values = super().clean(value)
        # run slugify to ensure anchor text is a slug
        cleaned_values["anchor_text"] = slugify(cleaned_values["anchor_text"])
        return cleaned_values


class BodyContentBlock(blocks.StreamBlock):
    """Common set of content blocks to be used on both content pages
    and editorial pages"""

    paragraph = blocks.RichTextBlock(
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
    )
    captioned_image = ImageWithCaption(label="image")  # lavel as image
    svg_image = SVGImageBlock()
    footnotes = blocks.RichTextBlock(
        features=["ol", "ul", "bold", "italic", "link"], classname="footnotes"
    )
    document = DocumentChooserBlock()
    linkable_section = LinkableSectionBlock()
    embed = EmbedBlock()


class PagePreviewDescriptionMixin(models.Model):
    """Page mixin with logic for page preview content. Adds an optional
    richtext description field, and methods to get description and plain-text
    description, for use in previews on the site and plain-text metadata
    previews."""

    description = RichTextField(
        blank=True,
        help_text="Optional. Brief description for preview display. Will "
        + "also be used for search description (without tags), if one is not entered.",
        features=["bold", "italic"],
    )

    #: maximum length for description to be displayed
    max_length = 250

    # ('a' is omitted by subsetting and p is added to default ALLOWED_TAGS)
    #: allowed tags for bleach html stripping in description
    allowed_tags = list((set(bleach.sanitizer.ALLOWED_TAGS) | set(["p"])) - set(["a"]))

    class Meta:
        abstract = True

    def get_description(self):
        """Get formatted description for preview. Uses description field
        if there is content, otherwise uses the beginning of the body content."""

        description = ""

        # use description field if set
        # use striptags to check for empty paragraph)
        if striptags(self.description):
            description = self.description

        # if not, use beginning of body content
        else:
            # Iterate over blocks and use content from the first paragraph content
            for block in self.body:
                if block.block_type == "paragraph":
                    description = block
                    # break so we stop after the first instead of using last
                    break

        description = bleach.clean(str(description), tags=self.allowed_tags, strip=True)
        # truncate either way
        return truncatechars_html(description, self.max_length)

    def get_plaintext_description(self):
        """Get plain-text description for use in metadata. Uses
        search_description field if set; otherwise uses the result of
        :meth:`get_description` with tags stripped."""

        if self.search_description.strip():
            return self.search_description
        return striptags(self.get_description())


class ContentPage(Page, PagePreviewDescriptionMixin):
    """Basic content page model."""

    body = StreamField(BodyContentBlock, use_json_field=True)

    content_panels = Page.content_panels + [
        FieldPanel("description"),
        FieldPanel("body"),
    ]


class CollectionPage(Page):
    """Collection list page, with editable text content"""

    body = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("body", classname="full"),
    ]

    # only allow creating directly under home page
    parent_page_types = [HomePage]
    # not allowed to have sub pages
    subpage_types = []

    def get_context(self, request):
        """Add collections and collection stats to template context"""
        context = super().get_context(request)

        # include all collections with stats
        context.update(
            {
                "collections": Collection.objects.all(),
                "stats": Collection.stats(),
            }
        )
        return context


class ContributorPage(Page, PagePreviewDescriptionMixin):
    """Project contributor and advisory board page."""

    contributors = StreamField(
        [("person", SnippetChooserBlock(Person))],
        blank=True,
        help_text="Select and order people to be listed as project \
        contributors.",
        use_json_field=True,
    )
    board = StreamField(
        [("person", SnippetChooserBlock(Person))],
        blank=True,
        help_text="Select and order people to be listed as board members.",
        use_json_field=True,
    )

    body = StreamField(BodyContentBlock, blank=True, use_json_field=True)

    content_panels = Page.content_panels + [
        FieldPanel("description"),
        FieldPanel("contributors"),
        FieldPanel("board"),
        FieldPanel("body"),
    ]

    # only allow creating directly under home page
    parent_page_types = [HomePage]
    # not allowed to have sub pages
    subpage_types = []
