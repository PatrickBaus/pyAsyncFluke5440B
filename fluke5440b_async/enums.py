"""Enums are used to represent the device functions and settings."""
from __future__ import annotations

from enum import Enum


class ErrorCode(Enum):
    """The error codes used by the Fluke 5440B."""

    NONE = 0
    BOOST_INTERFACE_CONNECTION_ERROR = 144
    BOOST_INTERFACE_MISSING = 145
    BOOST_INTERFACE_VOLTAGE_TRIP = 146
    BOOST_INTERFACE_CURRENT_TRIP = 147
    GPIB_HANDSHAKE_ERROR = 152
    TERMINATOR_ERROR = 153
    SEPARATOR_ERROR = 154
    UNKNOWN_COMMAND = 155
    INVALID_PARAMETER = 156
    BUFFER_OVERFLOW = 157
    INVALID_CHARACTER = 158
    RS232_ERROR = 160
    PARAMETER_OUT_OF_RANGE = 168
    OUTPUT_OUTSIDE_LIMITS = 169
    LIMIT_OUT_OF_RANGE = 170
    DIVIDER_OUT_OF_RANGE = 171
    INVALID_SENSE_MODE = 172
    INVALID_GUARD_MODE = 173
    INVALID_COMMAND = 175


class ModeType(Enum):
    """The output modes. Voltage boost means a connected Fluke 5205A power amplifier and current boost means a connected
    Fluke 5220A transconductance amplifier."""

    NORMAL = "BSTO"
    VOLTAGE_BOOST = "BSTV"
    CURRENT_BOOST = "BSTC"


class SeparatorType(Enum):
    """The separator used to distinguish multiple return values."""

    COMMA = 0
    COLON = 1


class DeviceState(Enum):
    """The internal device state."""

    IDLE = 0
    CALIBRATING_ADC = 16
    ZEROING_10V_POS = 32
    ZEROING_10V_NEG = 33
    ZEROING_20V_POS = 34
    ZEROING_20V_NEG = 35
    ZEROING_250V_POS = 36
    ZEROING_250V_NEG = 37
    ZEROING_1000V_POS = 38
    ZEROING_1000V_NEG = 39
    CALIBRATING_GAIN_10V_POS = 48
    CALIBRATING_GAIN_20V_POS = 49
    CALIBRATING_GAIN_HV_POS = 50
    CALIBRATING_GAIN_HV_NEG = 51
    CALIBRATING_GAIN_20V_NEG = 52
    CALIBRATING_GAIN_10V_NEG = 53
    EXT_CAL_10V = 64
    EXT_CAL_20V = 65
    EXT_CAL_250V = 66
    EXT_CAL_1000V = 67
    EXT_CAL_2V = 68
    EXT_CAL_02V = 69
    EXT_CAL_10V_NULL = 80
    EXT_CAL_20V_NULL = 81
    EXT_CAL_250V_NULL = 82
    EXT_CAL_1000V_NULL = 83
    EXT_CAL_2V_NULL = 84
    EXT_CAL_02V_NULL = 85
    CAL_N1_N2_RATIO = 96
    SELF_TEST_MAIN_CPU = 112
    SELF_TEST_FRONTPANEL_CPU = 113
    SELF_TEST_GUARD_CPU = 114
    SELF_TEST_LOW_VOLTAGE = 128
    SELF_TEST_HIGH_VOLTAGE = 129
    SELF_TEST_OVEN = 130
    PRINTING = 208
    WRITING_TO_NVRAM = 224
    RESETTING = 240


class TerminatorType(Enum):
    """The line terminator used by the instrument."""

    EOI = 0
    CR_LF_EOI = 1
    LF_EOI = 2
    CR_LF = 3
    LF = 4
