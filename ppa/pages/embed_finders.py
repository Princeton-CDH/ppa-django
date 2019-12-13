from urllib.parse import urljoin

from bs4 import BeautifulSoup
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

        # implementation assumes that glitch has an embed json file
        # with appropriate metadata
        response = requests.get(urljoin(url, 'embed.json'))
        if response.status_code == requests.codes.ok:
            embed_info = response.json()

            # if embed info request succeeded, then get actual content
            response = requests.get(url)
            soup = BeautifulSoup(response.content, 'html.parser')
            # make links relative
            for link in soup.find_all(href=True):
                link['href'] = urljoin(url, link['href'])
            for source in soup.find_all(src=True):
                source['src'] = urljoin(url, source['src'])

            embed_info['html'] = soup.prettify()
            return embed_info
