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

class DeviceError(Exception):
    def __init__(self, message, errorCode):
        super().__init__(message)

        self.code = errorCode

class SelftestError(DeviceError):
    pass

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

class ModeType(Enum):
    NORMAL = "BSTO"
    VOLTAGE_BOOST = "BSTV"
    CURRENT_BOOST = "BSTC"

class SeparatorType(Enum):
    COMMA = 0
    COLON = 1

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

class TerminatorType(Enum):
    EOI       = 0
    CR_LF_EOI = 1
    LF_EOI    = 2
    CR_LF     = 3
    LF        = 4

class SerialPollFlags(Flag):
    NONE               = 0b0
    DOING_STATE_CHANGE = 1 << 2
    MSG_RDY            = 1 << 3
    OUTPUT_SETTLED     = 1 << 4
    ERROR_CONDITION    = 1 << 5
    SRQ                = 1 << 6

class SrqMask(Flag):
    NONE                = 0b0
    DOING_STATE_CHANGE  = 1 << 2
    MSG_RDY             = 1 << 3
    OUTPUT_SETTLED      = 1 << 4
    ERROR_CONDITION     = 1 << 5

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
        return f"Fluke 5440B, software version {version}"

    async def connect(self):
        self.__lock = asyncio.Lock()

        await self.__conn.connect()
        if hasattr(self.__conn, "set_eot"):
            # Used by the Prologix adapters
            await self.__conn.set_eot(False)

        async with self.__lock:
            status = await self.serial_poll()              # clears the SRQ bit
            while status & SerialPollFlags.MSG_RDY:        # clear message buffer
                msg = await self.read()
                self.__logger.debug(f"Calibrator message at boot: {msg}.")
                status = await self.serial_poll()

            if status & SerialPollFlags.ERROR_CONDITION:
                err = await self.get_error()                    # clear error flags not produced by us
                self.__logger.debug(f"Calibrator errors at boot: {err}.")
            state = await self.get_state()
            self.__logger.debug(f"Calibrator state at boot: {state}.")
            if state != State.IDLE:
                await self.set_srq_mask(SrqMask.DOING_STATE_CHANGE)
                await self.__wait_for_idle()

            await self.__set_terminator(TerminatorType.LF_EOI)   # terminate lines with \n
            await self.__set_separator(SeparatorType.COMMA)      # use a comma as the separator
            await self.set_srq_mask(SrqMask.NONE)                # Disable interrupts

    async def disconnect(self):
        try:
            # Return access to the device
            await self.local()
        except ConnectionError:
            pass
        finally:
            await self.__conn.disconnect()

    async def write(self, cmd, test_error=False):
        assert isinstance(cmd, str) or isinstance(cmd, bytes)
        try:
            cmd = cmd.encode("ascii")
        except AttributeError:
            pass    # cmd is already a bytestring
        # The calibrator can only buffer 127 byte
        if len(cmd) > 127:
            raise ValueError("Command size must be 127 byte or less.")

        await self.__conn.write(cmd)
        if test_error:
            await asyncio.sleep(0.2)    # The device is slow in parsing commands
            if (await self.serial_poll()) & SerialPollFlags.ERROR_CONDITION:
                err = await self.get_error()
                raise DeviceError(f"Device error on command: {cmd}, code: {err}", err)

    async def read(self):
        result = (await self.__conn.read()).rstrip().decode("utf-8").split(",")  # strip \n and split at the seprator
        return result[0] if len(result) == 1 else result

    async def query(self, cmd, test_error=False):
        await self.write(cmd, test_error)
        return await self.read()

    async def __wait_for_state_change(self):
        while (await self.serial_poll()) & SerialPollFlags.DOING_STATE_CHANGE:
            await asyncio.sleep(0.5)

    async def reset(self):
        async with self.__lock:
            # We do not send "RESET", because a DCL will do the same and additionally circumvents the input buffer
            await self.__conn.clear()
            # We cannot use interrupts, because the device is resetting all settings and will not accept commands
            # until it has reset. So we will poll the status register first, and when this is done, we will poll
            # the device itself until it is ready
            await self.__wait_for_state_change()
            while (await self.get_state()) != State.IDLE:
                await asyncio.sleep(0.5)

            await self.__set_terminator(TerminatorType.LF_EOI)   # terminate lines with \n
            await self.__set_separator(SeparatorType.COMMA)      # use a comma as the separator
            await self.set_srq_mask(SrqMask.NONE)                # Disable interrupts

    async def local(self):
        await self.__conn.ibloc()

    async def get_terminator(self):
        async with self.__lock:
            return TerminatorType(int(await self.query("GTRM")))

    async def __set_terminator(self, value):
        """
        Engage lock, before calling
        """
        assert isinstance(value, TerminatorType)
        await self.write(f"STRM {value.value:d}", test_error=True)
        await self.__wait_for_state_change()

    async def get_separator(self):
        return SeparatorType(int(await self.query("GSEP")))

    async def __set_separator(self, value):
        """
        Engage lock, before calling
        """
        assert isinstance(value, SeparatorType)
        await self.write(f"SSEP {value.value:d}", test_error=True)
        await self.__wait_for_state_change()

    async def set_mode(self, value):
        assert isinstance(value, ModeType)
        await self.write(f"{value.value}", test_error=True)

    async def set_output_enabled(self, enabled):
        await self.write("OPER" if enabled else "STBY", test_error=True)

    async def get_output(self):
        return Decimal(await self.query("GOUT"))

    def __limit_numeric(self, value):
        # According to page 4-5 of the operator manual, the value needs to meet the follwing criteria:
        # - Maximum of 8 significant digits
        # - Exponent must have less than two digits
        # - Intgers must be less than 256
        # - 10e-12 < abs(value) < 10e8
        # Limit to to 10*-8 resolution (10 nV is the minimum)
        result = f"{value:.8f}"
        if abs(value) >= 1:
            # There are significant digits before the decimal point, so we need to limit the length of the string
            # to 9 characters (decimal point + 8 significant digits)
            result = f"{result:.9s}"
        return result

    async def set_output(self, value, test_error=True):
        if -1500 > value > 1500:
            raise ValueError("Value out of range")
        value = self.__limit_numeric(value)

        try:
            await self.write(f"SOUT {value}", test_error)
        except DeviceError as e:
            if e.code == ErrorCode.OUTPUT_OUTSIDE_LIMITS:
                raise ValueError("Value out of range") from None
            else:
                raise

    async def set_internal_sense(self, enabled):
        try:
            await self.write("ISNS" if enabled else "ESNS", test_error=True)
        except DeviceError as e:
            if e.code == ErrorCode.INVALID_SENSE_MODE:
                raise TypeError("Sense mode not allowed.") from None
            else:
                raise

    async def set_internal_guard(self, enabled):
        try:
            await self.write("IGRD" if enabled else "EGRD", test_error=True)
        except DeviceError as e:
            if e.code == ErrorCode.INVALID_GUARD_MODE:
                raise TypeError("Guard mode not allowed.") from None
            else:
                raise

    async def set_divider(self, enabled):
        await self.write("DIVY" if enabled else "DIVN", test_error=True)

    async def get_voltage_limit(self):
        # TODO: Needs testing for error when in current boost mode
        result = await self.query("GVLM", test_error=True)
        return Decimal(result[1]), Decimal(result[0])

    async def set_voltage_limit(self, value, value2=None):
        if -1500 > value > 1500:
            raise ValueError("Value out of range.")
        if value2 is not None:
            if not (-1500 <= value2 <= 1500):
                raise ValueError("Value out of range.")
            elif not (value * value2 <= 0):
                # Make sure, that one value is positive and one value negative or zero.
                raise ValueError("Invalid voltage limit.")

        value = self.__limit_numeric(value)
        try:
            if value2 is not None:
                value2 = self.__limit_numeric(value2)
                await self.write(f"SVLM {value2}", test_error=True)
            await self.write(f"SVLM {value}", test_error=True)
        except DeviceError as e:
            if e.code == ErrorCode.LIMIT_OUT_OF_RANGE:
                raise ValueError("Invalid voltage limit.") from None
            else:
                raise

    async def get_current_limit(self):
        # TODO: Needs testing for error when in voltage boost mode
        result = await self.query("GCLM", test_error=True)
        if isinstance(result, list):
            return Decimal(result[1]), Decimal(result[0])
        else:
            return Decimal(result)

    async def set_current_limit(self, value, value2=None):
        if -20 > value > 20:
            raise ValueError("Value out of range.")
        if value2 is not None:
            if not (-20 <= value2 <= 20):
                raise ValueError("Value out of range.")
            if not (value * value2 <= 0):
                raise ValueError("Invalid current limit.")

        value = self.__limit_numeric(value)
        try:
            if value2 is not None:
                value2 = self.__limit_numeric(value2)
                await self.write(f"SCLM {value2}", test_error=True)
            await self.write(f"SCLM {value}", test_error=True)
        except DeviceError as e:
            if e.code == ErrorCode.LIMIT_OUT_OF_RANGE:
                raise ValueError("Invalid current limit.") from None
            else:
                raise

    async def _get_software_version(self):
        return await self.query("GVRS")

    async def get_status(self):
        return StatusFlags(int(await self.query("GSTS")))

    async def get_error(self):
        return ErrorCode(int(await self.query("GERR")))

    async def get_state(self):
        return State(int(await self.query("GDNG")))

    async def __wait_for_rqs(self):
        await self.__conn.wait((1 << 11) | (1<<14))    # Wait for RQS or TIMO
        if hasattr(self.__conn, "ibsta"):
            ibsta = await self.__conn.ibsta()
            # Check for timeout
            if ibsta & (1 << 14):
                self.__logger.warning("Timeout during wait. Is the IbaAUTOPOLL(0x7) bit set for the board or the timeout set too low?")

    async def __wait_for_idle(self):
        """
        Make sure, that SrqMask.DOING_STATE_CHANGE is set.
        """
        state = await self.get_state()
        while state != State.IDLE:
            self.__logger.info(f"Calibrator busy: {state}.")
            await self.__wait_for_rqs()
            await self.serial_poll()           # Clear the SRQ bit
            state = await self.get_state()

    async def selftest_digital(self):
        async with self.__lock:
            await self.set_srq_mask(SrqMask.DOING_STATE_CHANGE)   # Enable SRQs to wait for each test step
            try:
                self.__logger.info("Running digital selftest. This takes about 5 seconds.")
                await self.__wait_for_idle()
                await self.get_error()          # Clear the error flag if set

                await self.write("TSTD", test_error=True)
                while "testing":
                    await self.__wait_for_rqs()
                    status = await self.serial_poll()  # Clear SRQ
                    if status & SerialPollFlags.MSG_RDY:
                        msg = await self.read()
                        self.__logger.warning(f"Digital selftest failed with message: {msg}.")
                        raise SelftestError(f"Digital selftest failed with message: {msg}.", msg)
                        return msg
                    if status & SerialPollFlags.DOING_STATE_CHANGE:
                        state = await self.get_state()
                        if state not in (State.IDLE, State.SELF_TEST_MAIN_CPU, State.SELF_TEST_FRONTPANEL_CPU, State.SELF_TEST_GUARD_CPU):
                            self.__logger.warning(f"Digital selftest failed. Invalid state: {state}.")
                            return state

                        if state == State.IDLE:
                            break
                        self.__logger.info(f"Selftest status: {state}.")
                self.__logger.info("Digital selftest passed.")
            finally:
                await self.set_srq_mask(SrqMask.NONE)   # Disable SRQs

    async def selftest_analog(self):
        async with self.__lock:
            await self.set_srq_mask(SrqMask.DOING_STATE_CHANGE)   # Enable SRQs to wait for each test step
            try:
                self.__logger.info("Running analog selftest. This takes about 4 minutes.")
                await self.__wait_for_idle()
                await self.get_error()          # Clear the error flag if set

                await self.write("TSTA", test_error=True)
                while "testing":
                    await self.__wait_for_rqs()
                    status = await self.serial_poll()  # Clear SRQ
                    if status & SerialPollFlags.MSG_RDY:
                        msg = await self.read()
                        self.__logger.warning(f"Analog selftest failed with message: {msg}.")
                        raise SelftestError(f"Analog selftest failed with message: {msg}.", msg)
                    if status & SerialPollFlags.DOING_STATE_CHANGE:
                        state = await self.get_state()
                        if state not in (State.IDLE, State.CALIBRATING_ADC, State.SELF_TEST_LOW_VOLTAGE, State.SELF_TEST_OVEN):
                            self.__logger.warning(f"Analog selftest failed. Invalid state: {state}.")
                            return state

                        if state == State.IDLE:
                            break
                        self.__logger.info(f"Selftest status: {state}.")
                self.__logger.info("Analog selftest passed.")
            finally:
                await self.set_srq_mask(SrqMask.NONE)   # Disable SRQs

    async def selftest_hv(self):
        async with self.__lock:
            await self.set_srq_mask(SrqMask.DOING_STATE_CHANGE)   # Enable SRQs to wait for each test step
            try:
                self.__logger.info("Running high voltage selftest. This takes about 1 minute.")
                await self.__wait_for_idle()
                await self.get_error()          # Clear the error flag if set

                await self.write("TSTH", test_error=True)
                while "testing":
                    await self.__wait_for_rqs()
                    status = await self.serial_poll()  # Clear SRQ
                    if status & SerialPollFlags.MSG_RDY:
                        msg = await self.read()
                        self.__logger.warning(f"High voltage selftest failed with message: {msg}.")
                        raise SelftestError(f"High voltage selftest failed with message: {msg}.", msg)
                    if status & SerialPollFlags.DOING_STATE_CHANGE:
                        state = await self.get_state()
                        if state not in (State.IDLE, State.CALIBRATING_ADC, State.SELF_TEST_HIGH_VOLTAGE):
                            self.__logger.warning(f"High voltage selftest failed. Invalid state: {state}.")
                            return state

                        if state == State.IDLE:
                            break
                        self.__logger.info(f"Selftest status: {state}.")
                self.__logger.info("High voltage selftest passed.")
            finally:
                await self.set_srq_mask(SrqMask.NONE)   # Disable SRQs

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
            await self.set_srq_mask(SrqMask.DOING_STATE_CHANGE)   # Enable SRQs to wait for each calibration step
            try:
                self.__logger.info("Running internal calibration. This will take about 6.5 minutes.")
                await self.__wait_for_idle()
                await self.get_error()          # Clear the error flag if set

                await self.write("CALI", test_error=True)
                while "calibrating":
                    await self.__wait_for_rqs()
                    status = await self.serial_poll()  # Clear SRQ
                    state = await self.get_state()
                    if state not in (
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
                        self.__logger.warning(f"Internal calibration failed. Invalid state: {state}.")

                    if state == State.IDLE:
                        break
                        self.__logger.info(f"Calibration status: {state}")
                self.__logger.info("Internal calibration done.")
                return 0    # Return 0 on success
            finally:
                await self.set_srq_mask(SrqMask.NONE)   # Disable SRQs

    async def get_calibration_constants(self):
        async with self.__lock:
            # We need to split the query in two parts, because the input buffer of the 5440B is only 127 byte
            result = await self.query(",".join(["GCAL " + str(i) for i in range(10)]), test_error=True)
            result += await self.query(",".join(["GCAL " + str(i) for i in range(10,20)]), test_error=True)
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
                "adc_gain": Decimal(result[19]),
            }

    async def get_rs232_baud_rate(self):
        return BAUD_RATES_AVAILABLE[int(await self.query("GBDR", test_error=True))]

    async def set_rs232_baud_rate(self, value):
        if not (value in BAUD_RATES_AVAILABLE):
            raise ValueError("Invalid baud rate. It must be one of: 50, 75, 110, 134.5, 150, 200, 300, 600, 1200, 1800, 2400, 4800, 9600.")
        async with self.__lock:
            self.__logger.info("Setting baud rate and writing to NVRAM. This takes about 1.5 minutes.")
            try:
                await self.write(f"SBDR {BAUD_RATES_AVAILABLE.index(value):d}", test_error=True)
                await self.set_srq_mask(SrqMask.DOING_STATE_CHANGE)   # Enable SRQs to wait until written to NVRAM
                await asyncio.sleep(0.5)
                await self.__wait_for_idle()
            finally:
                await self.set_srq_mask(SrqMask.NONE)   # Disable SRQs

    async def set_enable_rs232(self, enabled):
        await self.write("MONY" if enabled else "MONN", test_error=True)

    async def serial_poll(self):
        return SerialPollFlags(int(await self.__conn.serial_poll()))

    async def get_srq_mask(self):
        return SrqMask(int(await self.query("GSRQ")))

    async def set_srq_mask(self, value):
        assert isinstance(value, SrqMask)
        await self.write(f"SSRQ {value.value:d}")
