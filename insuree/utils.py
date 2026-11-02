from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


# Characters trimmed from both ends of an insuree number (whitespace and
# invisible characters commonly introduced by copy/paste or legacy imports).
INSUREE_NUMBER_EDGE_CHARS = (
    " \t\n\r\f\v"
    "\u00a0"  # no-break space
    "\u2007"  # figure space
    "\u202f"  # narrow no-break space
    "\u200b"  # zero-width space
    "\u200c"  # zero-width non-joiner
    "\u200d"  # zero-width joiner
    "\u2060"  # word joiner
    "\ufeff"  # byte order mark / zero-width no-break space
)

# Invisible/control characters that must not remain inside an insuree number.
# A regular space is allowed because some legacy numbers contain one.
INSUREE_NUMBER_FORBIDDEN_CHARS = frozenset(
    "\t\n\r\f\v\u00a0\u2007\u202f\u200b\u200c\u200d\u2060\ufeff"
)


def normalize_insuree_number(value):
    """Normalize an insuree number before it is stored or looked up.

    Surrounding whitespace/invisible characters are removed. Invisible or
    control characters left inside the value are rejected, so that two
    visually identical insuree numbers cannot be stored differently.

    :param value: raw insuree number (may be None)
    :return: normalized insuree number (or None)
    :raises ValidationError: if an invisible character remains inside
    """
    if value is None:
        return None
    normalized = str(value).strip(INSUREE_NUMBER_EDGE_CHARS)
    if any(char in INSUREE_NUMBER_FORBIDDEN_CHARS for char in normalized):
        raise ValidationError(_("Insuree number cannot contain invisible characters."))
    return normalized


def generate_error_return(instance_name_str, checksum_return=False):
    from insuree.apps import InsureeConfig
    if checksum_return:
        return [{"errorCode": InsureeConfig.validation_code_invalid_insuree_number_checksum,
                 "message": _(f"{instance_name_str}_national_id_checksum_not_valid")}]
    else:
        return [{"errorCode": InsureeConfig.validation_code_invalid_insuree_number_exception,
                 "message": _(f"{instance_name_str}_national_id_not_valid")}]


ZERO_CHAR = '0'
NINE_CHAR = '9'


class IdentifierValidator:
    """
    A class for validating Moldovan national identification numbers (IDs).
    Can be specified as an insuree number validator in apps.py config with the key: "insuree_number_validator"
    Example: "insuree_number_validator": IdentifierValidator().is_valid_resident_identifier
    """

    @staticmethod
    def is_valid(idn):
        if idn is None or len(idn) != 13 or not idn.strip():
            return False
        crc = 0
        for i in range(12):
            if not (ZERO_CHAR <= idn[i] <= NINE_CHAR):
                return False
            crc += (ord(idn[i]) - ord(ZERO_CHAR)) * (7 if i % 3 == 0 else (3 if i % 3 == 1 else 1))
        if not (ZERO_CHAR <= idn[12] <= NINE_CHAR):
            return False
        return crc % 10 == (ord(idn[12]) - ord(ZERO_CHAR))

    @staticmethod
    def is_valid_resident_identifier(idnp):
        if not IdentifierValidator.is_valid(idnp):
            return generate_error_return("resident")
        if not (idnp[0] == '2' or idnp.startswith('09')):
            return generate_error_return("resident", checksum_return=True)

    @staticmethod
    def is_valid_organization_identifier(idno):
        if not IdentifierValidator.is_valid(idno):
            return generate_error_return("organization")
        if not idno[0] == '1':
            return generate_error_return("organization", checksum_return=True)

    @staticmethod
    def is_valid_vehicle_identifier(idnv):
        if not IdentifierValidator.is_valid(idnv):
            return generate_error_return("vehicle")
        if not idnv[0] == '3':
            return generate_error_return("vehicle", checksum_return=True)
