from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from insuree.mpi.exceptions import MpiAmbiguous, MpiUnavailable


def bundle():
    return {
        "resourceType": "Bundle",
        "total": 1,
        "entry": [{"resource": {"resourceType": "Patient", "id": "patient-0"}}],
    }


class MpiCheckCommandTestCase(SimpleTestCase):
    @mock.patch("insuree.management.commands.mpi_check.MpiClient")
    def test_patient_found(self, client_cls):
        client_cls.return_value.search_patient.return_value = bundle()
        out = StringIO()

        call_command("mpi_check", "CH-001", stdout=out)

        self.assertIn("Patient trouvé : id=patient-0", out.getvalue())

    @mock.patch("insuree.management.commands.mpi_check.MpiClient")
    def test_no_patient(self, client_cls):
        client_cls.return_value.search_patient.return_value = None
        out = StringIO()

        call_command("mpi_check", "CH-001", stdout=out)

        self.assertIn("Aucun patient", out.getvalue())

    @mock.patch("insuree.management.commands.mpi_check.MpiClient")
    def test_unavailable(self, client_cls):
        client_cls.return_value.search_patient.side_effect = MpiUnavailable("timeout")

        with self.assertRaises(CommandError):
            call_command("mpi_check", "CH-001", stdout=StringIO())

    @mock.patch("insuree.management.commands.mpi_check.MpiClient")
    def test_ambiguous(self, client_cls):
        client_cls.return_value.search_patient.side_effect = MpiAmbiguous("2 patients")

        with self.assertRaises(CommandError):
            call_command("mpi_check", "CH-001", stdout=StringIO())
