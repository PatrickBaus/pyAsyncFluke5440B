"""Custom errors raised by the Fluke 5440B."""
from .enums import ErrorCode, SelfTestErrorCode


class Fluke5440bError(Exception):
    """The base class for all Fluke 5540B exceptions"""


class DeviceError(Fluke5440bError):
    """The device returned an error during operation."""

    def __init__(self, message: str, error_code: ErrorCode):
        super().__init__(message)

        self.code = error_code


class SelftestError(Fluke5440bError):
    """The device returned an error during self-test. See page 4-8 of the service manual for details."""

    def __init__(self, selftest: str, error_code: SelfTestErrorCode):
        super().__init__(
            f"{selftest} self-test failed with error: {error_code}."
            f" Check the service manual on page 4-8 for a solution."
        )

        self.code = error_code
