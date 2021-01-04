#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ##### BEGIN GPL LICENSE BLOCK #####
#
# Copyright (C) 2021 Patrick Baus
# This file is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This file is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this file.  If not, see <http://www.gnu.org/licenses/>.
#
# ##### END GPL LICENSE BLOCK #####

import asyncio
from decimal import Decimal
from enum import Enum, Flag
import logging

class InvalidStateError(ValueError):
    @property
    def value(self):
        return self.args[1]

    def __init__(self, message, value):
        self.args = [message, value]

class SeparatorType(Enum):
    COMMA = 0
    COLON = 1

class TerminatorType(Enum):
    EOI       = 0
    CR_LF_EOI = 1
    LF_EOI    = 2
    CR_LF     = 3
    LF        = 4

class ModeType(Enum):
    NORMAL = "BSTO"
    VOLTAGE_BOOST = "BSTV"
    CURRENT_BOOST = "BSTC"

class ErrorCode(Enum):
    NONE                              = 0
    BOOST_INTERFACE_CONNECTION_ERROR  = 144
    BOOST_INTERFACE_MISSING           = 145
    BOOST_INTERFACE_VOLTAGE_TRIP      = 146
    BOOST_INTERFACE_CURRENT_TRIP      = 147
    GPIB_HANDSHAKE_ERROR              = 152
    TERMINATOR_ERROR                  = 153
    SEPARATOR_ERROR                   = 154
    UNKNOWN_COMMAND                   = 155
    INVALID_PARAMTER                  = 156
    BUFFER_OVERFLOW                   = 157
    INVALID_CHARACTER                 = 158
    RS232_ERROR                       = 160
    PARAMTER_OUT_OF_RANGE             = 168
    OUTPUT_OUTSIDE_LIMITS             = 169
    LIMIT_OUT_OF_RANGE                = 170
    DIVIDER_OUT_OF_RANGE              = 171
    INVALID_SENSE_MODE                = 172
    INVALID_GUARD_MODE                = 173
    INVALID_COMMAND                   = 175

class State(Enum):
    IDLE                     = 0
    CALIBRATING_ADC          = 16
    ZEROING_10V_pos          = 32
    ZEROING_10V_neg          = 33
    ZEROING_20V_pos          = 34
    ZEROING_20V_neg          = 35
    ZEROING_250V_pos         = 36
    ZEROING_250V_neg         = 37
    ZEROING_1000V_pos        = 38
    ZEROING_1000V_neg        = 39
    CALIBRATING_GAIN_10V_pos = 48
    CALIBRATING_GAIN_20V_pos = 49
    CALIBRATING_GAIN_HV_pos  = 50
    CALIBRATING_GAIN_HV_neg  = 51
    CALIBRATING_GAIN_20V_neg = 52
    CALIBRATING_GAIN_10V_neg = 53
    EXT_CAL_10V              = 64
    EXT_CAL_20V              = 65
    EXT_CAL_250V             = 66
    EXT_CAL_1000V            = 67
    EXT_CAL_2V               = 68
    EXT_CAL_02V              = 69
    EXT_CAL_10V_NULL         = 80
    EXT_CAL_20V_NULL         = 81
    EXT_CAL_250V_NULL        = 82
    EXT_CAL_1000V_NULL       = 83
    EXT_CAL_2V_NULL          = 84
    EXT_CAL_02V_NULL         = 85
    CAL_N1_N2_RATIO          = 96
    SELF_TEST_MAIN_CPU       = 112
    SELF_TEST_FRONTPANEL_CPU = 113
    SELF_TEST_GUARD_CPU      = 114
    SELF_TEST_LOW_VOLTAGE    = 128
    SELF_TEST_HIGH_VOLTAGE   = 129
    SELF_TEST_OVEN           = 130
    PRINTING                 = 208
    WRITING_TO_NVRAM         = 224
    RESETTING                = 240

class SrqMask(Flag):
    NONE                = 0b0
    DOING_STATE_CHANGE  = 1 << 2
    MSG_RDY             = 1 << 3
    OUTPUT_SETTLED      = 1 << 4
    ERROR_CONDITION     = 1 << 5

class SerialPollFlags(Flag):
    NONE               = 0b0
    DOING_STATE_CHANGE = 1 << 2
    MSG_RDY            = 1 << 3
    OUTPUT_SETTLED     = 1 << 4
    ERROR_CONDITION    = 1 << 5
    SRQ                = 1 << 6

class StatusFlags(Flag):
    VOLTAGE_MODE           = 1 << 0
    CURRENT_BOOST_MODE     = 1 << 1
    VOLTAGE_BOOST_MODE     = 1 << 2
    DIVIDER_ENABLED        = 1 << 3
    INTERNAL_SENSE_ENABLED = 1 << 4
    OUTPUT_ENABLED         = 1 << 5
    INTERNAL_GUARD_ENABLED = 1 << 6
    REAR_OUTPUT_ENABLED    = 1 << 7

BAUD_RATES_AVAILABLE = (50, 75, 110, 134.5, 150, 200, 300, 600, 1200, 1800, 2400, 4800, 9600)

class Fluke_5440B:
    @property
    def connection(self):
        return self.__conn

    def __init__(self, connection):
        self.__conn = connection
        self.__lock = None

        self.__logger = logging.getLogger(__name__)

    async def get_id(self):
        version = (await self._get_software_version()).strip()
        return "Fluke 5440B, software version {version}".format(version=version)

    async def connect(self):
        self.__lock = asyncio.Lock()

        await self.__conn.connect()
        if hasattr(self.__conn, "set_eot"):
            # Used by the Prologix adapters
            await self.__conn.set_eot(False)
        async with self.__lock:
            await self.__conn.clear()
            await self.__wait_for_state_change()
            await self.__wait_for_idle()

        await asyncio.gather(
            self.__set_terminator(TerminatorType.LF_EOI),   # terminate lines with \n
            self.__set_separator(SeparatorType.COMMA),      # use a comma as the separator
        )

    async def disconnect(self):
        await self.__conn.disconnect()

    async def write(self, cmd):
        assert isinstance(cmd, str) or isinstance(cmd, bytes)
        try:
            cmd = cmd.encode("ascii")
        except AttributeError:
            pass    # cmd is already a bytestring
        # The calibrator can only buffer 127 byte
        if len(cmd) > 127:
            raise ValueError("Command size must be 127 byte or less.")

        await self.__conn.write(cmd)

    async def read(self):
        result = (await self.__conn.read())[:-1].decode("utf-8").split(",")  # strip \n and split at the seprator
        return result[0] if len(result) == 1 else result

    async def query(self, cmd):
        await self.write(cmd)
        return await self.read()

    async def reset(self):
        async with self.__lock:
            await self.write("RESET")
            await self.__wait_for_state_change()
            await self.__wait_for_idle()

    async def __wait_for_state_change(self):
        while (await self.serial_poll()) & SerialPollFlags.DOING_STATE_CHANGE:
            await asyncio.sleep(0.5)

    async def __wait_for_idle(self):
        while (await self.get_state()) != State.IDLE:
            await asyncio.sleep(0.5)

    async def get_terminator(self):
        async with self.__lock:
            return TerminatorType(int(await self.query("GTRM")))

    async def __set_terminator(self, value):
        assert isinstance(value, TerminatorType)
        async with self.__lock:
            await self.write("STRM {value:d}".format(value=value.value))
            await self.__wait_for_state_change()

    async def get_separator(self):
        return SeparatorType(int(await self.query("GSEP")))

    async def __set_separator(self, value):
        assert isinstance(value, SeparatorType)
        async with self.__lock:
            await self.write("SSEP {value:d}".format(value=value.value))
            await self.__wait_for_state_change()

    async def set_mode(self, value):
        assert isinstance(value, ModeType)
        await self.write("{value}".format(value=value.value))

    async def set_output_enabled(self, enabled):
        await self.write("OPER" if enabled else "STBY")

    async def get_output(self):
        return Decimal(await self.query("GOUT"))

    async def set_output(self, value):
        # Note: should be +-20 if in current boost mode
        # Note: should be +-1500 in voltage boost mode
        # Note: should be +-2.2 in divider mode
        #assert (-1100. <= value <= 1100.)
        await self.write("SOUT {value:f}".format(value=value))

    async def set_internal_sense(self, enabled):
        await self.write("ISNS" if enabled else "ESNS")

    async def set_internal_guard(self, enabled):
        await self.write("IGRD" if enabled else "EGRD")

    async def get_voltage_limit(self):
        # TODO catch error when in current boost mode
        return Decimal(await self.query("GVLM"))

    async def set_voltage_limit(self, value):
        # Note should be +-1500 in voltage boost mode
        #assert (-1100. <= value <= 1100.)
        pass

    async def get_current_limit(self):
        # TODO catch error when in voltage boost mode
        return Decimal(await self.query("GCLM"))

    async def set_current_limit(self, value):
        # Note: should be +-0.065 in voltage mode
        # Note: should be +-0.10 in voltage boost mode
        #assert (-20. <= value <= 20.)
        pass

    async def _get_software_version(self):
        return await self.query("GVRS")

    async def get_status(self):
        return StatusFlags(int(await self.query("GSTS")))

    async def get_error(self):
        return ErrorCode(int(await self.query("GERR")))

    async def get_state(self):
        try:
            return State(int(await self.__get_state()))
        except ValueError as e:
            raise InvalidStateError(e.args[0], result) from None

    async def __get_state(self):
        return await self.query("GDNG")

    async def selftest_digital(self):
        async with self.__lock:
            await self.__wait_for_idle()
            self.__logger.info("Running digital selftest. This takes about 5 seconds.")
            await self.write("TSTD")

            state = State.IDLE
            # Wait until we are done
            while "testing":
                new_state = await self.__get_state()
                try:
                    # test if it is an error code or state
                    # TODO: this needs to be verified with a broken unit, I can only guess, that the selftest will
                    # return a non zero result during test, which will be in the buffer, so the final result might be
                    # either the $errorcode, $errorcode\n$state or something else.
                    new_state = State(int(new_state))
                except ValueError:
                    self.__logger.warning("Digital selftest failed.")
                    return new_state

                if new_state not in (State.IDLE, State.SELF_TEST_MAIN_CPU, State.SELF_TEST_FRONTPANEL_CPU, State.SELF_TEST_GUARD_CPU):
                    self.__logger.warning("Digital selftest failed.")
                    return new_state.value

                if new_state != state:
                    state = new_state
                    if state == State.IDLE:
                        break
                    self.__logger.info("Selftest status: {status}".format(status=state))
                await asyncio.sleep(0.1)
            self.__logger.info("Digital selftest passed.")
            return state.value

    async def selftest_analog(self):
        async with self.__lock:
            await self.__wait_for_idle()
            self.__logger.info("Running analog selftest. This takes about 4 minutes.")
            await self.write("TSTA")

            state = State.IDLE
            # Wait until we are done
            while "testing":
                new_state = await self.__get_state()
                try:
                    # test if it is an error code or state
                    # TODO: this needs to be verified with a broken unit, I can only guess, that the selftest will
                    # return a non zero result during test, which will be in the buffer, so the final result might be
                    # either the $errorcode, $errorcode\n$state or something else.
                    new_state = State(int(new_state))
                except ValueError:
                    self.__logger.warning("Analog selftest failed. Code: {code}.".format(code=new_state))
                    return new_state

                if new_state not in (State.IDLE, State.CALIBRATING_ADC, State.SELF_TEST_LOW_VOLTAGE, State.SELF_TEST_OVEN):
                    self.__logger.warning("Analog selftest failed. Code: {code}.".format(code=new_state.value))
                    return new_state.value

                if new_state != state:
                    state = new_state
                    if state == State.IDLE:
                        break
                    self.__logger.info("Selftest status: {status}".format(status=state))
                await asyncio.sleep(5.0)
            self.__logger.info("Analog selftest passed.")
            return state.value

    async def selftest_hv(self):
        async with self.__lock:
            await self.__wait_for_idle()
            self.__logger.info("Running high voltage selftest. This takes about 1 minute")
            await self.write("TSTH")

            state = State.IDLE
            # Wait until we are done
            while "testing":
                new_state = await self.__get_state()
                try:
                    # test if it is an error code or state
                    # TODO: this needs to be verified with a broken unit, I can only guess, that the selftest will
                    # return a non zero result during test, which will be in the buffer, so the final result might be
                    # either the $errorcode, $errorcode\n$state or something else.
                    new_state = State(int(new_state))
                except ValueError:
                    self.__logger.warning("High voltage selftest failed. Code: {code}.".format(code=new_state))
                    return new_state

                if new_state not in (State.IDLE, State.CALIBRATING_ADC, State.SELF_TEST_HIGH_VOLTAGE):
                    self.__logger.warning("High voltage selftest failed. Code: {code}.".format(code=new_state.value))
                    return new_state.value

                if new_state != state:
                    state = new_state
                    if state == State.IDLE:
                        break
                    self.__logger.info("Selftest status: {status}".format(status=state))
                await asyncio.sleep(2.0)
            self.__logger.info("High voltage selftest passed.")
            return state.value

    async def selftest_all(self):
        result = await self.selftest_digital()
        if result != 0:
            return result

        result = await self.selftest_analog()
        if result != 0:
            return result

        result = await self.selftest_hv()
        return result

    async def acal(self):
        async with self.__lock:
            await self.__wait_for_idle()
            self.__logger.info("Running internal calibration. This will take about 6.5 minutes.")
            await self.write("CALI")

            state = State.IDLE
            # Wait until we are done
            while "calibrating":
                new_state = await self.get_state()

                if new_state not in (
                    State.IDLE,
                    State.CALIBRATING_ADC,
                    State.ZEROING_10V_pos,
                    State.CAL_N1_N2_RATIO,
                    State.ZEROING_10V_neg,
                    State.ZEROING_20V_pos,
                    State.ZEROING_20V_neg,
                    State.ZEROING_250V_pos,
                    State.ZEROING_250V_neg,
                    State.ZEROING_1000V_pos,
                    State.ZEROING_1000V_neg,
                    State.CALIBRATING_GAIN_10V_pos,
                    State.CALIBRATING_GAIN_20V_pos,
                    State.CALIBRATING_GAIN_HV_pos,
                    State.CALIBRATING_GAIN_HV_neg,
                    State.CALIBRATING_GAIN_20V_neg,
                    State.CALIBRATING_GAIN_10V_neg,
                    State.WRITING_TO_NVRAM,
                ):
                    self.__logger.warning("Invalid code: {code}.".format(code=new_state.value))
#                    return new_state.value

                if new_state != state:
                    state = new_state
                    if state == State.IDLE:
                        break
                    self.__logger.info("Calibration status: {status}".format(status=state))
                await asyncio.sleep(1.0)
            self.__logger.info("Internal calibration done.")
            return state.value

    async def get_baud_rate(self):
        return BAUD_RATES_AVAILABLE[int(await self.query("GBDR"))]

    async def set_baud_rate(self, value):
        assert (value in BAUD_RATES_AVAILABLE)
        await self.write("SBDR {value:d}".format(value=value))

    async def set_enable_rs232(self, enabled):
        await self.write("MONY" if enabled else "MONN")

    async def get_calibration_constants(self):
        async with self.__lock:
            # We need to split the query in two parts, because the input buffer of the 5440B is only 127 byte
            result = await self.query(",".join(["GCAL " + str(i) for i in range(10)]))
            result += await self.query(",".join(["GCAL " + str(i) for i in range(10,20)]))
            return {
                "gain_0.2V": Decimal(result[5]),
                "gain_2V": Decimal(result[4]),
                "gain_10V": Decimal(result[0]),
                "gain_20V": Decimal(result[1]),
                "gain_250V": Decimal(result[2]),
                "gain_1000V": Decimal(result[3]),
                "offset_10V_pos": Decimal(result[6]),
                "offset_20V_pos": Decimal(result[7]),
                "offset_250V_pos": Decimal(result[8]),
                "offset_1000V_pos": Decimal(result[9]),
                "offset_10V_neg": Decimal(result[10]),
                "offset_20V_neg": Decimal(result[11]),
                "offset_250V_neg": Decimal(result[12]),
                "offset_1000V_neg": Decimal(result[13]),
                "gain_shift_10V": Decimal(result[14]),
                "gain_shift_20V": Decimal(result[15]),
                "gain_shift_250V": Decimal(result[16]),
                "gain_shift_1000V": Decimal(result[17]),
                "resolution_ratio": Decimal(result[18]),
                "a/d_gain": Decimal(result[19]),
            }

    async def serial_poll(self):
        return SerialPollFlags(int(await self.__conn.serial_poll()))
