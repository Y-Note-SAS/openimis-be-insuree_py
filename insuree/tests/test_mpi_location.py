from unittest import mock

from django.test import SimpleTestCase

from insuree.apps import InsureeConfig
from insuree.mpi.exceptions import MpiAmbiguous, MpiInvalidPayload
from insuree.mpi.location import get_default_location


class MpiLocationTestCase(SimpleTestCase):
    @mock.patch("insuree.mpi.location.Location.objects.filter")
    def test_returns_single_active_location(self, locations):
        locations.return_value.count.return_value = 1
        locations.return_value.first.return_value = mock.Mock(id=42)

        location = get_default_location()

        self.assertEqual(location.id, 42)
        locations.assert_called_once_with(
            code=InsureeConfig.mpi_default_location_code, validity_to__isnull=True
        )

    @mock.patch("insuree.mpi.location.Location.objects.filter")
    def test_missing_location_raises(self, locations):
        locations.return_value.count.return_value = 0

        with self.assertRaises(MpiInvalidPayload):
            get_default_location()

    @mock.patch("insuree.mpi.location.Location.objects.filter")
    def test_multiple_locations_raise(self, locations):
        locations.return_value.count.return_value = 2

        with self.assertRaises(MpiAmbiguous):
            get_default_location()

    @mock.patch.object(InsureeConfig, "mpi_default_location_code", None)
    def test_missing_configuration_raises(self):
        with self.assertRaises(MpiInvalidPayload):
            get_default_location()
