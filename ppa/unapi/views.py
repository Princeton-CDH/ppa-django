from django.http import HttpResponse
from django.http.response import Http404
from django.shortcuts import get_object_or_404
from django.views.generic.base import TemplateView

from ppa.archive.models import DigitizedWork


class UnAPIView(TemplateView):
    """Simple unAPI service endpoint.  With no parameters or only id,
    provides a list of available metadata formats.  If id and
    format are specified, returns the metadata for the specified item
    in the requested format.

    See archived unAPI website for more details.
    https://web.archive.org/web/20140331070802/http://unapi.info/specs/
    """

    #: template for format information
    template_name = "unapi/formats.xml"
    #: default content type, when serving format information
    content_type = "application/xml"

    #: available metadata formats
    formats = {
        "dc": {"type": "application/xml"},  # Dublin Core XML
    }

    #: file extension for metadata formats, as a convenience to set
    #: download filename extension
    file_extension = {
        # Currently empty - dc format displays in browser instead of download
    }

    def get(self, *args, **kwargs):
        """Override get to check if id and format are specified; if they
        are, return the requested metadata.  Otherwise, falls back
        to normal template view behavior and displays format information."""

        # if both id and format are specified, return actual metadata
        item_id = self.request.GET.get("id", None)
        metadata_format = self.request.GET.get("format", None)
        if item_id and metadata_format:
            response = HttpResponse(
                content=self.get_metadata(item_id, metadata_format),
                content_type=self.formats[metadata_format]["type"],
            )
            # Only set download filename for specific formats
            # DC format displays in browser instead of forcing download
            if metadata_format in self.file_extension:
                response["Content-Disposition"] = 'filename="%s.%s"' % (
                    item_id,
                    self.file_extension[metadata_format],
                )
            # For dc format, no Content-Disposition = display in browser

            return response

        # otherwise, return information about available formats
        return super(UnAPIView, self).get(*args, **kwargs)

    def get_context_data(self, *args, **kwargs):
        """pass formats and id to template context"""
        context = super(UnAPIView, self).get_context_data(*args, **kwargs)
        context.update(
            {"formats": self.formats, "id": self.request.GET.get("id", None)}
        )
        return context

    def get_metadata(self, item_id, data_format):
        """get item and requested metadata"""
        # For excerpts, unapi id uses index/group id,
        # which combines source id with first page number.

        if "-p" in item_id:
            # For excerpts, extract source_id and page number
            base_source_id, page_part = item_id.split("-p", 1)
            page_num = page_part

            # Find the specific excerpt by source_id and first page
            item = (
                DigitizedWork.objects.by_first_page_orig(page_num)
                .filter(source_id=base_source_id)
                .first()
            )
            if not item:
                raise Http404
        else:
            # For full works, index id is equivalent to source id
            item = get_object_or_404(DigitizedWork, source_id=item_id)

        # Pass the full item_id (including page info) to handle excerpts
        return item.get_metadata(data_format, item_id=item_id)
