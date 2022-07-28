import csv
import operator
import re
import uuid
from io import StringIO
from time import sleep
from unittest.mock import Mock, patch

import pytest
import requests
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db.models.functions import Lower
from django.template.defaultfilters import escape
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils.http import urlencode
from django.utils.timezone import now
from parasolr.django import SolrClient, SolrQuerySet

from ppa.archive.forms import (
    AddFromHathiForm,
    ModelMultipleChoiceFieldWithEmpty,
    SearchForm,
)
from ppa.archive.models import NO_COLLECTION_LABEL, Collection, DigitizedWork
from ppa.archive.solr import ArchiveSearchQuerySet
from ppa.archive.templatetags.ppa_tags import (
    gale_page_url,
    hathi_page_url,
    page_image_url,
)
from ppa.archive.views import AddFromHathiView, DigitizedWorkCSV, DigitizedWorkListView


class TestDigitizedWorkDetailView(TestCase):
    fixtures = ["sample_digitized_works"]

    @pytest.fixture(autouse=True)
    def _admin_client(self, admin_client):
        # make pytest-django admin client available on the class
        self.admin_client = admin_client

    @staticmethod
    def index_page_content():
        # add sample page content for one of the fixture works
        # and index it in solr
        sample_page_content = [
            "something about dials and clocks",
            "knobs and buttons",
        ]
        htid = "chi.78013704"
        # NOTE: this test is brittle; should refactor to use
        # actual page indexing logic somehow, to reflect actual indexed fields
        solr_page_docs = [
            {
                "content": content,
                "order": i + 1,
                "item_type": "page",
                "source_id": htid,
                "id": "%s.%s" % (htid, i),
                "label": i,
                "source_t": "HathiTrust",
                "group_id_s": htid,
            }
            for i, content in enumerate(sample_page_content)
        ]
        # dial = DigitizedWork.objects.get(source_id='chi.78013704')
        # solr_work_docs = [dial.index_data()]
        # index_data = solr_work_docs + solr_page_docs
        SolrClient().update.index(solr_page_docs, commit=True)

    def setUp(self):
        # get a work and its detail page to test with
        self.dial = DigitizedWork.objects.get(source_id="chi.78013704")
        self.dial_url = reverse(
            "archive:detail", kwargs={"source_id": self.dial.source_id}
        )
        self.dial.index()
        TestDigitizedWorkDetailView.index_page_content()

    def test_anonymous_display(self):
        # get the detail view page and check that the response is 200
        response = self.client.get(self.dial_url)
        assert response.status_code == 200
        # no keyword search so no note about that
        # no page_obj or search results reflected
        assert "page_obj" not in response.context
        self.assertNotContains(response, "No keyword results.")

        # now check that the right template is used
        assert "archive/digitizedwork_detail.html" in [
            template.name for template in response.templates
        ]

        # check that the appropriate item is in context
        assert "object" in response.context
        assert response.context["object"] == self.dial

        # - check that the information we expect is displayed
        # hathitrust ID
        self.assertContains(response, self.dial.title, msg_prefix="Missing title")
        self.assertContains(
            response,
            self.dial.source_id,
            msg_prefix="Missing HathiTrust ID (source_id)",
        )
        self.assertContains(
            response, self.dial.source_url, msg_prefix="Missing source_url"
        )
        # self.assertContains(  # disabled for now since it's not in design spec
        #     response, dial.enumcron,
        #     msg_prefix='Missing volume/chronology (enumcron)'
        # )
        self.assertContains(response, self.dial.author, msg_prefix="Missing author")
        self.assertContains(
            response,
            self.dial.pub_place,
            msg_prefix="Missing place of publication (pub_place)",
        )
        self.assertContains(
            response, self.dial.publisher, msg_prefix="Missing publisher"
        )
        self.assertContains(
            response,
            self.dial.pub_date,
            msg_prefix="Missing publication date (pub_date)",
        )

        # notes not present since object has none
        self.assertNotContains(
            response,
            "Note on edition",
            msg_prefix="Notes field should not be visible without notes",
        )

    def test_anonymous_display_excerpt_hathi(self):
        # create an excerpt
        excerpt = DigitizedWork.objects.create(
            source_id="abc.1234",
            source_url="https://hdl.example.co/9823/abc.1234",
            title="Additional note",
            book_journal="Works",
            pages_orig="151-58",
            pages_digital="151-158",
            item_type=DigitizedWork.EXCERPT,
        )

        response = self.client.get(excerpt.get_absolute_url())
        self.assertContains(response, """<th scope="row">Book Title</th>""", html=True)
        self.assertContains(response, excerpt.title)
        self.assertContains(response, excerpt.book_journal)
        self.assertContains(
            response, hathi_page_url(excerpt.source_id, excerpt.first_page())
        )

    def test_anonymous_display_excerpt_gale(self):
        # create a gale excerpt to test link logic
        excerpt = DigitizedWork.objects.create(
            source_id="abc.1234",
            source_url="https://hdl.example.co/9823/abc.1234",
            title="Additional note",
            book_journal="Works",
            pages_orig="151-58",
            pages_digital="151-158",
            item_type=DigitizedWork.EXCERPT,
            source=DigitizedWork.GALE,
        )
        response = self.client.get(excerpt.get_absolute_url())
        self.assertContains(
            response,
            gale_page_url(excerpt.source_url, excerpt.first_page()).replace(
                "&", "&amp;"  # without escaping the ampersand, check fails
            ),
        )

    def test_anonymous_display_article_hathi(self):
        # create an article
        article = DigitizedWork.objects.create(
            source_id="abc.1234",
            source_url="https://hdl.example.co/9823/abc.1234",
            title="About Rhyme",
            book_journal="Saturday review",
            pages_orig="151-58",
            pages_digital="151-158",
            item_type=DigitizedWork.ARTICLE,
        )

        response = self.client.get(article.get_absolute_url())
        self.assertContains(
            response, """<th scope="row">Journal Title</th>""", html=True
        )
        self.assertContains(response, article.title)
        self.assertContains(response, article.book_journal)

    def test_unapi(self):
        response = self.client.get(self.dial_url)
        # unapi server link present
        self.assertContains(
            response,
            """<link rel="unapi-server" type="application/xml"
            title="unAPI" href="%s" />"""
            % reverse("unapi"),
            msg_prefix="unapi server link should be set",
            html=True,
        )
        # unapi id present
        self.assertContains(
            response,
            '<abbr class="unapi-id" title="%s"></abbr>' % self.dial.source_id,
            msg_prefix="unapi id should be embedded for each work",
        )

    def test_admin_display(self):
        # get the detail view page and check that the response is 200
        response = self.admin_client.get(self.dial_url)

        # only displaying these if logged in currently
        self.assertContains(
            response,
            self.dial.added.strftime("%d %b %Y"),
            msg_prefix="Missing added or in wrong format (d M Y in filter)",
        )
        self.assertContains(
            response,
            self.dial.updated.strftime("%d %b %Y"),
            msg_prefix="Missing updated or in wrong format (d M Y in filter)",
        )

    def test_notes(self):
        # set a note and re-query to see if it now appears
        self.dial.public_notes = "Nota bene"
        self.dial.notes = "Secret note"
        self.dial.save()
        response = self.client.get(self.dial_url)
        self.assertContains(
            response,
            "Note on edition",
            msg_prefix="Notes field should be visible if notes is set",
        )
        self.assertContains(
            response,
            self.dial.public_notes,
            msg_prefix="The actual value of the notes field should be displayed",
        )
        self.assertNotContains(
            response,
            self.dial.notes,
            msg_prefix="The private notes field should not be displayed",
        )

    def test_admin_notes(self):
        # set a note and re-query to see if it now appears
        self.dial.public_notes = "Nota bene"
        self.dial.notes = "Secret note"
        self.dial.save()

        response = self.admin_client.get(self.dial_url)
        self.assertContains(
            response,
            self.dial.notes,
            msg_prefix="The private notes field should be displayed",
        )

    def test_suppressed(self):
        # suppressed work
        self.dial.status = DigitizedWork.SUPPRESSED
        # don't actually process the data deletion
        with patch.object(self.dial, "hathi"):
            self.dial.save()

        response = self.client.get(self.dial_url)
        # status code should be 410 Gone
        assert response.status_code == 410
        # should use 410 template
        assert "410.html" in [template.name for template in response.templates]
        # should not display item details
        self.assertNotContains(response, self.dial.title, status_code=410)

    def test_nonhathi_display(self):
        # non-hathi work
        thesis = DigitizedWork.objects.create(
            source=DigitizedWork.OTHER,
            source_id="788423659",
            source_url="http://www.worldcat.org/title/study-of-the-accentual-structure-of-caesural-phrases-in-the-lady-of-the-lake/oclc/788423659",
            title="A study of the accentual structure of caesural phrases in The lady of the lake",
            sort_title="study of the accentual structure of caesural phrases in The lady of the lake",
            author="Farley, Odessa",
            publisher="University of Iowa",
            pub_date=1924,
            page_count=81,
        )

        response = self.client.get(thesis.get_absolute_url())
        # should display item details
        self.assertContains(response, thesis.title)
        self.assertContains(response, thesis.author)
        self.assertContains(response, thesis.source_id)
        self.assertContains(response, "View external record")
        self.assertContains(response, thesis.source_url)
        self.assertContains(response, thesis.pub_date)
        self.assertContains(response, thesis.page_count)
        self.assertNotContains(response, "HathiTrust")
        self.assertNotContains(response, "Search within the Volume")

        # no source url - should not display link
        thesis.source_url = ""
        thesis.save()
        response = self.client.get(thesis.get_absolute_url())
        self.assertNotContains(response, "View external record")

        # search term should be ignored for items without fulltext
        with patch("ppa.archive.views.SolrQuerySet") as mock_solrq:
            response = self.client.get(thesis.get_absolute_url(), {"query": "lady"})
            # not called at all
            assert mock_solrq.call_count == 0

    def test_search_within_empty(self):
        # search with no matches - test empty search result
        response = self.client.get(self.dial_url, {"query": "thermodynamics"})
        assert response.status_code == 200
        # test that the search form is rendered
        assert "search_form" in response.context
        assert "query" in response.context["search_form"].fields
        # query string passsed into context for form
        assert "query" in response.context
        assert response.context["query"] == "thermodynamics"
        # solr highlight results in query
        assert "page_highlights" in response.context
        # should be an empty dict
        assert response.context["page_highlights"] == {}
        # assert solr result in query
        assert "current_results" in response.context
        # object list should be empty
        assert not response.context["current_results"].object_list.count()

    def test_search_within_snippets(self):
        # test with a word that will produce some snippets
        response = self.client.get(self.dial_url, {"query": "knobs"})
        assert response.status_code == 200
        # paginated results should be in context
        assert "current_results" in response.context
        # it should be page one (because we have one result)
        assert response.context["current_results"].number == 1
        # it should have an object list equal in length to the page solr query
        assert len(response.context["current_results"].object_list) == 1
        # get the solr results (should be one)
        result = response.context["current_results"].object_list[0]
        # grab the highlight object that's rendered with our one match
        highlights = response.context["page_highlights"][result["id"]]
        # template has the expected information rendered
        self.assertContains(response, highlights["content"][0])
        # page number that correspondeds to label field should be present
        self.assertContains(
            response,
            "p. %s" % result["label"],
            count=1,
            msg_prefix="has page label for the print page numb.",
        )
        # image url should appear in each src and and srcset
        # (one for lazy load image and one for noscript image)
        self.assertContains(
            response,
            page_image_url(result["source_id"], result["order"], 225),
            count=4,
            msg_prefix="has img src url",
        )
        # 2x image url should appear in srcset for img and noscript img
        self.assertContains(
            response,
            page_image_url(result["source_id"], result["order"], 450),
            count=2,
            msg_prefix="has imgset src url",
        )
        self.assertContains(response, "1 occurrence")
        # image should have a link to hathitrust as should the page number
        self.assertContains(
            response,
            hathi_page_url(result["source_id"], result["order"]),
            count=2,
            msg_prefix="should include a link to HathiTrust",
        )

    def test_search_within_error(self):
        # test raising a generic solr error
        with patch("ppa.archive.views.Paginator") as mock_page:

            mock_page.side_effect = requests.exceptions.ConnectionError
            response = self.client.get(self.dial_url, {"query": "knobs"})
            self.assertContains(response, "Something went wrong.")

    def test_search_within_ajax(self):
        # ajax request for search results
        response = self.client.get(
            self.dial_url, {"query": "knobs"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        assert response.status_code == 200
        # should render the results list partial
        self.assertTemplateUsed("archive/snippets/results_within_list.html")
        # shouldn't render the whole list
        self.assertTemplateNotUsed("archive/digitizedwork_detail.html")
        # should have all the results
        assert len(response.context["page_highlights"]) == 1
        # should have the results count
        self.assertContains(response, "1 occurrence")
        # should have pagination
        self.assertContains(response, '<div class="page-controls')

    def test_get_queryset(self):
        # requesting non-excerpt with start page specified should return 404 not found
        bogus_dial_excerpt_url = reverse(
            "archive:detail",
            kwargs={"source_id": self.dial.source_id, "start_page": 15},
        )
        assert self.client.get(bogus_dial_excerpt_url).status_code == 404
        # create and retrieve an excerpt; should return 200 ok with correct object
        dial_excerpt = DigitizedWork.objects.create(
            source_id=self.dial.source_id, pages_digital="200-250"
        )
        print(dial_excerpt.get_absolute_url())
        response = self.client.get(dial_excerpt.get_absolute_url())
        assert response.status_code == 200
        print(response.context["object"])
        assert response.context["object"] == dial_excerpt

        # getting the full work should not return the excerpt
        response = self.client.get(self.dial_url)
        assert response.status_code == 200
        assert response.context["object"] == self.dial

        # create excerpt where there is no existing work
        excerpt = DigitizedWork.objects.create(
            source_id="abc.123456", pages_digital="10-20"
        )
        response = self.client.get(excerpt.get_absolute_url())
        # retrieve url for source id with no start apge
        nonexistent_source_url = reverse(
            "archive:detail", kwargs={"source_id": excerpt.source_id}
        )
        # should return permanent redirect to the single excerpt
        response = self.client.get(nonexistent_source_url)
        assert response.status_code == 301
        assert response["Location"] == excerpt.get_absolute_url()

        # if there are *TWO* excerpts for the same source, should 404 instead of redirecting
        excerpt2 = DigitizedWork.objects.create(
            source_id="abc.123456", pages_digital="30-45"
        )
        assert self.client.get(nonexistent_source_url).status_code == 404


class TestDigitizedWorkListRequest(TestCase):
    fixtures = ["sample_digitized_works"]

    @pytest.fixture(autouse=True)
    def _admin_client(self, admin_client, empty_solr):
        # make pytest-django admin client available on the class
        self.admin_client = admin_client
        # empty solr before indexing

    @staticmethod
    def index_fixtures():
        # add sample page content for one of the fixture works
        # and index it in solr
        sample_page_content = [
            "something about winter and wintry and wintriness",
            "something else delightful",
            "an alternate thing with words like blood and bone not in the title",
        ]
        htid = "chi.13880510"
        # NOTE: sample page index data must be updated if page indexing changes
        solr_page_docs = [
            {
                "content": content,
                "order": i,
                "item_type": "page",
                "source_id": htid,
                "id": "%s.%s" % (htid, i),
                "group_id_s": htid,  # group id for non-excerpt = source id
            }
            for i, content in enumerate(sample_page_content)
        ]

        work_docs = [dw.index_data() for dw in DigitizedWork.objects.all()]
        index_data = work_docs + solr_page_docs
        SolrClient().update.index(index_data)
        # NOTE: without a sleep, even with commit=True and/or low
        # commitWithin settings, indexed data isn't reliably available
        while SolrQuerySet().search(item_type="work").count() == 0:
            # sleep until we get records back; 0.1 seems to be enough
            # for local dev with local Solr
            sleep(0.1)

    def setUp(self):
        # get a work and its detail page to test with
        self.dial = DigitizedWork.objects.get(source_id="chi.78013704")
        self.wintry = DigitizedWork.objects.get(title__icontains="Wintry")

        # add a collection to use in testing the view
        self.collection = Collection.objects.create(name="Test Collection")
        self.wintry.collections.add(self.collection)
        self.url = reverse("archive:list")
        TestDigitizedWorkListRequest.index_fixtures()

    def test_noquery(self):
        # no query - should find all
        response = self.client.get(self.url)
        assert response.status_code == 200
        self.assertContains(
            response, "%d digitized works" % len(DigitizedWork.objects.all())
        )
        self.assertContains(
            response,
            '<p class="result-number">1</p>',
            msg_prefix="results have numbers",
        )
        self.assertContains(
            response,
            '<p class="result-number">2</p>',
            msg_prefix="results have multiple numbers",
        )

        # unapi server link present
        self.assertContains(
            response,
            """<link rel="unapi-server" type="application/xml"
            title="unAPI" href="%s" />"""
            % reverse("unapi"),
            msg_prefix="unapi server link should be set",
            html=True,
        )

        # should not have scores for all results, as not logged in
        self.assertNotContains(response, "score")

        # search form should be set in context for display
        assert isinstance(response.context["search_form"], SearchForm)
        # page group details from expanded part of collapsed query
        assert "page_groups" in response.context
        # facet range information from publication date range facet
        assert "facet_ranges" in response.context

        for digwork in DigitizedWork.objects.all():
            # check basic metadata for each work
            self.assertContains(response, digwork.title)
            self.assertContains(response, digwork.subtitle)
            self.assertContains(response, digwork.source_id)
            self.assertContains(response, digwork.author)
            self.assertContains(response, digwork.enumcron)
            # at least one publisher includes an ampersand, so escape text
            self.assertContains(response, escape(digwork.publisher))
            # self.assertContains(response, digwork.pub_place)
            self.assertContains(response, digwork.pub_date)
            # link to detail page
            self.assertContains(response, digwork.get_absolute_url())
            # unapi identifier for each work
            self.assertContains(
                response,
                '<abbr class="unapi-id" title="%s"' % digwork.index_id(),
                msg_prefix="unapi id should be embedded for each work",
            )

        # no page images or highlights displayed without search term
        self.assertNotContains(
            response,
            "babel.hathitrust.org/cgi/imgsrv/image",
            msg_prefix="no page images displayed without keyword search",
        )

        # no collection label should only display once
        # (for collection selection badge, not for result display)
        self.assertContains(response, NO_COLLECTION_LABEL, count=1)

    def test_admin(self):
        # request as logged in user; should include relevance score
        response = self.admin_client.get(self.url)
        self.assertContains(response, "score")

    def test_keyword_search(self):
        # use keyword search with a term in a fixture title
        response = self.client.get(self.url, {"query": "wintry"})
        # relevance sort for keyword search
        assert len(response.context["object_list"]) == 1
        self.assertContains(response, "1 digitized work")
        self.assertContains(response, self.wintry.source_id)
        # page image & text highlight displayed for matching page
        self.assertContains(
            response,
            "babel.hathitrust.org/cgi/imgsrv/image?id=%s;seq=0" % self.wintry.source_id,
            msg_prefix="page image displayed for matching pages on keyword search",
        )
        self.assertContains(
            response,
            "winter and <em>wintry</em> and",
            msg_prefix="highlight snippet from page content displayed",
        )

    def test_search_excerpt(self):
        # convert one of the fixtures into an excerpt
        # confirm link to excerpt url works properly
        with patch("ppa.archive.models.DigitizedWork.index_items"):
            # skip reindexing pages normally triggered by change to page range
            # test with an ARK identifier because most problematic
            self.wintry.source_id = "aeu.ark:/13960/t1pg22p71"
            self.wintry.pages_digital = "10-15"
            self.wintry.item_type = DigitizedWork.EXCERPT
            self.wintry.save()
        DigitizedWork.index_items([self.wintry])
        sleep(1)
        response = self.client.get(self.url, {"query": "wintry"})
        self.assertContains(response, self.wintry.get_absolute_url())

    def test_year_filter(self):
        # page image and text highlight should still display with year filter
        response = self.client.get(self.url, {"query": "wintry", "pub_date_0": 1800})
        assert response.context["page_highlights"]

        self.assertContains(
            response,
            "winter and <em>wintry</em> and",
            msg_prefix="highlight snippet from page content displayed",
        )
        self.assertContains(
            response,
            "babel.hathitrust.org/cgi/imgsrv/image?id=%s;seq=0" % self.wintry.source_id,
            msg_prefix="page image displayed for matching pages on keyword search",
        )
        self.assertContains(
            response,
            "winter and <em>wintry</em> and",
            msg_prefix="highlight snippet from page content displayed",
        )

    def test_page_keyword(self):
        # match in page content but not in book metadata should pull back title
        response = self.client.get(self.url, {"query": "blood"})
        self.assertContains(response, "1 digitized work")

        self.assertContains(response, self.wintry.source_id)
        self.assertContains(response, self.wintry.title)

    def test_search_author(self):
        # keyword search on author name
        response = self.client.get(self.url, {"query": "Robert Bridges"})
        self.assertContains(response, self.wintry.source_id)

        # search author as author field only
        response = self.client.get(self.url, {"author": "Robert Bridges"})
        self.assertContains(response, self.wintry.source_id)
        self.assertNotContains(response, self.dial.source_id)

    def test_search_title(self):
        # search title using the title field
        response = self.client.get(self.url, {"title": "The Dial"})
        self.assertContains(response, self.dial.source_id)
        self.assertNotContains(response, self.wintry.source_id)

        # search on subtitle using the title query field
        response = self.client.get(self.url, {"title": "valuable"})
        self.assertNotContains(response, self.dial.source_id)
        self.assertNotContains(response, self.wintry.source_id)
        self.assertContains(response, "135000 words")

    def test_search_publisher(self):
        # search text in publisher name
        response = self.client.get(self.url, {"query": "McClurg"})
        for digwork in DigitizedWork.objects.filter(publisher__icontains="mcclurg"):
            self.assertContains(response, digwork.source_id)

    def test_search_publication_place(self):
        # search text in publication place - matches wintry
        response = self.client.get(self.url, {"query": "Oxford"})
        self.assertContains(response, self.wintry.source_id)

    def test_search_exact_phrase(self):
        # exact phrase
        response = self.client.get(self.url, {"query": '"wintry delights"'})
        self.assertContains(response, "1 digitized work")
        self.assertContains(response, self.wintry.source_id)

    def test_search_boolean(self):
        # boolean
        response = self.client.get(self.url, {"query": "blood AND bone AND alternate"})
        self.assertContains(response, "1 digitized work")
        self.assertContains(response, self.wintry.source_id)
        response = self.client.get(self.url, {"query": "blood NOT bone"})
        self.assertContains(response, "No matching works.")

        # bad syntax
        # NOTE: According to Solr docs, edismax query parser
        # "includes improved smart partial escaping in the case of syntax
        # errors"; not sure how to trigger this error anymore!
        # response = self.client.get(url, {'query': '"incomplete phrase'})
        # self.assertContains(response, 'Unable to parse search query')

    def test_search_sort(self):
        # add a sort term - pub date
        response = self.client.get(self.url, {"sort": "pub_date_asc"})
        # get works from the database sorted by pub date
        sorted_works_ids = list(
            DigitizedWork.objects.order_by("pub_date").values_list(
                "source_id", flat=True
            )
        )
        # the list of sorted ids should match
        assert sorted_works_ids == [
            work["source_id"] for work in response.context["object_list"]
        ]

        # test sort date in reverse
        response = self.client.get(self.url, {"sort": "pub_date_desc"})
        # get works sorted by reverse pub date from the database
        sorted_works_ids = list(
            DigitizedWork.objects.order_by("-pub_date").values_list(
                "source_id", flat=True
            )
        )

        # the list of sorted ids should match
        assert sorted_works_ids == [
            work["source_id"] for work in response.context["object_list"]
        ]

        # one last test using title
        response = self.client.get(self.url, {"query": "", "sort": "title_asc"})
        sorted_work_ids = DigitizedWork.objects.order_by(
            Lower("sort_title")
        ).values_list("source_id", flat=True)
        # the list of ids should match exactly
        assert list(sorted_work_ids) == [
            work["source_id"] for work in response.context["object_list"]
        ]

    def test_relevance_sort_enabled(self):
        # - check that a query allows relevance as sort order toggle in form
        response = self.client.get(self.url, {"query": "foo", "sort": "title_asc"})
        enabled_input = '<div class="item " data-value="relevance">Relevance</div>'
        self.assertContains(response, enabled_input, html=True)
        response = self.client.get(self.url, {"title": "foo", "sort": "title_asc"})
        self.assertContains(response, enabled_input, html=True)
        response = self.client.get(self.url, {"author": "foo", "sort": "title_asc"})
        self.assertContains(response, enabled_input, html=True)
        # check that a search that does not have a query disables
        # relevance as a sort order option
        response = self.client.get(self.url, {"sort": "title_asc"})
        self.assertContains(
            response,
            '<div class="item disabled" data-value="relevance">Relevance</div>',
            html=True,
        )

    def test_default_sort(self):
        # default sort should be title if no keyword search and no sort specified
        response = self.client.get(self.url)
        assert response.context["search_form"].cleaned_data["sort"] == "title_asc"
        # default collections should be set based on exclude option
        assert set(response.context["search_form"].cleaned_data["collections"]) == set(
            [NO_COLLECTION_LABEL]
        ).union((set(Collection.objects.filter(exclude=False))))

        # if relevance sort is requested but no keyword, switch to default sort
        response = self.client.get(self.url, {"sort": "relevance"})
        assert response.context["search_form"].cleaned_data["sort"] == "title_asc"

    def test_collection_filter(self):
        # no collections = no items (but not an error)
        response = self.client.get(self.url, {"collections": ""})
        assert response.status_code == 200
        assert not response.context["object_list"]

        # restrict to test collection by id
        response = self.client.get(self.url, {"collections": self.collection.pk})
        assert response.context["object_list"].count() == 1
        self.assertContains(response, self.wintry.source_id)

        # special 'uncategorized' collection
        response = self.client.get(
            self.url, {"collections": ModelMultipleChoiceFieldWithEmpty.EMPTY_ID}
        )
        assert (
            len(response.context["object_list"])
            == DigitizedWork.objects.filter(collections__isnull=True).count()
        )

    def test_date_range_filter(self):
        # basic date range request
        response = self.client.get(self.url, {"pub_date_0": 1900, "pub_date_1": 1922})
        # in fixture data, only wintry and 135000 words are after 1900
        assert len(response.context["object_list"]) == 2
        self.assertContains(response, self.wintry.source_id)

        # invalid date range request / invalid form - not an exception
        response = self.client.get(self.url, {"pub_date_0": 1900, "pub_date_1": 1800})
        assert not response.context["object_list"].count()
        self.assertContains(response, "Invalid range")

    def test_ajax_request(self):
        # ajax request for search results
        response = self.client.get(self.url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        assert response.status_code == 200
        # should render the results list partial and single result partial
        self.assertTemplateUsed("archive/snippets/results_list.html")
        self.assertTemplateUsed("archive/snippest/search_result.html")
        # shouldn't render the search form or whole list
        self.assertTemplateNotUsed("archive/snippets/search_form.html")
        self.assertTemplateNotUsed("archive/digitizedwork_list.html")
        # should have all the results
        assert (
            len(response.context["object_list"]) == DigitizedWork.objects.all().count()
        )
        # should have the results count
        self.assertContains(response, " digitized works")
        # should have the histogram data
        self.assertContains(response, '<pre class="count">')
        # should have pagination
        self.assertContains(response, '<div class="page-controls')
        # test a query
        response = self.client.get(
            self.url,
            {"query": "blood AND bone AND alternate"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertContains(response, "1 digitized work")
        self.assertContains(response, self.wintry.source_id)

    @pytest.mark.usefixtures("mock_solr_queryset")
    def test_error(self):
        # simulate solr exception
        mock_searchqs = self.mock_solr_queryset(spec=ArchiveSearchQuerySet)

        with patch(
            "ppa.archive.views.ArchiveSearchQuerySet", new=mock_searchqs
        ) as mock_queryset_cls:

            mock_qs = mock_queryset_cls.return_value
            mock_qs.get_expanded.side_effect = requests.exceptions.ConnectionError
            # return main mock when paginated
            mock_qs.__getitem__.return_value = mock_qs
            # count needed for paginator
            mock_qs.count.return_value = 0
            # simulate empty result doc for last modified check
            mock_qs.return_value.__getitem__.return_value = {}
            mock_qs.get_facets.return_value.facet_ranges.as_dict.return_value = {
                "pub_date": []
            }
            response = self.client.get(self.url, {"query": "something"})
            # paginator variables should still be set
            assert "object_list" in response.context
            assert "paginator" in response.context
            self.assertContains(response, "Something went wrong.")


@pytest.mark.django_db
def test_archive_list_empty_solr(client, empty_solr):
    # archive page should not error when nothing is indexed
    response = client.get(reverse("archive:list"))
    assert response.status_code == 200
    assert "No matching works" in response.content.decode()


class TestDigitizedWorkCSV(TestCase):
    fixtures = ["sample_digitized_works"]

    def test_csv(self):
        # add an arbitrary note to one digital work so that the field is
        # populated in at least one case
        first_dw = DigitizedWork.objects.first()
        first_dw.notes = "private notes"
        first_dw.public_notes = "public notes"
        first_dw.save()

        # add an excerpt to check new fields are included
        excerpt = DigitizedWork.objects.create(
            source_id="njp.32101023869397",
            title="The Old and the New in Metrics",
            pub_date=1905,
            book_journal="The Classical journal",
            pages_orig="212-221",
            pages_digital="220-229",
            page_count=9,
        )

        # get the csv export and inspect the response
        response = self.client.get(reverse("archive:csv"))
        assert response.status_code == 200
        assert response["content-type"] == "text/csv"
        content_disposition = response["content-disposition"]
        assert content_disposition.startswith('attachment; filename="')
        assert "ppa-digitizedworks-" in content_disposition
        assert content_disposition.endswith('.csv"')
        assert now().strftime("%Y%m%d") in content_disposition
        assert re.search(r"\d{8}T\d{2}:\d{2}:\d{2}", content_disposition)

        # read content as csv and inspect
        csvreader = csv.reader(StringIO(response.content.decode()))
        rows = [row for row in csvreader]
        digworks = DigitizedWork.objects.order_by("id").all()
        # check for header row
        assert rows[0] == DigitizedWorkCSV.header_row
        # check for expected number of records - header + one row for each work
        assert len(rows) == digworks.count() + 1
        # check expected data in CSV output
        for digwork, digwork_data in zip(digworks, rows[1:]):
            assert digwork.source_id in digwork_data
            assert digwork.record_id in digwork_data
            assert digwork.title in digwork_data
            assert digwork.subtitle in digwork_data
            assert digwork.sort_title in digwork_data
            assert digwork.author in digwork_data
            assert str(digwork.pub_date) in digwork_data
            assert digwork.pub_place in digwork_data
            assert digwork.publisher in digwork_data
            assert digwork.publisher in digwork_data
            assert digwork.enumcron in digwork_data
            assert (
                ";".join([coll.name for coll in digwork.collections.all()])
                in digwork_data
            )
            assert digwork.notes in digwork_data
            assert digwork.public_notes in digwork_data
            assert "%d" % digwork.page_count in digwork_data
            assert "%s" % digwork.added in digwork_data
            assert "%s" % digwork.updated in digwork_data
            assert digwork.get_status_display() in digwork_data
            assert digwork.get_source_display() in digwork_data
            # excerpt fields
            assert digwork.get_item_type_display() in digwork_data
            # check optional fields if set
            for opt_field in ("book_journal", "pages_orig", "pages_digital"):
                value = getattr(digwork, opt_field)
                if value:
                    assert value in digwork_data


class TestAdminViews(TestCase):
    @pytest.fixture(autouse=True)
    def _admin_client(self, admin_client):
        # make pytest-django admin client available on the class
        self.admin_client = admin_client

    def test_digitizedwork_changelist_csv(self):
        # request digitized work change list as admin
        response = self.admin_client.get(
            reverse("admin:archive_digitizedwork_changelist")
        )
        self.assertContains(
            response,
            reverse("archive:csv"),
            msg_prefix="digitized work change list should include CSV download link",
        )
        self.assertContains(
            response,
            "Download as CSV",
            msg_prefix="digitized work change list should include CSV download button",
        )

    def test_other_changelist_no_csv(self):
        # link should not be on other change lists
        response = self.admin_client.get(reverse("admin:auth_user_changelist"))
        self.assertNotContains(
            response,
            reverse("archive:csv"),
            msg_prefix="CSV download link should only be on digitized work list",
        )


class TestDigitizedWorkByRecordId(TestCase):
    fixtures = ["sample_digitized_works"]

    def setUp(self):
        self.dial = DigitizedWork.objects.get(source_id="chi.78013704")
        self.record_url = reverse("archive:record-id", args=[self.dial.record_id])

    def test_single_item(self):
        # single item: should redirect
        response = self.client.get(self.record_url)
        assert response.status_code == 302
        assert response["Location"] == self.dial.get_absolute_url()

    def test_multiple_matches(self):
        # multiple works with the same record id: should 404
        # set all the test records to the same record id
        DigitizedWork.objects.update(record_id=self.dial.record_id)
        assert self.client.get(self.record_url).status_code == 404

    def test_bogus_id(self):
        # bogus id should 404
        record_url = reverse("archive:record-id", args=["012334567"])
        assert self.client.get(record_url).status_code == 404


class TestAddToCollection(TestCase):
    fixtures = ["sample_digitized_works"]

    def setUp(self):
        self.test_pass = "secret"
        self.testuser = "test"
        self.user = get_user_model().objects.create_user(
            username="test", password=self.test_pass
        )
        self.user.save()
        self.test_credentials = {"username": self.testuser, "password": self.test_pass}

        get_user_model().objects.create_superuser(
            username="super", password=self.test_pass, email="foo@bar.com"
        )
        self.admin_credentials = {"username": "super", "password": self.test_pass}

    def test_permissions(self):
        # - anonymous user gets redirect to login
        bulk_add = reverse("archive:add-to-collection")
        assert self.client.get(bulk_add).status_code == 302
        # - user without staff permissions gets forbidden
        self.client.login(**self.test_credentials)
        assert self.client.get(bulk_add).status_code == 302
        # - logged in staff user is still forbidden
        self.user.is_staff = True
        self.user.save()
        assert self.client.get(bulk_add).status_code == 403
        # - user with change permission on digitized work
        change_digwork_perm = Permission.objects.get(codename="change_digitizedwork")
        self.user.user_permissions.add(change_digwork_perm)
        assert self.client.get(bulk_add).status_code == 200

    def test_get(self):
        self.client.login(**self.admin_credentials)

        # - a get to the view with ids should return a message to use
        # the admin interface and not enable the form for submission
        bulk_add = reverse("archive:add-to-collection")
        response = self.client.get(bulk_add)
        self.assertContains(
            response, "<h1>Add Digitized Works to Collections</h1>", html=True
        )
        self.assertContains(
            response, "Please select digitized works from the admin interface."
        )
        # sending a set of pks that don't exist should produce the same result
        session = self.client.session
        session["collection-add-ids"] = [100, 101]
        session.save()
        response = self.client.get(bulk_add)
        # check that the session var has been set to an empy list
        assert self.client.session.get("collection-add-ids") == []
        self.assertContains(
            response, "Please select digitized works from the admin interface."
        )
        # create a collection and send valid pks
        coll1 = Collection.objects.create(name="Random Grabbag")
        session["collection-add-ids"] = [1, 2]
        session.save()
        response = self.client.get(bulk_add)
        # check html=False so we can look for just the opening tag of the form
        # block (html expects all the content between the closing tag too!)
        self.assertContains(
            response,
            '<form method="post"',
        )
        self.assertContains(
            response, '<option value="%d">Random Grabbag</option>' % coll1.id, html=True
        )

    @patch.object(DigitizedWork, "index")
    def test_post(self, mockindex):
        self.client.login(**self.admin_credentials)

        # - check that a post to the bulk-add route with valid pks
        # adds them to the appropriate collection
        # make a collection
        coll1 = Collection.objects.create(name="Random Grabbag")
        digworks = DigitizedWork.objects.order_by("id")[0:2]
        pks = list(digworks.values_list("id", flat=True))
        bulk_add = reverse("archive:add-to-collection")
        session = self.client.session
        session["collection-add-ids"] = pks
        session.save()

        # post to the add to collection url
        res = self.client.post(bulk_add, {"collections": coll1.pk})
        # redirects to the admin archive change list by default without filters
        # since none are set
        assert res.status_code == 302
        assert res.url == reverse("admin:archive_digitizedwork_changelist")
        # digitized works with pks 1,2 are added to the collection
        digworks = DigitizedWork.objects.filter(collections__pk=coll1.pk).order_by("id")
        assert digworks.count() == 2
        assert (
            list(digworks.values_list("id", flat=True)) == session["collection-add-ids"]
        )
        # the session variable is cleared
        assert "collection-add-ids" not in self.client.session
        # - check that index method was called
        assert mockindex.call_count == 1
        # check index called with the expected works
        # (use list because of queryset comparison limitations)
        assert list(mockindex.call_args[0][0]) == list(digworks)

        # - bulk add should actually add and not reset collections, i.e.
        # those individually added or added in a previous bulk add shouldn't
        # be erased from the collection's digitizedwork_set
        # only set pk 1 in the ids to add
        session["collection-add-ids"] = [digworks[0].pk]
        # also check that filters are preserved
        session["collection-add-filters"] = {"q": 1, "foo": "bar"}
        session.save()

        # bulk adding first pk but not the second
        res = self.client.post(bulk_add, {"collections": coll1.pk})
        # redirect as expected and retain querystring
        assert res.status_code == 302
        assert res.url == "%s?%s" % (
            reverse("admin:archive_digitizedwork_changelist"),
            urlencode(session["collection-add-filters"].items()),
        )
        digworks2 = DigitizedWork.objects.filter(collections__pk=coll1.pk).order_by(
            "id"
        )
        # this will fail if the bulk add removed the previously set two works
        assert digworks2.count() == 2
        # they should also be the same objects as before, i.e. this post request
        # should result in a noop
        assert digworks == digworks

        # - test a dud post (i.e. without a Collection)
        # should redirect with an error
        session["collection-add-ids"] = pks
        session.save()
        response = self.client.post(bulk_add, {"collections": ""})
        assert response.status_code == 200
        # check that the error message rendered for a missing Collection
        self.assertContains(
            response,
            '<ul class="errorlist"><li>Please select at least one '
            "Collection</li></ul>",
            html=True,
        )
        session["collection-add-ids"] = None
        session.save()
        response = self.client.post(bulk_add, {"collections": coll1.pk})
        # Default message for an unset collection pk list
        self.assertContains(
            response,
            "<p> Please select digitized works from the admin interface. </p>",
            html=True,
        )


class TestDigitizedWorkListView(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @pytest.mark.usefixtures("mock_solr_queryset")
    def test_get_page_highlights(self):

        digworkview = DigitizedWorkListView()

        # no keyword or page groups, no highlights
        assert digworkview.get_page_highlights({}) == {}

        # search term but no page groups
        digworkview.query = "iambic"
        assert digworkview.get_page_highlights({}) == {}

        # mock PagedSolrQuery to inspect that query is generated properly
        with patch(
            "ppa.archive.views.SolrQuerySet", new=self.mock_solr_queryset()
        ) as mock_queryset_cls:
            page_groups = {
                "group1": {
                    "docs": [
                        {"id": "p1a"},
                        {"id": "p1b"},
                    ]
                },
                "group2": {
                    "docs": [
                        {"id": "p2a"},
                        {"id": "p2b"},
                    ]
                },
            }

            highlights = digworkview.get_page_highlights(page_groups)

            mock_queryset_cls.assert_called_with()
            mock_qs = mock_queryset_cls.return_value
            mock_qs.search.assert_any_call(content="(iambic)")
            mock_qs.search.assert_called_with(
                id__in=["(p1a)", "(p1b)", "(p2a)", "(p2b)"]
            )
            mock_qs.only.assert_called_with("id")
            mock_qs.highlight.assert_called_with(
                "content*", snippets=3, method="unified"
            )
            mock_qs.get_results.assert_called_with(rows=4)

            assert highlights == mock_qs.get_highlighting()

    @pytest.mark.usefixtures("mock_solr_queryset")
    def test_get_queryset(self):
        digworkview = DigitizedWorkListView()

        # generate mock solr queryset based on subclass
        mock_searchqs = self.mock_solr_queryset(spec=ArchiveSearchQuerySet)

        # no text query, so solr query should not have page join present
        with patch(
            "ppa.archive.views.ArchiveSearchQuerySet", new=mock_searchqs
        ) as mock_queryset_cls:

            mock_qs = mock_queryset_cls.return_value
            # count is required for the paginator
            # mock_qs.count.return_value = 0

            # needed for the paginator
            # mockpsq.return_value.count.return_value = 0

            digworkview.request = self.factory.get(
                reverse("archive:list"), {"author": "Robert"}
            )
            digworkview.get_queryset()
            # queryset initialized
            mock_queryset_cls.assert_called_with()
            mock_qs.facet.assert_called_with(*SearchForm.facet_fields)
            mock_qs.order_by.assert_called_with("sort_title")  # default sort
            mock_qs.work_filter.assert_called_with(author="Robert")


class TestAddFromHathiView(TestCase):

    superuser = {"username": "super", "password": str(uuid.uuid4())}

    def setUp(self):
        self.factory = RequestFactory()
        self.add_from_hathi_url = reverse("admin:add-from-hathi")

        self.user = get_user_model().objects.create_superuser(
            email="su@example.com", **self.superuser
        )

        test_pass = "secret"
        testuser = "test"
        self.user = get_user_model().objects.create_user(
            username=testuser, password=test_pass, is_staff=True
        )
        self.user.save()
        self.test_credentials = {"username": testuser, "password": test_pass}

    def test_get_context(self):
        add_from_hathi = AddFromHathiView()
        add_from_hathi.request = self.factory.get(self.add_from_hathi_url)
        context = add_from_hathi.get_context_data()
        assert context["page_title"] == AddFromHathiView.page_title

    @patch("ppa.archive.views.HathiImporter")
    def test_form_valid(self, mock_hathi_importer):
        add_form = AddFromHathiForm({"hathi_ids": "old\nnew"})
        add_form.is_valid()

        mock_htimporter = mock_hathi_importer.return_value
        # set mock existing id & imported work on the mock importer
        mock_htimporter.existing_ids = {"old": 1}
        mock_htimporter.imported_works = [Mock(source_id="new", pk=2)]

        add_from_hathi = AddFromHathiView()
        add_from_hathi.request = self.factory.post(
            self.add_from_hathi_url, {"hathi_ids": "old\nnew"}
        )
        add_from_hathi.request.user = self.user
        response = add_from_hathi.form_valid(add_form)

        mock_hathi_importer.assert_called_with(add_form.get_hathi_ids())
        mock_htimporter.filter_existing_ids.assert_called_with()
        mock_htimporter.add_items.assert_called_with(
            log_msg_src="via django admin", user=self.user
        )
        mock_htimporter.index.assert_called_with()

        # can't inspect response context because not called with test client
        # sanity check result
        assert response.status_code == 200

    def test_get(self):
        # denied to anonymous user; django redirects to login
        assert self.client.get(self.add_from_hathi_url).status_code == 302

        # denied to logged in staff user
        self.client.login(**self.test_credentials)
        assert self.client.get(self.add_from_hathi_url).status_code == 403

        # works for user with add permission on digitized work
        add_digwork_perm = Permission.objects.get(codename="add_digitizedwork")
        self.user.user_permissions.add(add_digwork_perm)
        response = self.client.get(self.add_from_hathi_url)
        assert response.status_code == 200

        self.assertTemplateUsed(response, AddFromHathiView.template_name)
        # sanity check that form display
        self.assertContains(response, "<form")
        self.assertContains(response, '<textarea name="hathi_ids"')

    @patch("ppa.archive.views.HathiImporter")
    def test_post(self, mock_hathi_importer):
        mock_htimporter = mock_hathi_importer.return_value
        # set mock existing id & imported work on the mock importer
        mock_htimporter.existing_ids = {"old": 1}
        mock_htimporter.imported_works = [Mock(source_id="new", pk=2)]
        mock_htimporter.output_results.return_value = {
            "old": mock_hathi_importer.SKIPPED,
            "new": mock_hathi_importer.SUCCESS,
        }

        self.client.login(**self.superuser)
        response = self.client.post(self.add_from_hathi_url, {"hathi_ids": "old\nnew"})
        assert response.status_code == 200
        self.assertContains(response, "Processed 2 HathiTrust Identifiers")
        # inspect context
        assert response.context["results"] == mock_htimporter.output_results()
        assert response.context["existing_ids"] == mock_htimporter.existing_ids
        assert isinstance(response.context["form"], AddFromHathiForm)
        assert response.context["page_title"] == AddFromHathiView.page_title
        assert "admin_urls" in response.context
        assert response.context["admin_urls"]["old"] == reverse(
            "admin:archive_digitizedwork_change", args=[1]
        )
        assert response.context["admin_urls"]["new"] == reverse(
            "admin:archive_digitizedwork_change", args=[2]
        )

        # should redisplay the form
        self.assertContains(response, "<form")
        self.assertContains(response, '<textarea name="hathi_ids"')
