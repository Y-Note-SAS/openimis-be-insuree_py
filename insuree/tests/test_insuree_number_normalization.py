from unittest import mock

from django.core.exceptions import ValidationError
from django.test import TestCase

from core.test_helpers import create_test_interactive_user
from insuree.services import InsureeService, validate_insuree_number
from insuree.utils import normalize_insuree_number


class NormalizeInsureeNumberTest(TestCase):
    def test_trims_surrounding_spaces(self):
        self.assertEqual(normalize_insuree_number(" 120902348063480 "), "120902348063480")

    def test_trims_invisible_characters(self):
        value = "\u00a0\u200b120902348063480\u200b\u00a0"
        self.assertEqual(normalize_insuree_number(value), "120902348063480")

    def test_keeps_internal_space(self):
        self.assertEqual(
            normalize_insuree_number("CE/38/01/23/001 AKO/ELI "),
            "CE/38/01/23/001 AKO/ELI",
        )

    def test_rejects_internal_invisible_character(self):
        with self.assertRaises(ValidationError):
            normalize_insuree_number("1209\u200b02348063480")

    def test_none_is_unchanged(self):
        self.assertIsNone(normalize_insuree_number(None))


class InsureeServiceNumberNormalizationTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = create_test_interactive_user()
        cls.service = InsureeService(cls.user)

    @mock.patch.object(InsureeService, "_create_or_update")
    @mock.patch("insuree.services.InsureeConfig.is_insuree_photo_required", False)
    def test_create_or_update_trims_chf_id(self, mock_create_or_update):
        mock_create_or_update.side_effect = lambda insuree, photo: insuree
        data = {
            "chf_id": "120902348063480 ",
            "last_name": "TEST",
            "other_names": "TEST",
            "gender_id": "M",
            "dob": "1990-01-01",
        }

        self.service.create_or_update(data, create_family=False)

        insuree = mock_create_or_update.call_args[0][0]
        self.assertEqual(insuree.chf_id, "120902348063480")

    @mock.patch("insuree.services.InsureeConfig.get_insuree_number_modulo_root", return_value=None)
    @mock.patch("insuree.services.InsureeConfig.get_insuree_number_length", return_value=None)
    @mock.patch("insuree.services.InsureeConfig.get_insuree_number_validator", return_value=None)
    def test_validate_insuree_number_normalizes_input(self, *_):
        self.assertEqual(validate_insuree_number(" 120902348063480 "), [])
        self.assertEqual(len(validate_insuree_number("1209\t02348063480")), 1)
