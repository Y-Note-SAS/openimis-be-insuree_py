"""Resolve the fixed MPI location (05BAT06V) to an openIMIS Location."""

from location.models import Location

from insuree.apps import InsureeConfig

from .exceptions import MpiAmbiguous, MpiInvalidPayload


def get_default_location():
    """Return the active Location configured for MPI-created insurees."""
    code = InsureeConfig.mpi_default_location_code
    if not code:
        raise MpiInvalidPayload("mpi_default_location_code is not configured")

    locations = Location.objects.filter(code=code, validity_to__isnull=True)
    count = locations.count()
    if count == 0:
        raise MpiInvalidPayload("location %s not found" % code)
    if count > 1:
        raise MpiAmbiguous("multiple locations with code %s" % code)
    return locations.first()
