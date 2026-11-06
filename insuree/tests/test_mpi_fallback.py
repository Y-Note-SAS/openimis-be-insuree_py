from unittest import mock

from django.test import TestCase
from graphql import GraphQLError

from insuree.apps import InsureeConfig
from insuree.mpi.exceptions import MpiAmbiguous, MpiUnavailable
from insuree.schema import Query
from insuree.test_helpers import create_test_insuree


class MpiFallbackTestCase(TestCase):
    def setUp(self):
        user = mock.Mock()
        user.has_perms.return_value = True
        user._u.is_imis_admin = True
        self.info = mock.Mock()
        self.info.context.user = user

        patcher = mock.patch(
            "insuree.schema.gql_optimizer.query", side_effect=lambda qs, info: qs
        )
        patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch.object(InsureeConfig, "mpi_fallback_enabled", True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def resolve(self, **kwargs):
        return Query.resolve_insurees(None, self.info, **kwargs)

    @mock.patch("insuree.schema.MpiClient")
    def test_flag_off_makes_no_call(self, client):
        with mock.patch.object(InsureeConfig, "mpi_fallback_enabled", False):
            queryset = self.resolve(chfId="CH-404", ignoreLocation=True)

        self.assertFalse(queryset.exists())
        client.assert_not_called()

    @mock.patch("insuree.schema.MpiClient")
    def test_local_insuree_makes_no_call(self, client):
        insuree = create_test_insuree(custom_props={"chf_id": "CH-001"})

        queryset = self.resolve(chfId="CH-001", ignoreLocation=True)

        self.assertEqual(queryset.first().id, insuree.id)
        client.assert_not_called()

    @mock.patch("insuree.schema.get_or_create_from_bundle")
    @mock.patch("insuree.schema.MpiClient")
    def test_empty_local_and_one_patient_creates(self, client, get_or_create):
        client.return_value.search_patient.return_value = {
            "resourceType": "Bundle",
            "total": 1,
            "entry": [{"resource": {"resourceType": "Patient"}}],
        }
        get_or_create.return_value = create_test_insuree(
            custom_props={"chf_id": "CH-002"}
        )

        queryset = self.resolve(chfId="CH-002", ignoreLocation=True)

        self.assertEqual(queryset.first().chf_id, "CH-002")
        client.return_value.search_patient.assert_called_once_with("CH-002")

    @mock.patch("insuree.schema.MpiClient")
    def test_empty_local_and_zero_patient_returns_empty(self, client):
        client.return_value.search_patient.return_value = None

        queryset = self.resolve(chfId="CH-404", ignoreLocation=True)

        self.assertFalse(queryset.exists())

    @mock.patch("insuree.schema.MpiClient")
    def test_ambiguous_raises_graphql_error(self, client):
        client.return_value.search_patient.side_effect = MpiAmbiguous("2")

        with self.assertRaises(GraphQLError):
            self.resolve(chfId="CH-003", ignoreLocation=True)

    @mock.patch("insuree.schema.MpiClient")
    def test_unavailable_raises_graphql_error(self, client):
        client.return_value.search_patient.side_effect = MpiUnavailable("timeout")

        with self.assertRaises(GraphQLError):
            self.resolve(chfId="CH-004", ignoreLocation=True)
