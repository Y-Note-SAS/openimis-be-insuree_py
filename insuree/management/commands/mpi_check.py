from django.core.management.base import BaseCommand, CommandError

from insuree.mpi.client import MpiClient
from insuree.mpi.exceptions import MpiAmbiguous, MpiError


class Command(BaseCommand):
    help = "Interroge le CHC via openHIM pour un CHFID (diagnostic, hors chemin de requête)."

    def add_arguments(self, parser):
        parser.add_argument("chfid", help="CHFID / identifiant MPI à rechercher")

    def handle(self, *args, **options):
        chfid = options["chfid"]
        try:
            bundle = MpiClient().search_patient(chfid)
        except MpiAmbiguous as exc:
            raise CommandError("Plusieurs patients correspondent à ce CHFID (%s)." % exc)
        except MpiError as exc:
            raise CommandError("Recherche CHC indisponible : %s." % exc)

        if bundle is None:
            self.stdout.write("Aucun patient pour ce CHFID.")
            return

        entry = (bundle.get("entry") or [{}])[0]
        resource = entry.get("resource") or {}
        self.stdout.write("Patient trouvé : id=%s (Bundle total=1)." % resource.get("id", "?"))
