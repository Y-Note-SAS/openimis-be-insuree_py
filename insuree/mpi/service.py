"""Creation of Insuree + Family from a FHIR Patient (idempotent)."""

import logging

from django.db import IntegrityError, connection, transaction

from core.models import TechnicalUser
from insuree.models import Insuree
from insuree.services import InsureeService

from .exceptions import MpiAmbiguous, MpiInvalidPayload
from .location import get_default_location
from .mapper import to_insuree_dto

logger = logging.getLogger(__name__)


def _patient_from_bundle(bundle):
    if not isinstance(bundle, dict) or bundle.get("resourceType") != "Bundle":
        raise MpiInvalidPayload("not a Bundle")
    entries = bundle.get("entry") or []
    if len(entries) > 1:
        raise MpiAmbiguous("%s patients" % len(entries))
    if not entries:
        return None
    resource = entries[0].get("resource") or {}
    if resource.get("resourceType") != "Patient":
        raise MpiInvalidPayload("not a Patient")
    return resource


def _lock_identifier(chf_id):
    """Serialize concurrent creations for the same CHFID (PostgreSQL)."""
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))",
                ["mpi:%s" % chf_id],
            )


def get_or_create_from_bundle(bundle, chf_id):
    """Create the insuree and its family from a single-patient Bundle.

    Returns the existing active insuree when the CHFID is already known.
    """
    patient = _patient_from_bundle(bundle)
    if patient is None:
        return None

    chf_id = (chf_id or "").strip()
    if not chf_id:
        raise MpiInvalidPayload("missing chf_id")

    with transaction.atomic():
        _lock_identifier(chf_id)
        existing = Insuree.objects.filter(
            chf_id=chf_id, validity_to__isnull=True
        ).first()
        if existing:
            return existing

        location = get_default_location()
        data = to_insuree_dto(patient)
        data["chf_id"] = chf_id
        data["current_village_id"] = location.id

        try:
            insuree = InsureeService(TechnicalUser()).create_or_update(data)
        except IntegrityError:
            existing = Insuree.objects.filter(
                chf_id=chf_id, validity_to__isnull=True
            ).first()
            if existing:
                return existing
            raise

        logger.info("mpi insuree created id=%s", insuree.id)
        return insuree
