"""Mapping of a FHIR Patient to openIMIS Insuree fields."""

from .exceptions import MpiInvalidPayload

GENDER_MAP = {
    "male": "M",
    "female": "F",
    "other": "O",
    "unknown": "O",
}

MARITAL_MAP = {
    "M": "M",
    "S": "S",
    "D": "D",
    "W": "W",
    "U": "N",
}


def _official_name(patient):
    names = patient.get("name") or []
    for name in names:
        if name.get("use") in ("official", "usual"):
            return name
    return names[0] if names else {}


def _phone(patient):
    for telecom in patient.get("telecom") or []:
        if telecom.get("system") == "phone" and telecom.get("value"):
            return telecom["value"][:50]
    return None


def _address(patient):
    for address in patient.get("address") or []:
        value = address.get("text") or " ".join(address.get("line") or [])
        if value:
            return value[:200]
    return None


def _marital(patient):
    marital = patient.get("maritalStatus") or {}
    for coding in marital.get("coding") or []:
        code = MARITAL_MAP.get((coding.get("code") or "").upper())
        if code:
            return code
    return None


def _deceased(patient):
    if patient.get("deceasedBoolean") is True:
        return True, None
    deceased_date = patient.get("deceasedDateTime")
    if deceased_date:
        return True, deceased_date[:10]
    return False, None


def to_insuree_dto(patient):
    """Build the InsureeService payload from a FHIR Patient.

    Raises MpiInvalidPayload when a required field is missing or invalid.
    """
    if not isinstance(patient, dict) or patient.get("resourceType") != "Patient":
        raise MpiInvalidPayload("not a Patient")

    name = _official_name(patient)
    last_name = (name.get("family") or "").strip()
    given = [value for value in (name.get("given") or []) if value]
    other_names = " ".join(given).strip()
    dob = patient.get("birthDate")
    gender = (patient.get("gender") or "").lower()

    if not last_name or not other_names or not dob or not gender:
        raise MpiInvalidPayload("missing required patient fields")
    if len(last_name) > 100 or len(other_names) > 100:
        raise MpiInvalidPayload("patient name too long")
    gender_code = GENDER_MAP.get(gender)
    if not gender_code:
        raise MpiInvalidPayload("unsupported gender")

    dto = {
        "last_name": last_name,
        "other_names": other_names,
        "dob": dob,
        "gender_id": gender_code,
        "card_issued": False,
        "head": True,
        "status": "AC",
    }

    phone = _phone(patient)
    if phone:
        dto["phone"] = phone
    address = _address(patient)
    if address:
        dto["current_address"] = address
    marital = _marital(patient)
    if marital:
        dto["marital"] = marital
    dead, dod = _deceased(patient)
    if dead:
        dto["dead"] = True
        if dod:
            dto["dod"] = dod

    return dto
