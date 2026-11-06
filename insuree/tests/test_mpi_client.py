from unittest import mock

import requests
from django.test import SimpleTestCase

from insuree.apps import InsureeConfig
from insuree.mpi.client import MpiClient
from insuree.mpi.exceptions import MpiAmbiguous, MpiError, MpiInvalidPayload, MpiUnavailable


def bundle(entries=1):
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": entries,
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "patient-%d" % i}}
            for i in range(entries)
        ],
    }


def response(status=200, payload=None, json_error=False):
    resp = mock.Mock()
    resp.status_code = status
    if json_error:
        resp.json.side_effect = ValueError("no json")
    else:
        resp.json.return_value = payload
    return resp


class MpiClientTestCase(SimpleTestCase):
    def setUp(self):
        self.client = MpiClient(
            base_url="https://openhim.example/",
            user="mpi-user",
            password="secret",
            timeout_connect=3,
            timeout_read=7,
            total_timeout=10,
        )

    @mock.patch("insuree.mpi.client.requests.get")
    def test_returns_bundle_for_one_patient(self, get):
        get.return_value = response(payload=bundle(1))

        result = self.client.search_patient(" CH-001 ")

        self.assertEqual(result["entry"][0]["resource"]["id"], "patient-0")
        args, kwargs = get.call_args
        self.assertEqual(args[0], "https://openhim.example/api/fhir/Patient")
        self.assertEqual(kwargs["params"], {"identifier": "CH-001"})
        self.assertEqual(kwargs["auth"].username, "mpi-user")
        self.assertEqual(kwargs["timeout"].connect_timeout, 3)
        self.assertEqual(kwargs["timeout"].read_timeout, 7)
        self.assertEqual(kwargs["timeout"].total, 10)

    @mock.patch("insuree.mpi.client.requests.get")
    def test_returns_none_for_empty_bundle(self, get):
        get.return_value = response(payload=bundle(0))

        self.assertIsNone(self.client.search_patient("CH-001"))

    @mock.patch("insuree.mpi.client.requests.get")
    def test_404_raises_unavailable(self, get):
        get.return_value = response(status=404)

        with self.assertRaises(MpiUnavailable):
            self.client.search_patient("CH-001")

    @mock.patch("insuree.mpi.client.requests.get")
    def test_500_raises_unavailable(self, get):
        get.return_value = response(status=500)

        with self.assertRaises(MpiUnavailable):
            self.client.search_patient("CH-001")

    @mock.patch("insuree.mpi.client.requests.get")
    def test_timeout_raises_unavailable(self, get):
        get.side_effect = requests.exceptions.ReadTimeout("slow")

        with self.assertRaises(MpiUnavailable):
            self.client.search_patient("CH-001")

    @mock.patch("insuree.mpi.client.requests.get")
    def test_invalid_json_raises_invalid_payload(self, get):
        get.return_value = response(json_error=True)

        with self.assertRaises(MpiInvalidPayload):
            self.client.search_patient("CH-001")

    @mock.patch("insuree.mpi.client.requests.get")
    def test_non_bundle_raises_invalid_payload(self, get):
        get.return_value = response(payload={"resourceType": "Patient"})

        with self.assertRaises(MpiInvalidPayload):
            self.client.search_patient("CH-001")

    @mock.patch("insuree.mpi.client.requests.get")
    def test_more_than_one_patient_raises_ambiguous(self, get):
        get.return_value = response(payload=bundle(2))

        with self.assertRaises(MpiAmbiguous):
            self.client.search_patient("CH-001")

    def test_missing_base_url_raises(self):
        client = MpiClient(base_url="")

        with self.assertRaises(MpiError):
            client.search_patient("CH-001")

    def test_empty_identifier_raises(self):
        with self.assertRaises(ValueError):
            self.client.search_patient("   ")

    @mock.patch("insuree.mpi.client.requests.get")
    def test_uses_patient_path_from_backend_config(self, get):
        get.return_value = response(payload=bundle(1))
        with mock.patch.object(InsureeConfig, "mpi_patient_path", "/from/config/Patient"):
            client = MpiClient(base_url="https://openhim.example", user="mpi-user", password="secret")
            client.search_patient("CH-001")
        self.assertEqual(get.call_args[0][0], "https://openhim.example/from/config/Patient")

    @mock.patch("insuree.mpi.client.requests.get")
    def test_patient_path_argument_overrides_backend_config(self, get):
        get.return_value = response(payload=bundle(1))
        client = MpiClient(base_url="https://openhim.example", patient_path="custom/Patient")
        client.search_patient("CH-001")
        self.assertEqual(get.call_args[0][0], "https://openhim.example/custom/Patient")
