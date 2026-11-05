class MpiError(Exception):
    """Base error for the MPI (CHC) connector."""


class MpiUnavailable(MpiError):
    """The CHC could not be reached or returned a technical error."""


class MpiAmbiguous(MpiError):
    """The CHC returned more than one patient for an exact identifier."""


class MpiInvalidPayload(MpiError):
    """The CHC response is not a usable FHIR Bundle."""
