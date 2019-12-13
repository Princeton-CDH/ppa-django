from urllib.parse import urljoin

import requests
from wagtail.embeds.finders.base import EmbedFinder


class GlitchEmbedFinder(EmbedFinder):
    def __init__(self, **options):
        pass

    def accept(self, url):
        """
        Returns True if this finder knows how to fetch an embed for the URL.

        This should not have any side effects (no requests to external servers)
        """
        if '.glitch.me' in url:
            return True

        return False

    def find_embed(self, url, max_width=None):
        """
        Takes a URL and max width and returns a dictionary of information about
        the content to be used for embedding it on the site.

        This is the part that may make requests to external APIs.
        """
        # TODO: Perform the request

        response = requests.get(urljoin(url, 'embed.json'))
        if response.status_code == requests.codes.ok:
            embed_info = response.json()

            response = requests.get(url)
            embed_info['html'] = response.content
            return embed_info

        # return {
        #     'title': "Title of the content",
        #     'author_name': "Author name",
        #     'provider_name': "Provider name (eg. YouTube, Vimeo, etc)",
        #     'type': "Either 'photo', 'video', 'link' or 'rich'",
        #     'thumbnail_url': "URL to thumbnail image",
        #     'width': width_in_pixels,
        #     'height': height_in_pixels,
        #     'html': "<h2>The Embed HTML</h2>",
        # }
