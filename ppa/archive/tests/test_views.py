import csv
import html
import operator
import re
import uuid
from io import StringIO
from time import sleep
from unittest.mock import Mock, patch
from collections import defaultdict

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

from ppa.archive.forms import ImportForm, ModelMultipleChoiceFieldWithEmpty, SearchForm
from ppa.archive.models import NO_COLLECTION_LABEL, Collection, DigitizedWork, Cluster
from ppa.archive.solr import ArchiveSearchQuerySet
from ppa.archive.templatetags.ppa_tags import (
    gale_page_url,
    hathi_page_url,
    page_image_url,
)
from ppa.archive.views import DigitizedWorkListView, ImportView


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

        # volume should be present twice: field label + search within
        self.assertContains(
            response,
            "Volume",
            count=2,
            msg_prefix="Volume field should not display if no enumcron is set",
        )

        self.assertContains(
            response,
            self.dial.enumcron,
            msg_prefix="Volume field should display if enumcron is set",
        )

    def test_anonymous_display_no_volume(self):
        # test a fixture record with no enumcron
        digwork = DigitizedWork.objects.get(source_id="chi.13880510")
        response = self.client.get(digwork.get_absolute_url())
        assert not digwork.enumcron
        #
        self.assertContains(
            response,
            "Volume",
            count=1,
            msg_prefix="Volume metadata should not display if no enumcron",
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
        response = self.client.get(dial_excerpt.get_absolute_url())
        assert response.status_code == 200
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
        sample_page_content_other = [
            'wintry winter wonderlands require dials and compasses', 
            'this page is about the hot climes of the summer'
        ]
        htid = "chi.13880510"
        htid_other = "uc1.$b14645"
        
        # NOTE: sample page index data must be updated if page indexing changes
        def get_solr_page_docs(htid, docs):
            return [
                {
                    "content": content,
                    "order": i,
                    "item_type": "page",
                    "source_id": htid,
                    "id": "%s.%s" % (htid, i),
                    "group_id_s": htid,  # group id for non-excerpt = source id
                }
                for i, content in enumerate(docs)
            ]

        # get solr pages
        solr_page_docs = get_solr_page_docs(htid,sample_page_content)
        solr_page_docs+= get_solr_page_docs(htid_other,sample_page_content_other)

        # assign clusters
        cl1 = Cluster(cluster_id='treatisewinter')
        cl2 = Cluster(cluster_id='anothercluster')
        cl3 = Cluster(cluster_id='dialcluster')
        cl1.save()
        cl2.save()
        cl3.save()
        clustk = 'cluster_id_s'
        cluster_objs = {}
        work_docs = [dw.index_data() for dw in DigitizedWork.objects.all()]
        index_data = work_docs + solr_page_docs

        for d in index_data:
            sid=d['source_id']
            if sid == htid:
                d[clustk] = cl1.cluster_id
                cluster_objs[sid]=cl1

            elif sid in {"chi.78013704", "chi.78013677"}:
                
                d[clustk] = cl3.cluster_id
                cluster_objs[sid]=cl3
            
            elif sid == htid_other:
                d[clustk] = htid_other
            
            else:
                d[clustk] = cl2.cluster_id
                cluster_objs[sid]=cl2

        for dw in DigitizedWork.objects.all():
            cluster = cluster_objs.get(dw.source_id)
            if cluster:
                dw.cluster = cluster
                dw.save()


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

        # assemble a dictionary of cluster -> list of works within that cluster
        cluster2works = defaultdict(list)
        all_works = DigitizedWork.objects.all()
        for digwork in all_works:
            # using this instead of digwork.cluster_id_is for consistency with other tests
            digwork_index_data = digwork.index_data()
            cluster = digwork_index_data.get('cluster_id_s')
            # double checking that they're the same though:
            assert digwork_index_data.get('cluster_id_s') == digwork.index_cluster_id
            cluster2works[cluster].append(digwork)
            
        # assert that shown are number of *clusters* not number of works
        num_clusters = len(cluster2works)
        num_works = len(all_works)
        self.assertContains(
            response, "%d digitized works" % num_clusters
        )
        self.assertNotContains(
            response, "%d digitized works" % num_works
        )

        # are results numbered?
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
    
        # we need to assert that *at least one* work within each cluster has its metadata shown
        response_str = response.content.decode()
        attrs_to_test=['title','subtitle','author','enumcron','pub_date']
        for cluster,works in cluster2works.items():
            # assertion is similar for all these attrs
            for attr in attrs_to_test:
                assert any(str(getattr(w,attr)) in response_str for w in works)
            # at least one publisher includes an ampersand, so escape text
            assert any(escape(w.publisher) in response_str for w in works)
            # self.assertContains(response, digwork.pub_place)   # <- this was already commented, I believe because we're not showing it any longer?
            # link to detail page
            assert any(w.get_absolute_url() in response_str for w in works)
            # unapi identifier for each work
            assert any(
                ('<abbr class="unapi-id" title="%s"' % w.index_id()) in response_str
                for w in works
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
        response = self.client.get(self.url, {"query": "wintry", "sort":"relevance"})

        # relevance sort for keyword search
        assert len(response.context["object_list"]) == 2       # 2 hits: 1 in a cluster, 1 not
        self.assertContains(response, "2 digitized works")
        self.assertContains(response, self.wintry.source_id)    # has hits for wintry search
        self.assertNotContains(response, self.dial.source_id)   # no hits for wintry
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

        # need to unescape to test query args below
        htmlstr=html.unescape(response.content.decode())

        # 2 results but one cluster
        assert htmlstr.count("search and browse within cluster") == 1
        
        # link preserves args
        assert '/archive/?cluster=treatisewinter&query=wintry&sort=relevance&page=1' in htmlstr
        
        # the non-cluster hit should appear
        assert '/archive/uc1.$b14645/?query=wintry' in htmlstr   
        
        # no hits for wintry in this cluster
        print(htmlstr)
        assert '/archive/?cluster=anothercluster' not in htmlstr     


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
        html=response.content.decode()
        assert any(   # in the fixture both of these 2 hits are in the same cluster. the logic which of them is first/shown is independent so let's check for 1/any of them
            digwork.source_id in html
            for digwork in DigitizedWork.objects.filter(publisher__icontains="mcclurg")
        )

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
        ## get unique but sorted cluster ids in database                
        def _get_unique_list(l1):
            l2=[]
            for x in l1:
                if not x in l2:
                    l2.append(x)
            return l2
        sorted_cluster_ids_date = _get_unique_list(dw.index_cluster_id for dw in DigitizedWork.objects.order_by("pub_date"))
        sorted_cluster_ids_date_rev = _get_unique_list(dw.index_cluster_id for dw in DigitizedWork.objects.order_by("-pub_date"))
        sorted_cluster_ids_title = _get_unique_list(dw.index_cluster_id for dw in DigitizedWork.objects.order_by("title"))

        ## get unique but sorted cluster ids from response
        def _get_unique_list_response(response):
            return _get_unique_list(work["cluster_id"] for work in response.context["object_list"])
        response_sorted_cluster_ids_date = _get_unique_list_response(self.client.get(self.url, {"sort": "pub_date_asc"}))
        response_sorted_cluster_ids_date_rev = _get_unique_list_response(self.client.get(self.url, {"sort": "pub_date_desc"}))
        response_sorted_cluster_ids_title = _get_unique_list_response(self.client.get(self.url, {"query": "", "sort": "title_asc"}))

        ## these should match
        assert sorted_cluster_ids_date == response_sorted_cluster_ids_date
        assert sorted_cluster_ids_date_rev == response_sorted_cluster_ids_date_rev
        assert sorted_cluster_ids_title == response_sorted_cluster_ids_title



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
        works = DigitizedWork.objects.all()
        num_works = works.count()
        clusters = set(w.index_data().get('cluster_id_s') for w in works)
        num_clusters = len(clusters)
        num_respobjs = len(response.context["object_list"])

        print([num_works, num_respobjs, num_clusters])
        assert num_respobjs==num_clusters # used to be num_works: no longer!

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
            mock_qs.get_facets.side_effect = requests.exceptions.ConnectionError
            # return main mock when paginated
            mock_qs.__getitem__.return_value = mock_qs
            # count needed for paginator
            mock_qs.count.return_value = 0
            # simulate empty result doc for last modified check
            mock_qs.return_value.__getitem__.return_value = {}
            mock_qs.get_facets.return_value.facet_ranges = {"pub_date": []}
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

    @patch.object(DigitizedWork, "index_items")
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
    def test_get_pages(self):

        digworkview = DigitizedWorkListView()

        # mock PagedSolrQuery to inspect that query is generated properly
        with patch(
            "ppa.archive.views.SolrQuerySet", new=self.mock_solr_queryset()
        ) as mock_queryset_cls:

            solrq = mock_queryset_cls()

            # no keyword search, doesn't look for pages or highlights
            assert digworkview.get_pages(solrq) == ({}, {})

            # search term but no works found
            digworkview.query = "iambic"
            solrq.count.return_value = 0
            assert digworkview.get_pages(solrq) == ({}, {})

            solrq.count.return_value = 10
            solrq.__iter__.return_value = [
                {"id": "work1"},
                {"id": "work2"},
            ]

            pages, highlights = digworkview.get_pages(solrq)

            mock_queryset_cls.assert_called_with()
            mock_qs = mock_queryset_cls.return_value
            mock_qs.search.assert_any_call(content="(iambic)")
            mock_qs.filter.assert_any_call(item_type="page")
            mock_qs.filter.assert_any_call(group_id_s__in=['"work1"', '"work2"'])
            mock_qs.group.assert_called_with("group_id_s", limit=2, sort="score desc")
            mock_qs.highlight.assert_called_with(
                "content", snippets=3, method="unified"
            )
            mock_qs.get_response.assert_called_with(rows=100)

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


class TestImportView(TestCase):

    superuser = {"username": "super", "password": str(uuid.uuid4())}

    def setUp(self):
        self.factory = RequestFactory()
        self.import_url = reverse("admin:import")

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
        add_from_hathi = ImportView()
        add_from_hathi.request = self.factory.get(self.import_url)
        context = add_from_hathi.get_context_data()
        assert context["page_title"] == ImportView.page_title

    @patch("ppa.archive.views.HathiImporter")
    def test_form_valid(self, mock_hathi_importer):
        post_data = {"source_ids": "old\nnew", "source": DigitizedWork.HATHI}
        add_form = ImportForm(post_data)
        assert add_form.is_valid()

        mock_htimporter = mock_hathi_importer.return_value
        # set mock existing id & imported work on the mock importer
        mock_htimporter.existing_ids = {"old": 1}
        mock_htimporter.imported_works = [Mock(source_id="new", pk=2)]

        add_from_hathi = ImportView()
        add_from_hathi.request = self.factory.post(self.import_url, post_data)
        add_from_hathi.request.user = self.user
        response = add_from_hathi.form_valid(add_form)

        mock_hathi_importer.assert_called_with(add_form.get_source_ids())
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
        assert self.client.get(self.import_url).status_code == 302

        # denied to logged in staff user
        self.client.login(**self.test_credentials)
        assert self.client.get(self.import_url).status_code == 403

        # works for user with add permission on digitized work
        add_digwork_perm = Permission.objects.get(codename="add_digitizedwork")
        self.user.user_permissions.add(add_digwork_perm)
        response = self.client.get(self.import_url)
        assert response.status_code == 200

        self.assertTemplateUsed(response, ImportView.template_name)
        # sanity check that form display
        self.assertContains(response, "<form")
        self.assertContains(response, '<textarea name="source_ids"')

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
        response = self.client.post(
            self.import_url,
            {"source_ids": "old\nnew", "source": DigitizedWork.HATHI},
        )
        assert response.status_code == 200
        self.assertContains(response, "Processed 2 HathiTrust Identifiers")
        # inspect context
        assert response.context["results"] == mock_htimporter.output_results()
        assert response.context["existing_ids"] == mock_htimporter.existing_ids
        assert isinstance(response.context["form"], ImportForm)
        assert response.context["page_title"] == ImportView.page_title
        assert "admin_urls" in response.context
        assert response.context["admin_urls"]["old"] == reverse(
            "admin:archive_digitizedwork_change", args=[1]
        )
        assert response.context["admin_urls"]["new"] == reverse(
            "admin:archive_digitizedwork_change", args=[2]
        )

        # should redisplay the form
        self.assertContains(response, "<form")
        self.assertContains(response, '<textarea name="source_ids"')

    @patch("ppa.archive.views.GaleImporter")
    def test_post_gale(self, mock_gale_importer):
        mock_importer = mock_gale_importer.return_value
        # set mock existing id & imported work on the mock importer
        mock_importer.existing_ids = {"old": 1}
        mock_importer.imported_works = [Mock(source_id="new", pk=2)]
        mock_importer.output_results.return_value = {
            "old": mock_gale_importer.SKIPPED,
            "new": mock_gale_importer.SUCCESS,
        }

        self.client.login(**self.superuser)
        response = self.client.post(
            self.import_url,
            {"source_ids": "old\nnew", "source": DigitizedWork.GALE},
        )
        assert response.status_code == 200
        self.assertContains(response, "Processed 2 Gale Identifiers")
        # inspect context briefly
        assert response.context["results"] == mock_importer.output_results()
        assert response.context["existing_ids"] == mock_importer.existing_ids
        assert isinstance(response.context["form"], ImportForm)
