"""Flags are used for the status registers returned by the device."""

from enum import KEEP, Flag


class SerialPollFlags(Flag, boundary=KEEP):
    """
    The register returned by a serial poll. Undefined bits are kept instead of raising a ValueError, because the
    instrument or the GPIB adapter may set them.
    """

    NONE = 0b0
    DOING_STATE_CHANGE = 1 << 2
    MSG_RDY = 1 << 3
    OUTPUT_SETTLED = 1 << 4
    ERROR_CONDITION = 1 << 5
    SRQ = 1 << 6


class SrqMask(Flag, boundary=KEEP):
    """The register to control the service request interrupts."""

    NONE = 0b0
    DOING_STATE_CHANGE = 1 << 2
    MSG_RDY = 1 << 3
    OUTPUT_SETTLED = 1 << 4
    ERROR_CONDITION = 1 << 5


class StatusFlags(Flag, boundary=KEEP):
    """The internal status register that holds the device configuration."""

    VOLTAGE_MODE = 1 << 0
    CURRENT_BOOST_MODE = 1 << 1
    VOLTAGE_BOOST_MODE = 1 << 2
    DIVIDER_ENABLED = 1 << 3
    INTERNAL_SENSE_ENABLED = 1 << 4
    OUTPUT_ENABLED = 1 << 5
    INTERNAL_GUARD_ENABLED = 1 << 6
    REAR_OUTPUT_ENABLED = 1 << 7
