from unittest.mock import Mock, patch

import requests
import pytest
from wagtail.embeds.exceptions import EmbedException

from ppa.pages.embed_finders import GlitchEmbedFinder


class TestGlitchEmbedFinder:

    def test_accept(self):
        assert GlitchEmbedFinder().accept('foobar.glitch.me')
        assert not GlitchEmbedFinder().accept('youtube.com/foo')

    test_html = '''<html>
    <head>
        <link rel="stylesheet" type="text/css" href="mystyles.css"/>
    </head>
    <body>
        <script src="myscript.js"></script>
    </body>
    </html>
    '''

    @patch('ppa.pages.embed_finders.requests')
    def test_find_embed(self, mockrequests):
        # patch in actual request status codes
        mockrequests.codes = requests.codes
        glitcher = GlitchEmbedFinder()

        # embed response fails
        mockrequests.get.return_value.status_code = 404
        with pytest.raises(EmbedException):
            glitcher.find_embed('http://test.glitch.me')
        mockrequests.get.assert_called_with('http://test.glitch.me/embed.json')

        # json request succeeeds but main url does not
        mockrequests.get.side_effect = (Mock(status_code=200),
                                        Mock(status_code=500))
        with pytest.raises(EmbedException):
            glitcher.find_embed('http://test.glitch.me')

        mockrequests.get.side_effect = None
        mockrequests.get.return_value.status_code = 200
        mock_embed = {
            'title': 'test glitch',
            'author_name': 'me'
        }
        mockrequests.get.return_value.json.return_value = mock_embed
        mockrequests.get.return_value.content = self.test_html
        embed_info = glitcher.find_embed('http://test.glitch.me')
        mockrequests.get.assert_called_with('http://test.glitch.me')
        # embed info from json
        assert embed_info['title'] == mock_embed['title']
        assert embed_info['author_name'] == mock_embed['author_name']
        # html from response content
        assert embed_info['html'].startswith('<html>')
        # relative links made absolute
        assert 'href="http://test.glitch.me/mystyles.css' in embed_info['html']
        assert 'src="http://test.glitch.me/myscript.js' in embed_info['html']
