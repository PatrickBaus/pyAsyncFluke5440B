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


class SelfTestErrorCode(Enum):
    """The error codes thrown by the self-test routine. See page 4-8 of the service manual for details."""

    NONE = 0
    POWER_SUPPLY_FAULT_TEST_UNGUARDED_POWER = 8
    POWER_SUPPLY_FAULT_CHECK_GUARDED_POWER = 9
    MAIN_CONTROL_FAULT_CHECK_MAIN_CONTROLLER = 16
    MAIN_CONTROL_FAULT_CHECK_MAIN_MEMORY = 17
    MAIN_CONTROL_FAULT_CHECK_MAIN_NV_MEMORY = 18
    MAIN_INTERRUPT_FAULT_CHECK_SERIAL_OUTPUT_TIMER = 24
    MAIN_INTERRUPT_FAULT_CHECK_NVMEMORY_TIMER = 25
    MAIN_INTERRUPT_FAULT_CHECK_SERIAL_INPUT = 26
    MAIN_INTERRUPT_FAULT_CHECK_INPUT_FR_FRONT = 27
    MAIN_INTERRUPT_FAULT_CHECK_MAIN_CLOCK = 28
    MAIN_INTERRUPT_FAULT_CHECK_REMOTE_INPUT = 29
    MAIN_INTERRUPT_FAULT_CHECK_INPUT_FR_GUARD = 30
    FRONT_DIGITAL_FAULT_MEMORY = 32
    FRONT_DIGITAL_FAULT_PROCESSOR = 33
    INSIDE_GUARD_FAULT_CHECK_GUARD_MEMORY = 40
    INSIDE_GUARD_FAULT_CHECK_DATA_BUS = 41
    INSIDE_GUARD_FAULT_CHECK_ADDRESS_BUS = 42
    INSIDE_GUARD_FAULT_CHECK_GUARD_CONTROL_BUS = 43
    BOARD_ACK_FAULT_CHECK_DAC_BOARD = 48
    BOARD_ACK_FAULT_CHECK_PREAMP_BOARD = 49
    BOARD_ACK_FAULT_CHECK_SAMPLE_BOARD = 50
    BOARD_ACK_FAULT_CHECK_OUTPUT_BOARD = 51
    GUARD_COMMUNICATION_FAULT_CHECK_GARBLED_DATA = 56
    GUARD_COMMUNICATION_FAULT_GUARD_NOT_ANSWERING = 57
    FRONT_COMMUNICATION_FAULT = 64
    ANALOG_MEASURE_FAULT_CHECK_ANALOG_BUSS = 72
    ANALOG_MEASURE_FAULT_CHECK_ZERO_AMP = 73
    ANALOG_MEASURE_FAULT_UNABLE_TO_ZERO_RANGE = 74
    ANALOG_MEASURE_FAULT_GAIN_SHIFT_TOO_LARGE = 75
    DAC_DIGITAL_FAULT_CHECK_A_TO_D = 80
    DAC_DIGITAL_FAULT_CHECK_FIRST_SWITCH = 81
    DAC_DIGITAL_FAULT_SECOND_SWITCH = 82
    DAC_DIGITAL_FAULT_BIAS_SIGNAL = 83
    DAC_ANALOG_FAULT_CHECK_0V_OUTPUT = 87
    DAC_ANALOG_FAULT_CHECK_REFERENCE = 88
    DAC_ANALOG_FAULT_CHECK_NEG_5V_REGULATOR = 89
    DAC_ANALOG_FAULT_CHECK_10V_OUTPUT = 90
    DAC_ANALOG_FAULT_CHECK_NEG_10V_OUTPUT = 91
    DAC_ANALOG_FAULT_CHECK_DAC_FILTER = 92
    DAC_ANALOG_FAULT_CHECK_5V_DAC_CKT = 93
    DAC_ANALOG_FAULT_CHECK_SECOND_SPEED = 94
    DAC_ANALOG_FAULT_CHECK_DAC_OVEN = 95
    DAC_ANALOG_FAULT_CHECK_5V_DAC_REC = 96
    GRD_PWR_SUPPLY_FAULT_CHECK_20V_OVEN = 97
    PREAMP_ANALOG_FAULT_CHECK_INTCAL_CONFIG = 104
    PREAMP_OUT_BRDS_FAULT_CHECK_STANDBY_CONFIG = 109
    PREAMP_ANALOG_FAULT_CHECK_PREAMP_OVEN = 110
    OUTPUT_BOARDS_FAULT_CHECK_ZERO_AMP = 112
    OUTPUT_BOARDS_FAULT_CHECK_2V_RANGE = 113
    OUTPUT_BOARDS_FAULT_CHECK_CURR_LIM_CKT = 114
    OUTPUT_BOARDS_FAULT_CHECK_02V_RANGE = 115
    PREAMP_OUT_BRDS_FAULT_CHECK_250V_RANGE = 116
    SAMPLE_STRING_FAULT_CHECK_10V_INTCAL = 120
    SAMPLE_STRING_FAULT_CHECK_20V_INTCAL = 121
    SAMPLE_STRING_FAULT_CHECK_1KV_RANGE = 122
    PREAMP_SAMPLE_STRING_FAULT_CHECK_HIGH_V_INTCAL = 123
    FIL_BOUT_BRDS_FAULT_CHECK_NEG_275V_RANGE = 128
    FIL_BOUT_BRDS_FAULT_CHECK_275V_RANGE = 129
    FIL_BOUT_BRDS_FAULT_CHECK_550V_RANGE = 130
    FIL_BOUT_BRDS_FAULT_CHECK_875V_RANGE = 131
    FIL_BOUT_BRDS_FAULT_CHECK_1100V_RANGE = 132
    OUTPUT_LIMIT_FAULT = 136
    OUTPUT_LIMIT_FAULT_OUTPUT_OVER_VOLTAGE = 137
    OUTPUT_LIMIT_FAULT_OUTPUT_UNDER_VOLTAGE = 138
    BOOST_INTERFACE_ERROR_CHECK_REAR_CONNECTOR = 144
    BOOST_INTERFACE_ERROR_CHECK_MISSING_REAR_CABLE = 145
    BOOST_INTERFACE_ERROR_VOLTAGE_TRIP = 146
    BOOST_INTERFACE_ERROR_CURRENT_TRIP = 147
    IEEE488_REMOTE_ERROR_SOURCE_HANDSHAKE = 152
    IEEE488_REMOTE_ERROR_EXPECTING_TERMINATOR = 153
    IEEE488_REMOTE_ERROR_EXPECTING_SEPARATOR = 154
    IEEE488_REMOTE_ERROR_EXPECTING_HEADER = 155
    IEEE488_REMOTE_ERROR_EXPECTING_NUMBER = 156
    IEEE488_REMOTE_ERROR_EXPECTING_BUFFER_OVERFLOW = 157
    IEEE488_REMOTE_ERROR_EXPECTING_BAD_CHARACTER = 158
    RS232C_SERIAL_ERROR = 160
    USER_ENTRY_ERROR_NUMBER_OUT_OF_RANGE = 168
    USER_ENTRY_ERROR_OUTPUT_OUT_OF_RANGE = 169
    USER_ENTRY_ERROR_LIMITS_OUT_OF_RANGE = 170
    USER_ENTRY_ERROR_DIVIDER_OUT_OF_RANGE = 171
    USER_ENTRY_ERROR_IN_OUTPUT_TERMINAL_SENSE = 172
    USER_ENTRY_ERROR_IN_OUTPUT_TERMINAL_GUARD = 173
    CAL_SWITCH_LOCKED = 174
    USER_ENTRY_ERROR_INSTRUMENT_IS_BUSY = 175


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