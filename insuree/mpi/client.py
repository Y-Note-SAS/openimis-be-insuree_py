import hashlib
import logging
import uuid

import requests
import urllib3
from requests.auth import HTTPBasicAuth

from insuree.apps import InsureeConfig

from .exceptions import MpiAmbiguous, MpiInvalidPayload, MpiUnavailable, MpiError

logger = logging.getLogger(__name__)

DEFAULT_PATIENT_PATH = "/api/fhir/Patient"


class MpiClient:
    """Read-only client to search a patient in the CHC MPI through openHIM."""

    def __init__(
        self,
        base_url=None,
        user=None,
        password=None,
        timeout_connect=None,
        timeout_read=None,
        total_timeout=None,
        patient_path=None,
    ):
        base_url = base_url if base_url is not None else InsureeConfig.mpi_base_url
        self.base_url = (base_url or "").rstrip("/")
        self.user = user if user is not None else InsureeConfig.mpi_auth_user
        self.password = password if password is not None else InsureeConfig.mpi_auth_password
        self.timeout_connect = timeout_connect or InsureeConfig.mpi_timeout_connect
        self.timeout_read = timeout_read or InsureeConfig.mpi_timeout_read
        self.total_timeout = total_timeout or InsureeConfig.mpi_total_timeout
        path = patient_path or InsureeConfig.mpi_patient_path or DEFAULT_PATIENT_PATH
        self.patient_path = path if path.startswith("/") else f"/{path}"

    def search_patient(self, identifier):
        """Return the FHIR Bundle of the single matching patient, or None.

        Raises MpiUnavailable on network/technical failures, MpiAmbiguous when
        more than one patient matches, and MpiInvalidPayload when the response
        cannot be used.
        """
        identifier = (identifier or "").strip()
        if not identifier:
            raise ValueError("identifier is required")
        if not self.base_url:
            raise MpiError("mpi_base_url is not configured")

        correlation_id = uuid.uuid4().hex[:12]
        identifier_digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()[:8]
        auth = HTTPBasicAuth(self.user, self.password) if self.user else None
        timeout = urllib3.Timeout(
            connect=self.timeout_connect,
            read=self.timeout_read,
            total=self.total_timeout,
        )

        try:
            response = requests.get(
                f"{self.base_url}{self.patient_path}",
                params={"identifier": identifier},
                auth=auth,
                timeout=timeout,
                headers={"Accept": "application/fhir+json"},
            )
        except requests.exceptions.Timeout as exc:
            logger.warning("mpi lookup timeout corr=%s id=%s", correlation_id, identifier_digest)
            raise MpiUnavailable("timeout") from exc
        except requests.exceptions.RequestException as exc:
            logger.warning("mpi lookup request error corr=%s id=%s", correlation_id, identifier_digest)
            raise MpiUnavailable("request error") from exc

        if response.status_code == 404:
            raise MpiUnavailable("404")
        if response.status_code >= 500:
            raise MpiUnavailable("server error %s" % response.status_code)
        if response.status_code != 200:
            raise MpiInvalidPayload("unexpected status %s" % response.status_code)

        try:
            payload = response.json()
        except ValueError as exc:
            raise MpiInvalidPayload("invalid json") from exc

        if not isinstance(payload, dict) or payload.get("resourceType") != "Bundle":
            raise MpiInvalidPayload("not a Bundle")

        entries = payload.get("entry") or []
        total = payload.get("total")
        if total is None:
            total = len(entries)
        if total == 0 or not entries:
            return None
        if total > 1 or len(entries) > 1:
            raise MpiAmbiguous("%s patients" % max(total, len(entries)))
        return payload
