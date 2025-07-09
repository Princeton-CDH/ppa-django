from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from ppa.archive.models import DigitizedWork


class TestUnAPIViews(TestCase):
    fixtures = ["sample_digitized_works"]

    def test_unapi(self):
        unapi_url = reverse("unapi")

        # no id/format - get list of available formats as xml
        response = self.client.get(unapi_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<formats>")
        self.assertContains(response, '<format name="dc" type="application/xml"/>')

        # with id but no metadata
        test_id = "htid1234"
        response = self.client.get(unapi_url, {"id": test_id})
        self.assertContains(response, '<formats id="%s">' % test_id)

        # bogus id should 404
        response = self.client.get(unapi_url, {"id": test_id, "format": "dc"})
        self.assertEqual(response.status_code, 404)

        # excerpt id should work (now that we support excerpts)
        response = self.client.get(
            unapi_url, {"id": "%s-p43" % test_id, "format": "dc"}
        )
        self.assertEqual(response.status_code, 404)

        # valid id and format
        digwork = DigitizedWork.objects.first()
        with patch("ppa.unapi.views.get_object_or_404") as mock_getobj:
            mock_metadata_result = "some metadata"
            mock_getobj.return_value.get_metadata.return_value = mock_metadata_result

            response = self.client.get(
                unapi_url, {"id": digwork.index_id(), "format": "dc"}
            )

            mock_getobj.return_value.get_metadata.assert_called_with(
                "dc", item_id=digwork.source_id
            )
            self.assertContains(response, mock_metadata_result)
            # dc format displays in browser, no content-disposition header expected
