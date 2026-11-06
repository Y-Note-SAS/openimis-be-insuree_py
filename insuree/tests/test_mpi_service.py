import threading
from unittest import mock

from django.db import connection
from django.test import TestCase, TransactionTestCase

from insuree.apps import InsureeConfig
from insuree.models import Insuree
from insuree.mpi.exceptions import MpiAmbiguous, MpiInvalidPayload
from insuree.mpi.service import get_or_create_from_bundle
from location.test_helpers import create_test_location


def patient():
    return {
        "resourceType": "Patient",
        "name": [{"use": "official", "family": "RAISSA", "given": ["EBA'A"]}],
        "birthDate": "1992-05-01",
        "gender": "female",
        "telecom": [{"system": "phone", "value": "698062757"}],
        "address": [{"text": "Rue du Lac"}],
    }


def bundle(entries=1, **patient_overrides):
    patient_data = patient()
    patient_data.update(patient_overrides)
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": entries,
        "entry": [{"resource": patient_data} for _ in range(entries)],
    }


class MpiServiceTestCase(TestCase):
    chf_id = "120902348063480"

    @classmethod
    def setUpTestData(cls):
        cls.location = create_test_location(
            "V", custom_props={"code": InsureeConfig.mpi_default_location_code}
        )

    def setUp(self):
        self.patchers = [
            mock.patch.object(InsureeConfig, "get_insuree_number_length", return_value=None),
            mock.patch.object(InsureeConfig, "get_insuree_number_validator", return_value=None),
            mock.patch.object(InsureeConfig, "get_insuree_number_modulo_root", return_value=None),
        ]
        for patcher in self.patchers:
            patcher.start()
        self.addCleanup(lambda: [p.stop() for p in self.patchers])

    def test_creates_insuree_and_family(self):
        insuree = get_or_create_from_bundle(bundle(), self.chf_id)

        self.assertEqual(insuree.chf_id, self.chf_id)
        self.assertTrue(insuree.head)
        self.assertEqual(insuree.family.location_id, self.location.id)
        self.assertEqual(insuree.family.head_insuree_id, insuree.id)
        self.assertEqual(
            insuree.family.members.filter(validity_to__isnull=True).count(), 1
        )

    def test_is_idempotent(self):
        first = get_or_create_from_bundle(bundle(), self.chf_id)
        second = get_or_create_from_bundle(bundle(), self.chf_id)

        self.assertEqual(first.id, second.id)
        self.assertEqual(
            Insuree.objects.filter(chf_id=self.chf_id, validity_to__isnull=True).count(),
            1,
        )

    def test_empty_bundle_returns_none(self):
        self.assertIsNone(
            get_or_create_from_bundle(
                {"resourceType": "Bundle", "total": 0, "entry": []}, self.chf_id
            )
        )

    def test_more_than_one_patient_raises(self):
        with self.assertRaises(MpiAmbiguous):
            get_or_create_from_bundle(bundle(entries=2), self.chf_id)

    def test_invalid_patient_creates_nothing(self):
        with self.assertRaises(MpiInvalidPayload):
            get_or_create_from_bundle(bundle(gender=None), self.chf_id)

        self.assertFalse(Insuree.objects.filter(chf_id=self.chf_id).exists())

    def test_rollback_on_creation_error(self):
        with mock.patch(
            "insuree.mpi.service.InsureeService.create_or_update",
            side_effect=RuntimeError("boom"),
        ):
            with self.assertRaises(RuntimeError):
                get_or_create_from_bundle(bundle(), self.chf_id)

        self.assertFalse(Insuree.objects.filter(chf_id=self.chf_id).exists())


class MpiConcurrencyTestCase(TransactionTestCase):
    chf_id = "120902348063481"

    def setUp(self):
        self.location = create_test_location(
            "V", custom_props={"code": InsureeConfig.mpi_default_location_code}
        )
        self.patchers = [
            mock.patch.object(InsureeConfig, "get_insuree_number_length", return_value=None),
            mock.patch.object(InsureeConfig, "get_insuree_number_validator", return_value=None),
            mock.patch.object(InsureeConfig, "get_insuree_number_modulo_root", return_value=None),
        ]
        for patcher in self.patchers:
            patcher.start()
        self.addCleanup(lambda: [p.stop() for p in self.patchers])

    def test_two_concurrent_creations_create_one_insuree(self):
        results, errors = [], []

        def worker():
            try:
                insuree = get_or_create_from_bundle(bundle(), self.chf_id)
                results.append(insuree.id)
            except Exception as exc:  # pragma: no cover - diagnostic
                errors.append(exc)
            finally:
                connection.close()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [])
        self.assertEqual(len(set(results)), 1)
        self.assertEqual(
            Insuree.objects.filter(chf_id=self.chf_id, validity_to__isnull=True).count(),
            1,
        )
