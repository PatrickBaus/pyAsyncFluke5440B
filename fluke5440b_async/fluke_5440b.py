# ##### BEGIN GPL LICENSE BLOCK #####
#
# Copyright (C) 2023 Patrick Baus
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
"""
This is an asyncIO driver for the Fluke 5440B voltage calibrator to abstract away the GPIB interface.
"""

import asyncio
import itertools
import logging
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
from types import TracebackType
from typing import TYPE_CHECKING, Self, cast, override

from fluke5440b_async.enums import DeviceState, ErrorCode, ModeType, SelfTestErrorCode, SeparatorType, TerminatorType
from fluke5440b_async.errors import DeviceError, SelftestError
from fluke5440b_async.flags import SerialPollFlags, SrqMask, StatusFlags

if TYPE_CHECKING:
    from async_gpib import AsyncGpib
    from prologix_gpib_async import AsyncPrologixGpibController

# The value of a `type` alias is evaluated lazily, so the adapter libraries are only needed for type checking
type GpibConnection = AsyncGpib | AsyncPrologixGpibController

BAUD_RATES_AVAILABLE = (50, 75, 110, 134.5, 150, 200, 300, 600, 1200, 1800, 2400, 4800, 9600)


def _decode_error(code: int) -> ErrorCode | SelfTestErrorCode | int:
    """
    Convert an error number returned by the instrument to an enum. Command errors are looked up first, then
    self-test/calibration faults. Unknown codes are returned as a plain int, so that the original error is never lost.
    """
    try:
        return ErrorCode(code)
    except ValueError:
        pass
    try:
        return SelfTestErrorCode(code)
    except ValueError:
        return code


def _decode_selftest_error(code: int) -> SelfTestErrorCode | int:
    """
    Convert an error number returned by the instrument after a failed self-test to an enum. Unknown codes are returned
    as a plain int, so that the original error is never lost.
    """
    try:
        return SelfTestErrorCode(code)
    except ValueError:
        return code


def _parse_int(result: str | list[str]) -> int:
    """Parse an integer reply from the instrument, raising a ValueError with the reply if it is not an integer."""
    try:
        if not isinstance(result, str):
            raise ValueError
        return int(result)
    except ValueError:
        raise ValueError(f"Invalid reply received. Expected an integer, but received: {result}") from None


class _ReentrantLock:
    """
    An asyncio lock, that can be acquired again by the task already holding it. This allows the multistep sequences
    (self-tests, ACAL, ...) to hold the lock while calling :func:`Fluke_5440B.write` and :func:`Fluke_5440B.query`,
    which lock as well.
    """

    def __init__(self) -> None:
        self.__lock = asyncio.Lock()
        self.__owner: asyncio.Task | None = None
        self.__depth = 0

    async def __aenter__(self) -> None:
        task = asyncio.current_task()
        if self.__owner is not None and self.__owner is task:
            self.__depth += 1
            return
        await self.__lock.acquire()
        self.__owner = task
        self.__depth = 1

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, traceback: TracebackType | None
    ) -> None:
        self.__depth -= 1
        if self.__depth == 0:
            self.__owner = None
            self.__lock.release()


@dataclass(slots=True)
class CalibrationConstants:  # pylint: disable=too-many-instance-attributes
    """The calibration constants of the Fluke 5440B."""

    # capital V due to SI pylint: disable=invalid-name
    gain_02V: Decimal
    gain_2V: Decimal
    gain_10V: Decimal
    gain_20V: Decimal
    gain_250V: Decimal
    gain_1000V: Decimal
    offset_10V_pos: Decimal
    offset_20V_pos: Decimal
    offset_250V_pos: Decimal
    offset_1000V_pos: Decimal
    offset_10V_neg: Decimal
    offset_20V_neg: Decimal
    offset_250V_neg: Decimal
    offset_1000V_neg: Decimal
    gain_shift_10V: Decimal
    gain_shift_20V: Decimal
    gain_shift_250V: Decimal
    gain_shift_1000V: Decimal
    resolution_ratio: Decimal
    adc_gain: Decimal

    @override
    def __str__(self) -> str:
        """Pretty-print the calibration constants."""
        return (
            f"Gain 0.2 V       : {self.gain_02V*10**3:.8f} mV\n"
            f"Gain 2 V         : {self.gain_2V*10**3:.8f} mV\n"
            f"Gain 10 V        : {self.gain_10V*10**3:.8f} mV\n"
            f"Gain 20 V        : {self.gain_20V*10**3:.8f} mV\n"
            f"Gain 250 V       : {self.gain_250V*10**3:.8f} mV\n"
            f"Gain 1000 V      : {self.gain_1000V*10**3:.8f} mV\n"
            f"Offset +10 V     : {self.offset_10V_pos*10**3:.8f} mV\n"
            f"Offset +20 V     : {self.offset_20V_pos*10**3:.8f} mV\n"
            f"Offset +250 V    : {self.offset_250V_pos*10**3:.8f} mV\n"
            f"Offset +1000 V   : {self.offset_1000V_pos*10**3:.8f} mV\n"
            f"Offset -10 V     : {self.offset_10V_neg*10**3:.8f} mV\n"
            f"Offset -20 V     : {self.offset_20V_neg*10**3:.8f} mV\n"
            f"Offset -250 V    : {self.offset_250V_neg*10**3:.8f} mV\n"
            f"Offset -1000 V   : {self.offset_1000V_neg*10**3:.8f} mV\n"
            f"Gain shift 10 V  : {self.gain_shift_10V} µV/V\n"
            f"Gain shift 20 V  : {self.gain_shift_20V} µV/V\n"
            f"Gain shift 250 V : {self.gain_shift_250V} µV/V\n"
            f"Gain shift 1000 V: {self.gain_shift_1000V} µV/V\n"
            f"Resolution ratio : {self.resolution_ratio}\n"
            f"ADC gain         : {self.adc_gain*10**3:.8f} mV"
        )


class Fluke_5440B:  # noqa pylint: disable=too-many-public-methods,invalid-name,too-many-lines
    """
    The driver for the Fluke 5440B voltage calibrator. It supports both linux-gpib and the Prologix GPIB adapters.
    """

    @property
    def connection(self) -> GpibConnection:
        """
        The GPIB connection.
        """
        return self.__conn

    def __init__(self, connection: GpibConnection, log_level: int = logging.WARNING):
        """
        Create Fluke 5440B device with the GPIB connection given.

        Parameters
        ----------
        connection: AsyncGpib or AsyncPrologixGpibController
            The GPIB connection.
        log_level: int, default=logging.WARNING
            The level of logging output. By default, only warnings or higher are output.
        """
        self.__conn = connection
        self.__lock = _ReentrantLock()

        self.__logger = logging.getLogger(__name__)
        self.__logger.setLevel(log_level)  # Only log really important messages by default

    @override
    def __str__(self) -> str:
        return f"Fluke 5440B at {str(self.connection)}"

    async def __aenter__(self) -> Self:
        await self.connect()
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, traceback: TracebackType | None
    ) -> None:
        await self.disconnect()

    async def get_id(self) -> tuple[str, str, str, str]:
        """
        Returns the instrument name and the software version string. To emulate the `*IDN?` SCPI command, the result
        is a tuple containing the Manufacturer, Device, Serial (0) and FW version.
        Returns
        -------
        tuple of str
            A tuple containing the manufacturer id, device id, a zero, and the software version.
        """
        version = (await self._get_software_version()).strip()
        return "Fluke", "5440B", "0", version

    def set_log_level(self, loglevel: int = logging.WARNING):
        """
        Set the log level of the library. By default, the level is set to warning.
        Parameters
        ----------
        loglevel: int, default=logging.WARNING
            The log level of the library
        """
        self.__logger.setLevel(loglevel)

    async def connect(self) -> None:
        """
        Connect the GPIB connection and configure the GPIB device for the DMM. This function must be called from the
        AsyncIO loop and takes care of connecting the GPIB adapter.
        """
        await self.__conn.connect()
        if hasattr(self.__conn, "set_eot"):
            # Used by the Prologix adapters
            await self.__conn.set_eot(False)

        async with self.__lock:
            status = await self.serial_poll()  # clears the SRQ bit
            while status & SerialPollFlags.MSG_RDY:  # clear message buffer
                msg = await self.read()
                self.__logger.debug("Calibrator message at boot: %s.", msg)
                status = await self.serial_poll()

            if status & SerialPollFlags.ERROR_CONDITION:
                error = _decode_error(await self.get_error())  # clear error flags not produced by us
                self.__logger.debug("Calibrator errors at boot: %s.", error)
            state = await self.get_state()
            self.__logger.debug("Calibrator state at boot: %s.", state)
            if state != DeviceState.IDLE:
                await self.set_srq_mask(SrqMask.DOING_STATE_CHANGE)
                await self.__wait_for_idle()

            await self.__set_terminator(TerminatorType.LF_EOI)  # terminate lines with \n
            await self.__set_separator(SeparatorType.COMMA)  # use a comma as the separator
            await self.set_srq_mask(SrqMask.NONE)  # Disable interrupts

    async def disconnect(self) -> None:
        """
        Disconnect from the instrument and clean up. This call will also automatically remove the local lockout if set.
        """
        try:
            # Return access to the device
            await self.local()
        except ConnectionError:
            pass
        finally:
            await self.__conn.disconnect()

    async def write(self, cmd: str | bytes, test_error: bool = False):
        """
        Write a string or bytestring to the instrument.
        Parameters
        ----------
        cmd: str or bytes
            The command written to the device
        test_error: bool, default=False
            Check for errors by serial polling after sending the command.

        Raises
        ------
        DeviceError
            If test_error is set to True and there was an error processing the command.
        """
        if isinstance(cmd, str):
            cmd = cmd.encode("ascii")
        elif not isinstance(cmd, bytes):
            raise TypeError(f"Command must be str or bytes, not {type(cmd).__name__}.")
        # The calibrator can only buffer 127 byte
        if len(cmd) > 127:
            raise ValueError("Command size must be 127 byte or less.")

        # Hold the lock, so that the error check below cannot be interleaved with commands from other tasks
        async with self.__lock:
            await self.__conn.write(cmd)
            if test_error:
                await asyncio.sleep(0.2)  # The instrument is slow in parsing commands
                spoll = await self.serial_poll()
                if spoll & SerialPollFlags.ERROR_CONDITION:
                    self.__logger.debug(
                        "Received error while writing command %s. Serial poll register: %s.", cmd, spoll
                    )
                    msg = None
                    if spoll & SerialPollFlags.MSG_RDY:
                        # The command did return some msg, so we need to read that first (and drop it)
                        msg = await self.read()

                    err = _decode_error(await self.get_error())
                    if msg is None:
                        raise DeviceError(f"Device error on command: {cmd.decode('utf-8')}, code: {err}", err)
                    raise DeviceError(
                        f"Device error on command: {cmd.decode('utf-8')}, code: {err}, Message returned: {msg}", err
                    )

    async def read(self) -> str | list[str]:
        """
        Read from the device.
        Returns
        -------
        str or list of str:
            Returns either a simple string, or if multiple results are returned, a list of strings.
        """
        result = (await self.__conn.read()).rstrip().decode("utf-8").split(",")  # strip \n and split at the separator
        return result[0] if len(result) == 1 else result

    async def query(self, cmd: str | bytes, test_error: bool = False) -> str | list[str]:
        """
        Write a string or bytestring to the instrument, then immediately read back the result. This is a combined call
        to :func:`write` and :func:`read`.
        Parameters
        ----------
        cmd: str or bytes
            The command written to the device
        test_error: bool, default=False
            Check for errors by serial polling after sending the command.

        Returns
        -------
        str or list of str:
            Returns either a simple string, or if multiple results are returned, a list of strings.

        Raises
        ------
        DeviceError
            If test_error is set to True and there was an error processing the command.
        """
        async with self.__lock:  # make sure no other task reads our reply
            await self.write(cmd, test_error)
            return await self.read()

    async def __wait_for_state_change(self) -> None:
        while (await self.serial_poll()) & SerialPollFlags.DOING_STATE_CHANGE:
            await asyncio.sleep(0.5)

    async def reset(self) -> None:
        """
        Place the instrument in standby, enable voltage mode, set the output voltage to 0.0, disable the divider output,
        the external guard mode and external sense mode.
        Raises
        ------
        DeviceError
            Raised if there was an error processing the command.
        """
        async with self.__lock:
            # We do not send "RESET", because a DCL will do the same and additionally circumvents the input buffer
            await self.__conn.clear()
            # We cannot use interrupts, because the device is resetting all settings and will not accept commands
            # until it has reset. So we will poll the status register first, and when this is done, we will poll
            # the device itself until it is ready
            await self.__wait_for_state_change()
            while (await self.get_state()) != DeviceState.IDLE:
                await asyncio.sleep(0.5)

            await self.__set_terminator(TerminatorType.LF_EOI)  # terminate lines with \n
            await self.__set_separator(SeparatorType.COMMA)  # use a comma as the separator
            await self.set_srq_mask(SrqMask.NONE)  # Disable interrupts

    async def local(self) -> None:
        """
        Enable the front panel buttons, if the instrument is in local lock out.
        """
        await self.__conn.ibloc()

    async def get_terminator(self) -> TerminatorType:
        """
        Returns the line terminator sent by the instrument.
        Returns
        -------
        TerminatorType
            The line terminator used by the device.
        """
        async with self.__lock:
            result = await self.query("GTRM", test_error=True)
            term = _parse_int(result)
            return TerminatorType(term)

    async def __set_terminator(self, value: TerminatorType) -> None:
        """
        Set the line terminator used by the instrument. The choice of line terminators are EOI, <CR><LF><EOI>,
        <LF><EOI>, <CR><LF> and <LF> only. Engage the lock, before calling.
        Parameters
        ----------
        value: TerminatorType

        Raises
        ------
        DeviceError
            Raised if there was an error processing the command.
        """
        assert isinstance(value, TerminatorType)
        await self.write(f"STRM {value.value:d}", test_error=True)
        await self.__wait_for_state_change()

    async def get_separator(self) -> SeparatorType:
        """
        Returns the separator used by the instrument to separate multiple queries.
        Returns
        -------
        SeparatorType
            The separator used by the device.

        Raises
        ------
        DeviceError
            Raised if there was an error processing the command.
        """
        result = await self.query("GSEP", test_error=True)
        sep = _parse_int(result)
        return SeparatorType(sep)

    async def __set_separator(self, value: SeparatorType) -> None:
        """
        Set the query separator used by the instrument. The choice of separators are "," (colon) and ";" (semicolon).
        Engage the lock, before calling.
        Parameters
        ----------
        value: SeparatorType
            The separator used by the device.

        Raises
        ------
        DeviceError
            Raised if there was an error processing the command.
        """
        assert isinstance(value, SeparatorType)
        await self.write(f"SSEP {value.value:d}", test_error=True)
        await self.__wait_for_state_change()

    async def set_mode(self, value: ModeType) -> None:
        """
        Enabled either voltage or current boost mode using an external Fluke 5205A power amplifier or a Fluke 5220A
        transconductance amplifier.
        Parameters
        ----------
        value: ModeType
            Either normal mode, current or voltage boost.

        Raises
        ------
        DeviceError
            Raised if there was an error processing the command.
        """
        assert isinstance(value, ModeType)
        await self.write(value, test_error=True)

    async def set_output_enabled(self, enabled: bool) -> None:
        """
        Set the output to either STANDBY or OPR.
        Parameters
        ----------
        enabled: bool
            Set to OPR if true

        Raises
        ------
        DeviceError
            Raised if there was an error processing the command.
        """
        await self.write("OPER" if enabled else "STBY", test_error=True)

    async def get_output(self) -> Decimal:
        """
        Returns the output voltage currently set.
        Returns
        -------
        Decimal
            The output voltage set.

        Raises
        ------
        DeviceError
            Raised if there was an error processing the command.
        """
        result = await self.query("GOUT", test_error=True)
        assert isinstance(result, str)
        return Decimal(result)

    @staticmethod
    def __limit_numeric(value: int | float | Decimal) -> str:
        """
        According to page 4-5 of the operator manual, the value needs to meet the following criteria:
         - Maximum of 8 significant digits
         - Exponent must have less than two digits
         - Integers must be less than 256
         - 10e-12 < abs(value) < 10e8
         Limit to to 10*-8 resolution (10 nV is the minimum)

        Parameters
        ----------
        value: int or float or Decimal
            The input to format

        Returns
        -------
        str
            A formatted string of the number.
        """
        # Convert floats via str() to avoid binary representation artifacts, e.g. 0.1 -> 0.1000000000000000055...
        number = Decimal(str(value)) if isinstance(value, float) else Decimal(value)
        if number == 0:
            return "0"
        # Round (not truncate) to 8 significant digits, but never finer than 10 nV (1e-8).
        exponent = max(number.adjusted() - 7, -8)
        result = number.quantize(Decimal(1).scaleb(exponent), rounding=ROUND_HALF_EVEN)
        if result == 0:
            # Below the resolution. Send it like an exact zero, without a sign.
            return "0"
        if result.adjusted() - exponent >= 8:
            # Rounding carried into a 9th significant digit (e.g. 9.99999999 -> 10.0000000), so drop one more decimal
            # place. This does not apply to a carry at the resolution limit (e.g. 6 nV -> 10 nV).
            result = number.quantize(Decimal(1).scaleb(exponent + 1), rounding=ROUND_HALF_EVEN)
        return f"{result:f}"

    async def set_output(self, value: int | float | Decimal, test_error: bool = True) -> None:
        """
        Set the output of the calibrator. If an output greater than ±22 V is set, the calibrator will automatically go
        to STBY for safety reasons. Call `set_output_enabled(True)` to re-enable the output.
        Parameters
        ----------
        value: int or float or Decimal
            The value to be set
        test_error: bool, Default=True
            Raise an exception if there was an error

        Raises
        ------
        DeviceError
            Raised if there was an error processing the command and test_error was set to True.
        """
        if not -1500 <= value <= 1500:
            raise ValueError("Value out of range")
        try:
            await self.write(f"SOUT {self.__limit_numeric(value)}", test_error)
        except DeviceError as e:
            if e.code == ErrorCode.OUTPUT_OUTSIDE_LIMITS:
                raise ValueError("Value out of range") from None
            raise

    async def set_internal_sense(self, enabled: bool) -> None:
        """
        If the load resistance is greater than 1 MΩ, 2-wire calibration can be used. Otherwise, the cable resistance
        will reduce the accuracy. Use internal sense for 2-wire calibrations. See page 2-13 of the operator manual for
        details.

        Parameters
        ----------
        enabled: bool
            Set to True for 2-wire sense.

        Raises
        ------
        ValueError
            Raised if the sense mode is not allowed in the current configuration of the instrument.
        DeviceError
            Raised if there was an error processing the command.
        """
        try:
            await self.write("ISNS" if enabled else "ESNS", test_error=True)
        except DeviceError as e:
            if e.code == ErrorCode.INVALID_SENSE_MODE:
                raise ValueError("Sense mode not allowed.") from None
            raise

    async def set_internal_guard(self, enabled: bool) -> None:
        """
        If set, the guard is internally connected to the output LO terminal. Use this, if the device being calibrated
        has floating inputs. If calibrating devices with grounded inputs, connect the guard terminal to the input LO of
        the device and disable the internal guard. See page 2-14 of the operator manual for details.
        Parameters
        ----------
        enabled: bool
            Set to True for floating devices.

        Raises
        ------
        ValueError
            Raised if the guard mode is not allowed in the current configuration of the instrument.
        DeviceError
            Raised if there was an error processing the command.
        """
        try:
            await self.write("IGRD" if enabled else "EGRD", test_error=True)
        except DeviceError as e:
            if e.code == ErrorCode.INVALID_GUARD_MODE:
                raise ValueError("Guard mode not allowed.") from None
            raise

    async def set_divider(self, enabled: bool) -> None:
        """
        Enable the internal 1:10 and 1:100 divider to reduce the output noise and increase the resolution of voltages
        in the range -2.2 V to 2.2 V. Do not enable the external sense connection via :func:`set_internal_sense(False)`,
        as this will decrease the accuracy. The divider has an output impedance of 450 Ω. The load should ideally be
        greater than 1 GΩ to keep the loading error below 1 ppm. See page 3-10 of the operator manual for details.

        Parameters
        ----------
        enabled: bool
            Set to True to enable the divider.

        Raises
        ------
        DeviceError
            Raised if there was an error processing the command.
        """
        await self.write("DIVY" if enabled else "DIVN", test_error=True)

    async def get_voltage_limit(self) -> Decimal | tuple[Decimal, Decimal]:
        """
        Get the voltage limit set on the instrument. It will raise an error, when in current boost mode.
        Returns
        -------
        Decimal or tuple of Decimal
            The positive and negative limit, or a single value if the instrument only returns one limit

        Raises
        ------
        DeviceError
            Raised if there was an error processing the command.
        """
        # TODO: Needs testing for error when in current boost mode
        result = await self.query("GVLM", test_error=True)
        if isinstance(result, list):
            return Decimal(result[1]), Decimal(result[0])
        return Decimal(result)

    async def set_voltage_limit(
        self, value: int | float | Decimal, value2: int | float | Decimal | None = None
    ) -> None:
        """
        Set the positive and negative voltage limit.
        Parameters
        ----------
        value: int or float or Decimal
            Either a positive or negative number to set the positive or negative limit.
        value2: int or float or Decimal, optional
            Either a positive or negative number to set the positive or negative limit. If omitted, only one limit will
            be set.

        Raises
        ------
        DeviceError
            Raised if there was an error processing the command.
        ValueError
            Raised if the limits are out of bounds.
        """
        value = Decimal(value)
        if not -1500 <= value <= 1500:
            raise ValueError("Value out of range.")
        if value2 is not None:
            value2 = Decimal(value2)
            if not -1500 <= value2 <= 1500:
                raise ValueError("Value out of range.")
            if not value * value2 <= 0:
                # Make sure, that one value is positive and one value negative or zero.
                raise ValueError("Invalid voltage limit.")

        try:
            if value2 is not None:
                await self.write(f"SVLM {self.__limit_numeric(value2)}", test_error=True)
            await self.write(f"SVLM {self.__limit_numeric(value)}", test_error=True)
        except DeviceError as e:
            if e.code == ErrorCode.LIMIT_OUT_OF_RANGE:
                raise ValueError("Invalid voltage limit.") from None
            raise

    async def get_current_limit(self) -> Decimal | tuple[Decimal, Decimal]:
        """
        Get the current limit set on the instrument. It will raise an error, when in voltage boost mode.
        Returns
        -------
        tuple of Decimal
            The positive and negative limit

        Raises
        ------
        DeviceError
            Raised if there was an error processing the command.
        """
        # TODO: Needs testing for error when in voltage boost mode
        result = await self.query("GCLM", test_error=True)
        if isinstance(result, list):
            return Decimal(result[1]), Decimal(result[0])
        return Decimal(result)

    async def set_current_limit(
        self, value: int | float | Decimal, value2: int | float | Decimal | None = None
    ) -> None:
        """
        Set the positive and negative current limit.
        Parameters
        ----------
        value: int or float or Decimal
            Either a positive or negative number to set the positive or negative limit.
        value2: int or float or Decimal, optional
            Either a positive or negative number to set the positive or negative limit. If omitted, only one limit will
            be set.

        Raises
        ------
        DeviceError
            Raised if there was an error processing the command.
        ValueError
            Raised if the limits are out of bounds.
        """
        value = Decimal(value)
        if not -20 <= value <= 20:
            raise ValueError("Value out of range.")
        if value2 is not None:
            value2 = Decimal(value2)
            if not -20 <= value2 <= 20:
                raise ValueError("Value out of range.")
            if not value * value2 <= 0:
                raise ValueError("Invalid current limit.")

        try:
            if value2 is not None:
                await self.write(f"SCLM {self.__limit_numeric(value2)}", test_error=True)
            await self.write(f"SCLM {self.__limit_numeric(value)}", test_error=True)
        except DeviceError as e:
            if e.code == ErrorCode.LIMIT_OUT_OF_RANGE:
                raise ValueError("Invalid current limit.") from None
            raise

    async def _get_software_version(self) -> str:
        """
        Query the version number of the device software. It will return a string formatted as dd.dd.
        Returns
        -------
        str
            The software version number of the instrument.

        Raises
        ------
        DeviceError
            Raised if there was an error processing the command.
        """
        result = await self.query("GVRS", test_error=True)
        assert isinstance(result, str)
        return result

    async def get_status(self) -> StatusFlags:
        """
        Get the status of the instrument. The status flags contain the mode the instrument is running in, like boost
        mode, or the state of the external sense connection, etc.
        Returns
        -------
        StatusFlags
            The status flags of the different settings

        Raises
        ------
        DeviceError
            Raised if there was an error processing the command.
        """
        result = await self.query("GSTS", test_error=True)
        status = _parse_int(result)

        return StatusFlags(status)

    async def get_error(self) -> int:
        """
        Get the last error thrown by the instrument if any. It is recommended to check for errors after using the
        :func:`write` function, if the `test_error` parameter is not set.
        Returns
        -------
        int
            The last error thrown. It might be an ErrorCode or a SelfTestErrorCode. This is ambiguous and depends on the
            last command.
        """
        # Do not test for errors, because this is an infinite loop.
        result = await self.query("GERR", test_error=False)
        error_code = _parse_int(result)

        return error_code

    async def get_state(self) -> DeviceState:
        """
        While the instrument is running long jobs, it signals its current state. Use this to poll the state.
        Returns
        -------
        DeviceState
            The current device state.

        Raises
        ------
        DeviceError
            Raised if there was an error processing the command.
        """
        result = await self.query("GDNG", test_error=True)
        dev_state = _parse_int(result)

        return DeviceState(dev_state)

    async def __wait_for_rqs(self, raise_error: bool = True) -> SerialPollFlags:
        """Wait until the device requests service (RQS)"""
        try:
            await self.__conn.wait((1 << 11) | (1 << 14))  # Wait for RQS or TIMO
        except TimeoutError:
            self.__logger.warning(
                "Timeout during wait. Is the IbaAUTOPOLL(0x7) bit set for the board? Or the timeout set too low?"
            )

        spoll = await self.serial_poll()  # Clear the SRQ bit
        if spoll & SerialPollFlags.ERROR_CONDITION and raise_error:
            self.__logger.debug(
                "Received error while waiting for device to request service. Serial poll register: %s.", spoll
            )
            # If there was an error during waiting, raise it.
            # I have seen GPIB_HANDSHAKE_ERRORs with a prologix adapter, which does a lot of polling during wait.
            # Ignore that error for now.
            err = _decode_error(await self.get_error())
            if err is ErrorCode.GPIB_HANDSHAKE_ERROR:
                self.__logger.info(
                    "Got error during waiting: %s. "
                    "If you are using a Prologix adapter, this can be safely ignored at this point.",
                    err,
                )
            else:
                raise DeviceError(f"Device error, code: {err}", err)
        return spoll

    async def __wait_for_idle(self) -> None:
        """
        Make sure, that SrqMask.DOING_STATE_CHANGE is set.
        """
        state = await self.get_state()
        while state != DeviceState.IDLE:
            self.__logger.info("Calibrator busy: %s.", state)
            await self.__wait_for_rqs()
            state = await self.get_state()

    async def __run_selftest(
        self, name: str, command: str, duration: str, states: tuple[DeviceState, ...], timeout: float | None
    ) -> None:
        """
        Run a self-test and follow its state changes until the instrument is idle again.

        Parameters
        ----------
        name: str
            The name of the self-test used in the log messages and errors, e.g. "digital"
        command: str
            The command starting the self-test
        duration: str
            The approximate duration of the self-test for the log message, e.g. "5 seconds"
        states: tuple of DeviceState
            The states the instrument passes through during the self-test. Other states are logged as a warning.
        timeout: float or None
            The time in seconds the self-test may take, or None to wait forever.

        Raises
        ------
        SelftestError
            Raised if the instrument reports a fault.
        TimeoutError
            Raised if the self-test did not finish within the timeout.
        DeviceError
            Raised if there was an error processing the command.
        """
        title = name[0].upper() + name[1:]
        timer = asyncio.timeout(timeout)
        async with self.__lock:
            await self.set_srq_mask(SrqMask.DOING_STATE_CHANGE)  # Enable SRQs to wait for each test step
            try:
                async with timer:
                    self.__logger.info("Running %s self-test. This takes about %s.", name, duration)
                    await self.__wait_for_idle()

                    await self.write(command, test_error=True)
                    while "testing":
                        status = await self.__wait_for_rqs(raise_error=False)
                        if status & SerialPollFlags.ERROR_CONDITION:
                            error_code = await self.get_error()
                            raise SelftestError(title, _decode_selftest_error(error_code))
                        if status & SerialPollFlags.DOING_STATE_CHANGE:
                            state = await self.get_state()
                            if state not in (DeviceState.IDLE, *states):
                                self.__logger.warning("%s self-test failed. Invalid state: %s.", title, state)

                            if state == DeviceState.IDLE:
                                break
                            self.__logger.info("Self-test status: %s.", state)
                self.__logger.info("%s self-test passed.", title)
            except TimeoutError:
                if not timer.expired():
                    raise  # Raised by the GPIB adapter, not by our timeout
                raise TimeoutError(f"The {name} self-test did not finish within {timeout} s.") from None
            finally:
                await self.__clean_up_after_job(after_timeout=timer.expired())

    async def __clean_up_after_job(self, after_timeout: bool) -> None:
        """
        Disable the SRQs after a self-test or ACAL. A timeout may have interrupted a query between writing the command
        and reading the reply, so unread replies are discarded first. Otherwise, the next query would read them.
        After a timeout, the instrument is probably still busy and may reject the command. This must not hide the
        TimeoutError, so the error is only logged then.
        """
        try:
            if after_timeout:
                while (await self.serial_poll()) & SerialPollFlags.MSG_RDY:
                    self.__logger.debug("Discarding an unread reply after the timeout: %s.", await self.read())
            await self.set_srq_mask(SrqMask.NONE)
        except DeviceError as exc:
            if not after_timeout:
                raise
            self.__logger.warning("Could not disable the SRQs after the timeout, the instrument may be busy: %s.", exc)

    async def selftest_digital(self, timeout: float | None = 10) -> None:
        """
        Test the main CPU, the front panel CPU and the guard CPU. It will take about 5 seconds during which the
        instrument hardware is blocked. See page 3-19 of the operator manual for details.

        Parameters
        ----------
        timeout: float or None, default=10
            The time in seconds the self-test may take, about twice its usual duration. Set to None to wait forever.

        Raises
        ------
        DeviceError
            Raised if there was an error processing the command.
        TimeoutError
            Raised if the self-test did not finish within the timeout.
        """
        await self.__run_selftest(
            "digital",
            "TSTD",
            "5 seconds",
            (DeviceState.SELF_TEST_MAIN_CPU, DeviceState.SELF_TEST_FRONTPANEL_CPU, DeviceState.SELF_TEST_GUARD_CPU),
            timeout,
        )

    async def selftest_analog(self, timeout: float | None = 480) -> None:
        """
        Test the ADC, the low voltage part and the oven. It will take about 4 minutes during which the instrument
        hardware is blocked. See page 3-19 of the operator manual for details.

        Parameters
        ----------
        timeout: float or None, default=480
            The time in seconds the self-test may take, about twice its usual duration. Set to None to wait forever.

        Raises
        ------
        DeviceError
            Raised if there was an error processing the command.
        TimeoutError
            Raised if the self-test did not finish within the timeout.
        """
        await self.__run_selftest(
            "analog",
            "TSTA",
            "4 minutes",
            (DeviceState.CALIBRATING_ADC, DeviceState.SELF_TEST_LOW_VOLTAGE, DeviceState.SELF_TEST_OVEN),
            timeout,
        )

    async def selftest_hv(self, timeout: float | None = 120) -> None:
        """
        Test the ADC and the high voltage part. It will take about 1 minute during which the instrument hardware is
        blocked. See page 3-20 of the operator manual for details.

        Parameters
        ----------
        timeout: float or None, default=120
            The time in seconds the self-test may take, about twice its usual duration. Set to None to wait forever.

        Raises
        ------
        DeviceError
            Raised if there was an error processing the command.
        TimeoutError
            Raised if the self-test did not finish within the timeout.
        """
        await self.__run_selftest(
            "high voltage",
            "TSTH",
            "1 minute",
            (DeviceState.CALIBRATING_ADC, DeviceState.SELF_TEST_HIGH_VOLTAGE),
            timeout,
        )

    async def selftest_all(self) -> None:
        """
        Run all three self-tests. This function is a combination of :func:`selftest_digital`, :func:`selftest_analog`
        and :func:`selftest_hv`.

        Raises
        ------
        DeviceError
            Raised if there was an error processing the command.
        """
        await self.selftest_digital()
        await self.selftest_analog()
        await self.selftest_hv()

    async def acal(self, timeout: float | None = 780) -> None:
        """
        Run the internal calibration routine. It will take about 6.5 minutes during which the instrument hardware is
        blocked. See page 3-2 of the operator manual for details.

        Parameters
        ----------
        timeout: float or None, default=780
            The time in seconds the calibration may take, about twice its usual duration. Set to None to wait forever.

        Raises
        ------
        DeviceError
            Raised if there was an error processing the command or the instrument reports a fault.
        TimeoutError
            Raised if the calibration did not finish within the timeout.
        """
        timer = asyncio.timeout(timeout)
        async with self.__lock:
            await self.set_srq_mask(SrqMask.DOING_STATE_CHANGE)  # Enable SRQs to wait for each calibration step
            try:
                async with timer:
                    self.__logger.info("Running internal calibration. This will take about 6.5 minutes.")
                    await self.__wait_for_idle()

                    await self.write("CALI", test_error=True)
                    while "calibrating":
                        await self.__wait_for_rqs()
                        state = await self.get_state()
                        if state not in (
                            DeviceState.IDLE,
                            DeviceState.CALIBRATING_ADC,
                            DeviceState.ZEROING_10V_POS,
                            DeviceState.CAL_N1_N2_RATIO,
                            DeviceState.ZEROING_10V_NEG,
                            DeviceState.ZEROING_20V_POS,
                            DeviceState.ZEROING_20V_NEG,
                            DeviceState.ZEROING_250V_POS,
                            DeviceState.ZEROING_250V_NEG,
                            DeviceState.ZEROING_1000V_POS,
                            DeviceState.ZEROING_1000V_NEG,
                            DeviceState.CALIBRATING_GAIN_10V_POS,
                            DeviceState.CALIBRATING_GAIN_20V_POS,
                            DeviceState.CALIBRATING_GAIN_HV_POS,
                            DeviceState.CALIBRATING_GAIN_HV_NEG,
                            DeviceState.CALIBRATING_GAIN_20V_NEG,
                            DeviceState.CALIBRATING_GAIN_10V_NEG,
                            DeviceState.WRITING_TO_NVRAM,
                        ):
                            self.__logger.warning("Internal calibration failed. Invalid state: %s.", state)

                        if state == DeviceState.IDLE:
                            break
                        self.__logger.info("Calibration status: %s", state)
                self.__logger.info("Internal calibration done.")
            except TimeoutError:
                if not timer.expired():
                    raise  # Raised by the GPIB adapter, not by our timeout
                raise TimeoutError(f"The internal calibration did not finish within {timeout} s.") from None
            finally:
                await self.__clean_up_after_job(after_timeout=timer.expired())

    async def get_calibration_constants(self) -> CalibrationConstants:
        """
        Query the calibration constants and gain shifts with respect to the previous internal calibration. See page 3-18
        of the operator manual for details.
        Returns
        -------
        CalibrationConstants:
            A dataclass containing the constants as Decimals
        """
        async with self.__lock:
            # We need to split the query in two parts, because the input buffer of the 5440B is only 127 byte
            values: list[str] = []
            for indices in itertools.batched(range(20), 10):
                values += cast(list[str], await self.query(",".join(f"GCAL {i}" for i in indices), test_error=True))
            return CalibrationConstants(
                gain_02V=Decimal(values[5]),
                gain_2V=Decimal(values[4]),
                gain_10V=Decimal(values[0]),
                gain_20V=Decimal(values[1]),
                gain_250V=Decimal(values[2]),
                gain_1000V=Decimal(values[3]),
                offset_10V_pos=Decimal(values[6]),
                offset_20V_pos=Decimal(values[7]),
                offset_250V_pos=Decimal(values[8]),
                offset_1000V_pos=Decimal(values[9]),
                offset_10V_neg=Decimal(values[10]),
                offset_20V_neg=Decimal(values[11]),
                offset_250V_neg=Decimal(values[12]),
                offset_1000V_neg=Decimal(values[13]),
                gain_shift_10V=Decimal(values[14]),
                gain_shift_20V=Decimal(values[15]),
                gain_shift_250V=Decimal(values[16]),
                gain_shift_1000V=Decimal(values[17]),
                resolution_ratio=Decimal(values[18]),
                adc_gain=Decimal(values[19]),
            )

    async def get_rs232_baud_rate(self) -> int | float:
        """
        Return the RS-232 the baud rate in bit/s.
        Returns
        -------
        float
            The baud rate in bit/s

        Raises
        ------
        DeviceError
            If test_error is set to True and there was an error processing the command.
        """
        result = await self.query("GBDR", test_error=True)
        baud_rate = _parse_int(result)
        if not 0 <= baud_rate < len(BAUD_RATES_AVAILABLE):
            raise ValueError(f"Invalid reply received. Expected a baud rate index, but received: {result}")
        return BAUD_RATES_AVAILABLE[baud_rate]

    async def set_rs232_baud_rate(self, value: int | float) -> None:
        """
        Set the baud rate of the RS-232 interface.
        Parameters
        ----------
        value: {50, 75, 110, 134.5, 150, 200, 300, 600, 1200, 1800, 2400, 4800, 9600}
            The baud rate.

        Raises
        ------
        DeviceError
            If test_error is set to True and there was an error processing the command.
        """
        if value not in BAUD_RATES_AVAILABLE:
            raise ValueError(f"Invalid baud rate. It must be one of: {','.join(map(str, BAUD_RATES_AVAILABLE))}.")
        async with self.__lock:
            self.__logger.info("Setting baud rate to %s and writing to NVRAM. This takes about 1.5 minutes.", value)
            try:
                await self.write(f"SBDR {BAUD_RATES_AVAILABLE.index(value):d}", test_error=True)
                await self.set_srq_mask(SrqMask.DOING_STATE_CHANGE)  # Enable SRQs to wait until written to NVRAM
                await asyncio.sleep(0.5)
                await self.__wait_for_idle()
            finally:
                await self.set_srq_mask(SrqMask.NONE)  # Disable SRQs

    async def set_enable_rs232(self, enabled: bool) -> None:
        """
        Enable the RS-232 printer port.
        Parameters
        ----------
        enabled: bool
            True to enable the RS-232 port.

        Raises
        ------
        DeviceError
            If test_error is set to True and there was an error processing the command.
        """
        await self.write("MONY" if enabled else "MONN", test_error=True)

    async def serial_poll(self) -> SerialPollFlags:
        """
        Poll the serial output buffer of the device. This can be used to query for the SRQ bit when device requests
        service, has encountered an error or is busy.
        Returns
        -------
        SerialPollFlags
            The content of the serial output buffer
        """
        return SerialPollFlags(int(await self.__conn.serial_poll()))

    async def get_srq_mask(self) -> SrqMask:
        """
        Get the SRQ mask. This mask is used to determine, when the device will signal the SRQ line.
        Returns
        -------
        SrqMask
            The bitmask to determine the bits to signal.

        Raises
        ------
        DeviceError
            If test_error is set to True and there was an error processing the command.
        """
        result = await self.query("GSRQ", test_error=True)
        mask = _parse_int(result)
        return SrqMask(mask)

    async def set_srq_mask(self, value: SrqMask) -> None:
        """
        Set the service request mask register. Each bit set, will signal the SRQ line, when a service request of the
        device is triggered.
        Parameters
        ----------
        value: SrqMask
            The bitmask to set.

        Raises
        ------
        DeviceError
            If test_error is set to True and there was an error processing the command.
        """
        assert isinstance(value, SrqMask)
        await self.write(f"SSRQ {value.value:d}", test_error=True)
