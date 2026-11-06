from django.test import SimpleTestCase

from insuree.mpi.exceptions import MpiInvalidPayload
from insuree.mpi.mapper import to_insuree_dto


def patient(**overrides):
    data = {
        "resourceType": "Patient",
        "name": [{"use": "official", "family": "RAISSA", "given": ["EBA'A", "EVEU-ZOA"]}],
        "birthDate": "1992-05-01",
        "gender": "female",
        "telecom": [{"system": "phone", "value": "698062757"}],
        "address": [{"text": "Rue du Lac"}],
        "maritalStatus": {"coding": [{"code": "M"}]},
    }
    data.update(overrides)
    return data


class MpiMapperTestCase(SimpleTestCase):
    def test_maps_required_fields(self):
        dto = to_insuree_dto(patient())

        self.assertEqual(dto["last_name"], "RAISSA")
        self.assertEqual(dto["other_names"], "EBA'A EVEU-ZOA")
        self.assertEqual(dto["dob"], "1992-05-01")
        self.assertEqual(dto["gender_id"], "F")
        self.assertEqual(dto["phone"], "698062757")
        self.assertEqual(dto["current_address"], "Rue du Lac")
        self.assertEqual(dto["marital"], "M")
        self.assertFalse(dto["card_issued"])
        self.assertTrue(dto["head"])
        self.assertEqual(dto["status"], "AC")

    def test_missing_required_fields_raise(self):
        for field in ("name", "birthDate", "gender"):
            bad = patient()
            bad.pop(field)
            with self.assertRaises(MpiInvalidPayload):
                to_insuree_dto(bad)

    def test_missing_family_name_raises(self):
        with self.assertRaises(MpiInvalidPayload):
            to_insuree_dto(patient(name=[{"given": ["X"]}]))

    def test_missing_given_name_raises(self):
        with self.assertRaises(MpiInvalidPayload):
            to_insuree_dto(patient(name=[{"family": "X"}]))

    def test_unknown_gender_maps_to_other(self):
        self.assertEqual(to_insuree_dto(patient(gender="unknown"))["gender_id"], "O")

    def test_deceased_date_is_mapped(self):
        dto = to_insuree_dto(patient(deceasedDateTime="2020-01-02T00:00:00Z"))
        self.assertTrue(dto["dead"])
        self.assertEqual(dto["dod"], "2020-01-02")
