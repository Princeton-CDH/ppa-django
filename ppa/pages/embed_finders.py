'''
Custom :class:`~wagtail.embeds.finders.base.EmbedFinder` implementations
for embedding content in wagtail pages.
'''

from json import JSONDecodeError
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import requests
from wagtail.embeds.finders.base import EmbedFinder
from wagtail.embeds.exceptions import EmbedException


class GlitchEmbedFinder(EmbedFinder):
    '''Custom oembed finder built to embed Glitch apps in wagtail pages.

    To support embedding, the glitch app should include a file named
    embed.json, available directly under the top level url, with
    oembed content::

        {
          "title": "title",
          "author_name": "author",
          "provider_name": "Glitch",
          "type": "rich",
          "thumbnail_url": "URL to thumbnail image",
          "width": xx,
          "height": xx
        }

    If the request for an embed.json file fails, no content will be embedded.

    Any urls that cannot automatically be made relative by embed code (i.e.
    data files loaded by javascript code) should use absolute URLs, or they
    will not resolve when embedded.
    '''

    def accept(self, url):
        """
        Accept a url if it includes `.glitch.me`
        """
        # return True if this finder can handle a url; no external requests
        return bool('.glitch.me' in url)

    def find_embed(self, url, max_width=None):
        """
        Retrieve embed.json and requested url and return content
        for embedding it on the site.
        """
        # NOTE: currently ignores max width

        # implementation assumes that glitch has an embed json file
        # with appropriate metadata
        response = requests.get(urljoin(url, 'embed.json'))
        # if embed info couldn't be loaded, error
        if response.status_code != requests.codes.ok:
            raise EmbedException('Failed to load embed.json file')
        try:
            embed_info = response.json()
        except JSONDecodeError:
            raise EmbedException('Error parsing embed.json file')

        # if embed info request succeeded, then get actual content
        response = requests.get(url)
        if response.status_code != requests.codes.ok:
            raise EmbedException('Failed to load url')

        soup = BeautifulSoup(response.content, 'html.parser')
        # cnovert relative links so they are absolute to glitch url
        for link in soup.find_all(href=True):
            link['href'] = urljoin(url, link['href'])
        for source in soup.find_all(src=True):
            source['src'] = urljoin(url, source['src'])

        embed_info['html'] = soup.prettify()
        return embed_info
