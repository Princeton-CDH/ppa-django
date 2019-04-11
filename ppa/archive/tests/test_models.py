from datetime import date, timedelta
import json
import os.path
from time import sleep
import types
from unittest.mock import patch, Mock
from zipfile import ZipFile

from django.conf import settings
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models.query import QuerySet
from django.test import TestCase, override_settings
from django.urls import reverse
from eulxml.xmlmap import load_xmlobject_from_file
from pairtree import pairtree_client, pairtree_path, storage_exceptions
import pytest

from ppa.archive import hathi
from ppa.archive.models import DigitizedWork, Collection, \
    NO_COLLECTION_LABEL, ProtectedWorkFieldFlags, CollectionSignalHandlers
from ppa.archive.solr import get_solr_connection, Indexable


FIXTURES_PATH = os.path.join(settings.BASE_DIR, 'ppa', 'archive', 'fixtures')


class TestProtectedFlags(TestCase):

    def test_deconstruct(self):
        ret = ProtectedWorkFieldFlags.deconstruct()
        assert ret[0] == 'ppa.archive.models.ProtectedWorkFieldFlags'
        assert ret[1] == ['no_flags']
        assert ret[2] == {}

    def test_str(self):
        fields = ProtectedWorkFieldFlags.enumcron | ProtectedWorkFieldFlags.title | \
            ProtectedWorkFieldFlags.sort_title
        assert str(fields) == 'enumcron, sort_title, title'


@pytest.mark.django_db
class TestCollectionSignalHandlers:

    @patch.object(Indexable, 'index_items')
    def test_save(self, mock_index_items):
        digwork = DigitizedWork.objects.create(source_id='njp.32101013082597')
        coll1 = Collection.objects.create(name='Flotsam')
        digwork.collections.add(coll1)

        CollectionSignalHandlers.save(Mock(), coll1)
        # index not called because collection name has not changed
        mock_index_items.assert_not_called()

        # modify name to test indexing
        coll1.name = 'Jetsam'
        CollectionSignalHandlers.save(Mock(), coll1)
        # call must be inspected piecemeal because queryset equals comparison fails
        args, kwargs = mock_index_items.call_args
        assert isinstance(args[0], QuerySet)
        assert digwork in args[0]
        assert kwargs['params'] == {'commitWithin': 3000}

    @patch.object(Indexable, 'index_items')
    def test_delete(self, mock_index_items):
        digwork = DigitizedWork.objects.create(source_id='njp.32101013082597')
        coll1 = Collection.objects.create(name='Flotsam')
        digwork.collections.add(coll1)

        CollectionSignalHandlers.delete(Mock(), coll1)

        assert coll1.digitizedwork_set.count() == 0
        args, kwargs = mock_index_items.call_args
        assert isinstance(args[0], QuerySet)
        assert digwork in args[0]
        assert kwargs['params'] == {'commitWithin': 3000}


class TestDigitizedWork(TestCase):
    fixtures = ['sample_digitized_works']

    bibdata_full = os.path.join(
        FIXTURES_PATH, 'bibdata_full_njp.32101013082597.json')
    bibdata_full2 = os.path.join(
        FIXTURES_PATH, 'bibdata_full_aeu.ark_13960_t1pg22p71.json')
    bibdata_brief = os.path.join(
        FIXTURES_PATH, 'bibdata_brief_njp.32101013082597.json')
    metsfile = os.path.join(FIXTURES_PATH, '79279237.mets.xml')

    def test_str(self):
        digwork = DigitizedWork(source_id='njp.32101013082597')
        assert str(digwork) == digwork.source_id

    def test_display_title(self):
        digwork = DigitizedWork(title='Elocutionary Language')
        assert digwork.display_title() == digwork.title

    def test_has_fulltext(self):
        digwork = DigitizedWork(title='Elocutionary Language')
        # should be hathi (thus have fulltext) by default
        assert digwork.has_fulltext
        digwork.source = DigitizedWork.OTHER
        # for non-hathi items, shouldn't have full text
        assert not digwork.has_fulltext
        
    def test_hathi(self):
        digwork = DigitizedWork(source_id='njp.32101013082597',
                                source=DigitizedWork.HATHI)
        assert isinstance(digwork.hathi, hathi.HathiObject)
        assert digwork.hathi.hathi_id == digwork.source_id

        # not returned for non-hathi objects
        digwork = DigitizedWork(source_id='foobar',
                                source=DigitizedWork.OTHER)
        assert digwork.hathi is None

    @pytest.mark.usefixtures('solr')
    def test_index(self):
        with open(self.bibdata_brief) as bibdata:
            brief_bibdata = hathi.HathiBibliographicRecord(json.load(bibdata))

        digwork = DigitizedWork(source_id='njp.32101013082597')
        digwork.populate_from_bibdata(brief_bibdata)
        digwork.save()
        solr, solr_collection = get_solr_connection()
        # digwork should be unindexed
        res = solr.query(solr_collection, {'q': '*:*'})
        assert res.get_results_count() == 0
        # reindex to check that the method works on a saved object
        digwork.index()
        # digwork should be unindexed still because no commitWithin
        res = solr.query(solr_collection, {'q': '*:*'})
        assert res.get_results_count() == 0
        digwork.index(params={'commitWithin': 500})
        sleep(1)
        # digwork should be returned by a query
        res = solr.query(solr_collection, {'q': '*:*'})
        assert res.get_results_count() == 1
        assert res.docs[0]['id'] == 'njp.32101013082597'

    def test_compare_protected_fields(self):

        digwork = DigitizedWork(
            source_id='testid',
            title='Fake Title',
            enumcron='02',
            pub_place='Paris',
            protected_fields=ProtectedWorkFieldFlags.all_flags
        )
        # change title and pub_place, leave enumcron
        db_digwork = DigitizedWork(
            source_id='testid2',
            title='New Title',
            enumcron='02',
            pub_place='London',
            protected_fields=ProtectedWorkFieldFlags.all_flags
        )


        changed_fields = digwork.compare_protected_fields(db_digwork)
        assert 'title' in changed_fields
        assert 'pub_place' in changed_fields
        # source_id isn't a protected field so it shouldn't ever be in
        # changed_fields
        assert 'source_id' not in changed_fields
        assert 'enumcron' not in changed_fields

    def test_populate_fields(self):
        digwork = DigitizedWork(
            source_id='testid',
            title='Fake Title',
            enumcron='02',
            pub_place='Paris',
            protected_fields=ProtectedWorkFieldFlags.enumcron
            )
        field_dict = {
            'title': 'Test Title',
            'enumcron': '01',
            'pub_place': 'London'
        }
        digwork.populate_fields(field_dict)
        # protected field was protected
        assert digwork.enumcron == '02'
        # unprotected fields are updated
        assert digwork.title == 'Test Title'
        assert digwork.pub_place == 'London'

    def test_populate_from_bibdata(self):
        with open(self.bibdata_full) as bibdata:
            full_bibdata = hathi.HathiBibliographicRecord(json.load(bibdata))

        with open(self.bibdata_brief) as bibdata:
            brief_bibdata = hathi.HathiBibliographicRecord(json.load(bibdata))

        digwork = DigitizedWork(source_id='njp.32101013082597')
        digwork.populate_from_bibdata(brief_bibdata)
        assert digwork.record_id == brief_bibdata.record_id
        assert digwork.title == brief_bibdata.title
        assert digwork.pub_date == brief_bibdata.pub_dates[0]
        # no enumcron in this record
        assert digwork.enumcron == ''
        # fields from marc not set
        assert not digwork.author
        assert not digwork.pub_place
        assert not digwork.publisher

        # test no pub date
        brief_bibdata.info['publishDates'] = []
        digwork = DigitizedWork(source_id='njp.32101013082597')
        digwork.populate_from_bibdata(brief_bibdata)
        assert not digwork.pub_date

        # TODO: test enumcron from copy details

        # populate from full record
        digwork.populate_from_bibdata(full_bibdata)
        # title and subtitle set from marc
        assert digwork.title == full_bibdata.marcxml['245']['a']
        assert digwork.subtitle == full_bibdata.marcxml['245']['b']
        # fixture has indicator 0, no non-sort characters
        assert digwork.sort_title == ' '.join([digwork.title, digwork.subtitle])
        # authors should have trailing period removed
        assert digwork.author == full_bibdata.marcxml.author().rstrip('.')
        # comma should be stripped from publication place and publisher
        assert digwork.pub_place == full_bibdata.marcxml['260']['a'].strip(',')
        assert digwork.publisher == full_bibdata.marcxml['260']['b'].strip(',')

        # second bibdata record with sort title
        with open(self.bibdata_full2) as bibdata:
            full_bibdata = hathi.HathiBibliographicRecord(json.load(bibdata))

        digwork = DigitizedWork(source_id='aeu.ark:/13960/t1pg22p71')
        digwork.populate_from_bibdata(full_bibdata)
        assert digwork.title == full_bibdata.marcxml['245']['a']
        # subtitle should omit last two characters (trailing space and slash)
        assert digwork.subtitle == full_bibdata.marcxml['245']['b'][:-2]
        # fixture has title with non-sort characters
        assert digwork.sort_title == ' '.join([
            digwork.title[int(full_bibdata.marcxml['245'].indicators[1]):],
            full_bibdata.marcxml['245']['b']
        ])
        # store title before modifying it for tests
        orig_bibdata_title = full_bibdata.marcxml['245']['a']

        # test error in record (title non-sort character non-numeric)
        with open(self.bibdata_full2) as bibdata:
            full_bibdata = hathi.HathiBibliographicRecord(json.load(bibdata))
            full_bibdata.marcxml['245'].indicators[1] = ' '
            digwork.populate_from_bibdata(full_bibdata)
            assert digwork.sort_title == \
                ' '.join([digwork.title, full_bibdata.marcxml['245']['b']])

            # test error in title sort (doesn't include space after definite article)
            full_bibdata.marcxml['245'].indicators[1] = 3
            digwork.populate_from_bibdata(full_bibdata)
            assert not digwork.sort_title.startswith(' ')

            # test cleaning up leading punctuation
            full_bibdata.marcxml['245'].indicators[1] = 0
            full_bibdata.marcxml['245']['a'] = '"Elocutionary Language."'
            digwork.populate_from_bibdata(full_bibdata)
            assert not digwork.sort_title.startswith('"')

            full_bibdata.marcxml['245']['a'] = "[Pamphlets on Language.]"
            digwork.populate_from_bibdata(full_bibdata)
            assert not digwork.sort_title.startswith('[')

        # test title cleanup
        full_bibdata.marcxml['245']['a'] = orig_bibdata_title
        # - remove trailing slash from title
        full_bibdata.marcxml['245']['a'] += ' /'
        digwork.populate_from_bibdata(full_bibdata)
        # title should omit last two characters
        assert digwork.title == orig_bibdata_title
        # - remove initial open bracket
        full_bibdata.marcxml['245']['a'] = '[{}'.format(orig_bibdata_title)
        digwork.populate_from_bibdata(full_bibdata)
        assert digwork.title == orig_bibdata_title
        # - internal brackets should be unchanged
        full_bibdata.marcxml['245']['a'] = 'A third[-fourth] class reader.'
        digwork.populate_from_bibdata(full_bibdata)
        assert digwork.title == full_bibdata.marcxml['245']['a']

        # author trailing period not removed for single initials
        # - name with initials, no date
        full_bibdata.marcxml['100']['a'] = 'Mitchell, M. S.'
        full_bibdata.marcxml['100']['d'] = ''
        digwork.populate_from_bibdata(full_bibdata)
        assert digwork.author == full_bibdata.marcxml['100']['a']
        # - initials with no space
        full_bibdata.marcxml['100']['a'] = 'Mitchell, M.S.'
        digwork.populate_from_bibdata(full_bibdata)
        assert digwork.author == full_bibdata.marcxml['100']['a']
        # - esquire
        full_bibdata.marcxml['100']['a'] = 'Wilson, Richard, Esq.'
        digwork.populate_from_bibdata(full_bibdata)
        assert digwork.author == full_bibdata.marcxml['100']['a']
        # - remove '[from old catalog]'
        full_bibdata.marcxml['100']['a'] = 'Thurber, Samuel. [from old catalog]'
        digwork.populate_from_bibdata(full_bibdata)
        assert digwork.author == 'Thurber, Samuel'

        # sine loco/nomine should be cleared out
        full_bibdata.marcxml['260']['a'] = '[S.l.]'
        full_bibdata.marcxml['260']['b'] = '[s.n.]'
        digwork.populate_from_bibdata(full_bibdata)
        assert not digwork.pub_place
        assert not digwork.publisher

        # brackets around publisher and pub place should be removed
        full_bibdata.marcxml['260']['a'] = '[London]'
        full_bibdata.marcxml['260']['b'] = '[Faber]'
        digwork.populate_from_bibdata(full_bibdata)
        assert digwork.pub_place == full_bibdata.marcxml['260']['a'].strip('[]')
        assert digwork.publisher == full_bibdata.marcxml['260']['b'].strip('[]')
        full_bibdata.marcxml['260']['a'] = 'New Brunswick [N.J.]'
        digwork.populate_from_bibdata(full_bibdata)
        assert digwork.pub_place == full_bibdata.marcxml['260']['a']

        # clean up publisher preliminary text
        publisher = 'James Humphreys'
        variants =  [
            'Printed at',
            'Printed and sold by',
            'Printed and published by',
            'Pub. for',
            'Published for the',
            'Publisht for the',
        ]
        for prefix in variants:
            full_bibdata.marcxml['260']['b'] = ' '.join([prefix, publisher])
            digwork.populate_from_bibdata(full_bibdata)
            assert digwork.publisher == publisher

        # handle subtitle, publisher, place of publication unset
        full_bibdata.marcxml['245']['b'] = None
        full_bibdata.marcxml['260']['a'] = None
        full_bibdata.marcxml['260']['b'] = None
        digwork.populate_from_bibdata(full_bibdata)
        assert digwork.subtitle == ''
        assert digwork.pub_place == ''
        assert digwork.publisher == ''

        # NOTE: not currently testing publication info unavailable

        with open(self.bibdata_full2) as bibdata:
            full_bibdata = hathi.HathiBibliographicRecord(json.load(bibdata))

        # test that protected fields are respected
        digwork = DigitizedWork(source_id='aeu.ark:/13960/t1pg22p71')
        # set each of the protected fields
        digwork.title = 'Fake title'
        digwork.subtitle = 'Silly subtitle'
        digwork.sort_title = 'Sort title fake'
        digwork.enumcron = '0001'
        digwork.author = 'Not an author'
        digwork.pub_place = 'Nowhere'
        digwork.publisher = 'Not a publisher'
        digwork.pub_date = 2200
        # set all fields as protected
        digwork.protected_fields = ProtectedWorkFieldFlags.all_flags
        # fake bibdata for empty fields

        full_bibdata.copy_details = Mock()
        full_bibdata.copy_details.return_value = {
            'enumcron': '0002',
            'itemURL': 'http://example.com',

        }
        # fields have not changed
        digwork.populate_from_bibdata(full_bibdata)
        assert digwork.title == 'Fake title'
        assert digwork.subtitle == 'Silly subtitle'
        assert digwork.sort_title == 'Sort title fake'
        assert digwork.enumcron == '0001'
        assert digwork.pub_place == 'Nowhere'
        assert digwork.publisher == 'Not a publisher'
        assert digwork.pub_date == 2200
        # check fallbacks for title
        digwork.populate_from_bibdata(full_bibdata)
        assert digwork.title == 'Fake title'
        assert digwork.subtitle == 'Silly subtitle'
        assert digwork.sort_title == 'Sort title fake'
        # no protected fields
        digwork.protected_fields = ProtectedWorkFieldFlags.no_flags
        digwork.populate_from_bibdata(full_bibdata)
        # all fields overwritten
        assert digwork.title != 'Fake title'
        assert digwork.subtitle != 'Silly subtitle'
        assert digwork.sort_title != 'Sort title fake'
        assert digwork.enumcron != '0001'
        assert digwork.pub_place != 'Nowhere'
        assert digwork.publisher != 'Not a publisher'
        assert digwork.pub_date != 2200

    def test_index_data(self):
        digwork = DigitizedWork.objects.create(
            source_id='njp.32101013082597',
            title='The Structure of English Verse', pub_date=1884,
            subtitle='An essay',
            sort_title='Structure of English Verse',
            author='Charles Witcomb', pub_place='Paris',
            publisher='Mesnil-Dramard',
            source_url='https://hdl.handle.net/2027/njp.32101013082597',
            public_notes='A note field here',
            notes='internal notes for curation')
        coll1 = Collection.objects.create(name='Flotsam')
        coll2 = Collection.objects.create(name='Jetsam')
        digwork.collections.add(coll1)
        digwork.collections.add(coll2)
        index_data = digwork.index_data()
        assert index_data['id'] == digwork.source_id
        assert index_data['source_id'] == digwork.source_id
        assert index_data['item_type'] == 'work'
        assert index_data['title'] == digwork.title
        assert index_data['subtitle'] == digwork.subtitle
        assert index_data['sort_title'] == digwork.sort_title
        assert index_data['author'] == digwork.author
        assert index_data['pub_place'] == digwork.pub_place
        assert index_data['pub_date'] == digwork.pub_date
        assert index_data['collections'] == ['Flotsam', 'Jetsam']
        assert index_data['publisher'] == digwork.publisher
        assert index_data['source_url'] == digwork.source_url
        assert digwork.public_notes in index_data['notes']
        assert digwork.notes not in index_data['notes']
        assert not index_data['enumcron']

        # with enumcron
        digwork.enumcron = 'v.7 (1848)'
        assert digwork.index_data()['enumcron'] == digwork.enumcron

        # not in a collection
        digwork.collections.clear()
        assert digwork.index_data()['collections'] == [NO_COLLECTION_LABEL]

        # suppressed
        digwork.status = digwork.SUPPRESSED
        # don't actually process the data deletion
        with patch.object(digwork, 'hathi'):
            digwork.save()

            # should *only* contain id, nothing else
            index_data = digwork.index_data()
            assert len(index_data) == 1
            assert index_data['id'] == digwork.source_id

    def test_get_absolute_url(self):
        work = DigitizedWork.objects.first()
        assert work.get_absolute_url() == \
            reverse('archive:detail', kwargs={'source_id': work.source_id})

    @patch('ppa.archive.models.HathiBibliographicAPI')
    def test_get_metadata(self, mock_hathibib):
        work = DigitizedWork(source_id='ht:1234')

        # unsupported metadata format should error
        with pytest.raises(ValueError):
            work.get_metadata('bogus')

        # for marc, should call hathi bib api and return marc in binary form
        mdata = work.get_metadata('marc')
        mock_hathibib.assert_any_call()
        mock_bibapi = mock_hathibib.return_value
        mock_bibapi.record.assert_called_with('htid', work.source_id)
        mock_bibdata = mock_bibapi.record.return_value
        mock_bibdata.marcxml.as_marc.assert_any_call()
        assert mdata == mock_bibdata.marcxml.as_marc.return_value

        # non-hathi record: for now, not supported
        nonhathi_work = DigitizedWork(source=DigitizedWork.OTHER, source_id='788423659')
        # should not error, but nothing to return
        assert not nonhathi_work.get_metadata('marc')


    @patch('ppa.archive.models.ZipFile', spec=ZipFile)
    def test_count_pages(self, mockzipfile):
        prefix, pt_id = ('ab', '12345:6')
        mock_pairtree_client = Mock(spec=pairtree_client.PairtreeStorageClient)
        digwork = DigitizedWork.objects.create(source_id='.'.join([prefix, pt_id]))

        pt_obj = mock_pairtree_client.get_object.return_value
        pt_obj.list_parts.return_value = ['12345.mets.xml', '12345.zip']
        pt_obj.id_to_dirpath.return_value = 'ab/path/12345+6'
        # parts = ptobj.list_parts(content_dir)
        # __enter__ required because zipfile used as context block
        mockzip_obj = mockzipfile.return_value.__enter__.return_value
        page_files = ['0001.txt', '00002.txt']
        mockzip_obj.namelist.return_value = page_files
        # simulate reading zip file contents
        # mockzip_obj.open.return_value.__enter__.return_value \
            # .read.return_value.decode.return_value = 'page content'

        # count the pages
        page_count = digwork.count_pages(mock_pairtree_client)

        # inspect pairtree logic
        mock_pairtree_client.get_object.assert_any_call(pt_id, create_if_doesnt_exist=False)
        # list parts called on encoded version of pairtree id
        content_dir = pairtree_path.id_encode(pt_id)
        pt_obj.list_parts.assert_any_call(content_dir)
        pt_obj.id_to_dirpath.assert_any_call()

        # inspect zipfile logic
        mockzip_obj.namelist.assert_called_with()

        zipfile_path = os.path.join(pt_obj.id_to_dirpath(), content_dir, '12345.zip')
        mockzipfile.assert_called_with(zipfile_path)

        # return total and digitized work page counts updated
        assert page_count == 2
        digwork = DigitizedWork.objects.get(source_id=digwork.source_id)
        assert digwork.page_count == 2

        # should ignore non-text files
        page_files = ['0001.txt', '00002.txt', '00001.jp2', '00002.jp2']
        mockzip_obj.namelist.return_value = page_files
        assert digwork.count_pages(mock_pairtree_client) == 2


        # object not found in pairtree data
        mock_pairtree_client.get_object.side_effect = \
            storage_exceptions.ObjectNotFoundException
        # should not error; should report not found
        with pytest.raises(storage_exceptions.ObjectNotFoundException):
            digwork.count_pages(mock_pairtree_client)

    @patch('ppa.archive.models.ZipFile', spec=ZipFile)
    @override_settings(HATHI_DATA='/tmp/ht_text_pd')
    def test_page_index_data(self, mockzipfile):
        mockzip_obj = mockzipfile.return_value.__enter__.return_value
        page_files = ['0001.txt', '00002.txt']
        mockzip_obj.namelist.return_value = page_files
        # simulate reading zip file contents
        contents = ('page content for one', 'hello! pshaw! what?')
        mockzip_obj.open.return_value.__enter__.return_value \
            .read.return_value.decode.side_effect = contents

        work = DigitizedWork(source_id='chi.79279237')

        # page data comes from mets
        mets = load_xmlobject_from_file(self.metsfile, hathi.MinimalMETS)
        with patch.object(DigitizedWork, 'hathi') as mock_hathiobj:
            mock_hathiobj.zipfile_path.return_value = '/path/to/79279237.zip'
            mock_hathiobj.metsfile_path.return_value = self.metsfile
            mock_hathiobj.content_dir = 'data'

            page_data = work.page_index_data()
            assert isinstance(page_data, types.GeneratorType)

            for i, data in enumerate(page_data):
                mets_page = mets.structmap_pages[i]
                assert data['id'] == '.'.join([work.source_id, mets_page.text_file.sequence])
                assert data['source_id'] == work.source_id
                assert data['content'] == contents[i]
                assert data['order'] == mets_page.order
                assert data['item_type'] == 'page'
                assert data['label'] == mets_page.display_label
                assert 'tags' in data
                assert data['tags'] == mets_page.label.split(', ')

            # not suppressed by no data
            mock_hathiobj.metsfile_path.side_effect = \
                storage_exceptions.ObjectNotFoundException
            # should log an error, not currently tested
            assert not list(work.page_index_data())

        # if item is suppressed - no page data
        work.status = DigitizedWork.SUPPRESSED
        assert not list(work.page_index_data())

        # non hathi item - no page data
        nonhathi_work = DigitizedWork(source=DigitizedWork.OTHER)
        assert not list(nonhathi_work.page_index_data())

    def test_index_id(self):
        work = DigitizedWork(source_id='chi.79279237')
        assert work.index_id() == work.source_id

    def test_save(self):
        work = DigitizedWork(source_id='chi.79279237')
        with patch.object(work, 'hathi') as mock_hathiobj:
            # no change in status - nothing should happen
            work.save()
            mock_hathiobj.delete_pairtree_data.assert_not_called()

            # change status to suppressed - data should be deleted
            work.status = work.SUPPRESSED
            work.save()
            assert mock_hathiobj.delete_pairtree_data.call_count == 1

            # changing status but not to suppressed - should not be called
            mock_hathiobj.reset_mock()
            work.status = work.PUBLIC
            work.save()
            mock_hathiobj.delete_pairtree_data.assert_not_called()

            # non-hathi record - should not try to delete hathi data
            work = DigitizedWork(source=DigitizedWork.OTHER)
            work.save()
            work.status = work.SUPPRESSED
            work.save()
            mock_hathiobj.delete_pairtree_data.assert_not_called()

        # if source_id changes, old id should be removed from solr index
        work = DigitizedWork.objects.create(source=DigitizedWork.OTHER,
                                            source_id='12345')
        with patch.object(work, 'remove_from_index') as mock_rm_from_index:
            work.source_id = 'abcdef'
            work.save()
            mock_rm_from_index.assert_called()

    def test_clean(self):
        work = DigitizedWork(source_id='chi.79279237')

        # no validation error
        work.clean()

        # change to suppressed - no problem
        work.status = work.SUPPRESSED
        work.clean()
        # don't actually process the data deletion
        with patch.object(work, 'hathi'):
            work.save()

        # try to change back - should error
        work.status = work.PUBLIC
        with pytest.raises(ValidationError):
            work.clean()

        # trying to change source id for hathi record should error
        work.source_id = '123456a'
        work.status = work.SUPPRESSED
        with pytest.raises(ValidationError):
            work.clean()

        # not an error for non-hathi
        work.source = DigitizedWork.OTHER
        work.clean()

    def test_is_suppressed(self):
        work = DigitizedWork(source_id='chi.79279237')
        assert not work.is_suppressed

        work.status = DigitizedWork.SUPPRESSED
        assert work.is_suppressed

    @patch('ppa.archive.models.DigitizedWork.populate_from_bibdata')
    @patch('ppa.archive.models.DigitizedWork.get_hathi_data')
    @patch('ppa.archive.models.HathiBibliographicAPI')
    def test_add_from_hathi(self, mock_hathibib_api, mock_get_hathi_data,
                            mock_pop_from_bibdata):

        script_user = User.objects.get(username=settings.SCRIPT_USERNAME)

        # add new with default opts
        test_htid = 'abc:12345'
        digwork = DigitizedWork.add_from_hathi(test_htid)
        assert isinstance(digwork, DigitizedWork)
        mock_hathibib_api.assert_called_with()
        mock_hathibib = mock_hathibib_api.return_value
        mock_hathibib.record.assert_called_with('htid', test_htid)
        mock_pop_from_bibdata.assert_called_with(mock_hathibib.record.return_value)
        mock_get_hathi_data.assert_not_called()

        # log entry should exist for record creation only
        log_entries = LogEntry.objects.filter(object_id=digwork.id)
        # should only be one log entry
        assert log_entries.count() == 1
        log_entry = log_entries.first()
        assert log_entry.user == script_user
        assert log_entry.content_type == ContentType.objects.get_for_model(DigitizedWork)
        # default log message for new record
        assert log_entry.change_message == 'Created from HathiTrust bibliographic data'
        assert log_entry.action_flag == ADDITION

        # add new with bib api pased in, get data, and custom message
        my_bib_api = Mock()
        mock_hathibib_api.reset_mock()
        test_htid = 'def:678910'
        digwork = DigitizedWork.add_from_hathi(
            test_htid, bib_api=my_bib_api, get_data=True,
            log_msg_src='in unit tests')
        mock_hathibib_api.assert_not_called()
        my_bib_api.record.assert_called_with('htid', test_htid)
        assert mock_get_hathi_data.call_count == 1
        log_entry = LogEntry.objects.get(object_id=digwork.id)
        assert log_entry.change_message == 'Created in unit tests'

        # update existing record - no change on hathi, not forced
        digwork_updated = digwork.updated  # store local record updated time
        mockhathirecord = mock_hathibib.record.return_value
        # set hathi record last updated before digwork last update
        mockhathirecord.copy_last_updated.return_value = date.today() - timedelta(days=1)
        digwork = DigitizedWork.add_from_hathi(test_htid)
        # bib api should still be called
        mock_hathibib.record.assert_called_with('htid', test_htid)
        # record update time should be unchanged
        assert digwork.updated == digwork_updated
        # still only one log entry
        assert LogEntry.objects.filter(object_id=digwork.id).count() == 1

        # update existing record - no change on hathi, update forced
        mock_pop_from_bibdata.reset_mock()
        digwork = DigitizedWork.add_from_hathi(test_htid, update=True)
        # record update time should be changed
        assert digwork.updated != digwork_updated
        mock_pop_from_bibdata.assert_called_with(mock_hathibib.record.return_value)
        # new log entry should be added
        assert LogEntry.objects.filter(object_id=digwork.id).count() == 2
        # log entry should exist for record update; get newest
        log_entry = LogEntry.objects.filter(object_id=digwork.id) \
            .order_by('-action_time').first()
        assert log_entry.action_flag == CHANGE
        assert log_entry.change_message.startswith('Updated')
        assert '(forced update)' in log_entry.change_message

        # update existing record - changed on hathi, should auto update
        # set hathi record last updated *after* digwork last update
        mock_pop_from_bibdata.reset_mock()
        mockhathirecord.copy_last_updated.return_value = date.today() + timedelta(days=1)
        digwork_updated = digwork.updated  # store local record updated time
        digwork = DigitizedWork.add_from_hathi(test_htid)
        # record update time should be changed
        assert digwork.updated != digwork_updated
        mock_pop_from_bibdata.assert_called_with(mock_hathibib.record.return_value)
        # new log entry should be added
        assert LogEntry.objects.filter(object_id=digwork.id).count() == 3
        # newest log entry should be an update
        assert LogEntry.objects.filter(object_id=digwork.id) \
            .order_by('-action_time').first().action_flag == CHANGE

    @patch('ppa.archive.models.HathiDataAPI')
    def test_get_hathi_data(self, mock_hathidata_api):
        # should do nothing for non-hathi record
        non_hathi_work = DigitizedWork(source=DigitizedWork.OTHER)
        non_hathi_work.get_hathi_data()
        mock_hathidata_api.assert_not_called()

        mock_hathidata = mock_hathidata_api.return_value
        mets_filename = 'ht.12358.mets.xml'
        mock_hathidata.get_structure.return_value.headers = {
            'content-disposition': mets_filename
        }
        zip_filename = 'ht.12358.zip'
        mock_hathidata.get_aggregate.return_value.headers = {
            'content-disposition': 'filename=%s' % zip_filename
        }

        digwork = DigitizedWork(source_id='ht:12358')
        with patch.object(digwork, 'hathi') as mock_hathiobj:
            with patch.object(digwork, 'count_pages') as mock_count_pages:
                mock_hathiobj.content_dir = 'my/pairtree/content/dir'
                digwork.get_hathi_data()

                # should initialize hathi data api client
                mock_hathidata_api.assert_called_with()

                # should get pairtree object & create if necessary
                mock_hathiobj.pairtree_object.assert_called_with(create=True)
                pairtree_obj = mock_hathiobj.pairtree_object.return_value
                # should get structure xml (METS)
                mock_hathidata.get_structure.assert_called_with(digwork.source_id)
                # should add mets to pairtree based on filename in response header
                expect_mets_filename = os.path.join(
                    mock_hathiobj.content_dir, mets_filename)
                mets_response = mock_hathidata.get_structure.return_value
                print(pairtree_obj.add_bytestream_by_path.call_args_list)
                pairtree_obj.add_bytestream_by_path.assert_any_call(
                    expect_mets_filename, mets_response.content)
                # should add zip to pairtree similarly
                expect_zip_filename = os.path.join(
                    mock_hathiobj.content_dir, zip_filename)
                zip_response = mock_hathidata.get_aggregate.return_value
                pairtree_obj.add_bytestream_by_path.assert_any_call(
                    expect_zip_filename, zip_response.content)

                mock_count_pages.assert_called_with()


class TestCollection(TestCase):
    fixtures = ['sample_digitized_works']

    def test_str(self):
        collection = Collection(name='Random Assortment')
        assert str(collection) == 'Random Assortment'

    def test_name_changed(self):
        collection = Collection(name='Random Assortment')
        assert not collection.name_changed
        # change the name
        collection.name = 'Randomer'
        assert collection.name_changed
        # save changes; should no longer be marked as changed
        collection.save()
        assert not collection.name_changed

    @pytest.mark.usefixtures("solr")
    def test_stats(self):
        # test collection stats from Solr

        coll1 = Collection.objects.create(name='Random Grabbag')
        coll2 = Collection.objects.create(
            name='Foo through Time',
            description="A <em>very</em> useful collection."
        )

        # add items to collections
        # - put everything in collection 1
        digworks = DigitizedWork.objects.all()
        for digwork in digworks:
            digwork.collections.add(coll1)
        # just one item in collection 2
        wintry = digworks.get(title__icontains='Wintry')
        wintry.collections.add(coll2)

        # reindex the digitized works so we can check stats
        solr, solr_collection = get_solr_connection()
        solr.index(solr_collection, [dw.index_data() for dw in digworks],
                   params={"commitWithin": 100})
        sleep(2)

        stats = Collection.stats()
        assert stats[coll1.name]['count'] == digworks.count()
        assert stats[coll1.name]['dates'] == '1880–1904'
        assert stats[coll2.name]['count'] == 1
        assert stats[coll2.name]['dates'] == '1903'
