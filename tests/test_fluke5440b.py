"""Unit tests for the Fluke 5440B driver using a fake GPIB connection (no hardware required)."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import Any, override

import pytest

from fluke5440b_async import (
    CalibrationConstants,
    DeviceState,
    ErrorCode,
    Fluke_5440B,
    ModeType,
    SerialPollFlags,
    SrqMask,
    StatusFlags,
    TerminatorType,
)
from fluke5440b_async.enums import SelfTestErrorCode
from fluke5440b_async.errors import DeviceError, SelftestError

MSG_RDY = SerialPollFlags.MSG_RDY.value
ERROR_CONDITION = SerialPollFlags.ERROR_CONDITION.value
DOING_STATE_CHANGE = SerialPollFlags.DOING_STATE_CHANGE.value


class FakeConnection:  # pylint: disable=missing-function-docstring,too-many-instance-attributes
    """
    Minimal stand-in for AsyncGpib / AsyncPrologixGpibController. It answers queries like the calibrator, keeps an
    output buffer and sets the bits of the serial poll register accordingly.
    """

    def __init__(self) -> None:
        self.written: list[bytes] = []
        self.calls: list[str] = []
        # Replies to queries, by command header
        self.replies: dict[str, str] = {
            "GOUT": "1.5",
            "GVRS": "1.08",
            "GSTS": str(StatusFlags.VOLTAGE_MODE.value | StatusFlags.OUTPUT_ENABLED.value),
            "GTRM": "2",
            "GSEP": "0",
            "GSRQ": "0",
            "GVLM": "1100,-1100",
            "GCLM": "0.02,-0.02",
            "GBDR": "12",
        }
        self.overrides: dict[str, str] = {}  # Replies by command header, these take precedence over all other replies
        self.output_buffer: list[bytes] = []
        self.error_on: dict[str, int] = {}  # Command prefix -> error code raised by the instrument
        self.error = 0
        self.states: list[int] = []  # States returned by GDNG, IDLE once empty
        self.state_change = False
        self.extra_status = 0  # Additional bits returned by the serial poll
        self.error_during_wait: int | None = None  # Error raised by the instrument while a long job is running
        self.wait_timeouts = 0  # Number of waits that time out before the instrument requests service
        self.fail_local = False

    @override
    def __str__(self) -> str:
        return "FakeConnection"

    async def connect(self) -> None:
        self.calls.append("connect")

    async def disconnect(self) -> None:
        self.calls.append("disconnect")

    async def clear(self) -> None:
        self.calls.append("clear")
        self.state_change = True  # A device clear resets the instrument

    async def ibloc(self) -> None:
        if self.fail_local:
            raise ConnectionError("Connection lost")
        self.calls.append("ibloc")

    async def write(self, msg: bytes) -> None:
        await asyncio.sleep(0)  # Let other tasks run, like a real connection would
        self.written.append(msg)
        replies = []
        for cmd in msg.decode("ascii").split(","):
            header = cmd.split(" ")[0]
            for prefix, code in self.error_on.items():
                if cmd.startswith(prefix):
                    self.error = code
            if header in self.overrides:
                replies.append(self.overrides[header])
            elif header == "GERR":
                replies.append(str(self.error))
                self.error = 0
            elif header == "GDNG":
                replies.append(str(self.states.pop(0) if self.states else DeviceState.IDLE.value))
            elif header == "GCAL":
                replies.append(str(int(cmd.split(" ")[1]) + 1))  # GCAL i returns i+1 to check the order
            elif header in self.replies:
                replies.append(self.replies[header])
        if replies:
            self.output_buffer.append(",".join(replies).encode("ascii") + b"\n")

    async def read(self) -> bytes:
        return self.output_buffer.pop(0)

    async def wait(self, mask: int) -> None:  # pylint: disable=unused-argument
        if self.wait_timeouts:
            self.wait_timeouts -= 1
            raise TimeoutError("Timeout waiting for SRQ.")
        self.state_change = True
        if self.error_during_wait is not None:
            self.error = self.error_during_wait

    async def serial_poll(self) -> int:
        status = self.extra_status
        if self.output_buffer:
            status |= MSG_RDY
        if self.error:
            status |= ERROR_CONDITION
        if self.state_change:
            status |= DOING_STATE_CHANGE
            self.state_change = False
        return status

    @property
    def commands(self) -> list[str]:
        """All commands written, decoded."""
        return [cmd.decode("ascii") for cmd in self.written]


class FakePrologixConnection(FakeConnection):
    """The Prologix adapters additionally need the EOI setting."""

    def __init__(self) -> None:
        super().__init__()
        self.eot: bool | None = None

    async def set_eot(self, value: bool) -> None:
        """Enable or disable appending the EOT character, when the instrument signals EOI."""
        self.eot = value


@pytest.fixture(autouse=True)
def no_delays(monkeypatch: pytest.MonkeyPatch) -> None:
    """The driver waits for the slow instrument. Skip these delays to keep the tests fast."""
    sleep = asyncio.sleep

    async def no_sleep(delay: float, result: Any = None) -> Any:  # pylint: disable=unused-argument
        return await sleep(0, result)

    monkeypatch.setattr(asyncio, "sleep", no_sleep)


def run[T](conn: FakeConnection, scenario: Callable[[Fluke_5440B], Awaitable[T]]) -> T:
    """Connect to the fake instrument, run the scenario and disconnect."""

    async def main() -> T:
        async with Fluke_5440B(conn) as device:  # type: ignore[arg-type]
            return await scenario(device)

    return asyncio.run(main())


def with_states(
    conn: FakeConnection, states: list[DeviceState], method: str, *args: Any
) -> Callable[[Fluke_5440B], Awaitable[Any]]:
    """
    Return a scenario, that sets the states the instrument reports and calls the method. The states are set after
    connecting, because connect() reads the state as well.
    """

    async def scenario(device: Fluke_5440B) -> Any:
        conn.states = [state.value for state in states]
        return await getattr(device, method)(*args)

    return scenario


def test_connect_configures_instrument() -> None:
    """connect() must set the terminator, the separator and disable SRQs; leaving must return to local."""
    conn = FakeConnection()

    async def scenario(device: Fluke_5440B) -> None:
        assert str(device) == "Fluke 5440B at FakeConnection"

    run(conn, scenario)
    assert conn.calls == ["connect", "ibloc", "disconnect"]
    for cmd in ("STRM 2", "SSEP 0", "SSRQ 0"):
        assert cmd in conn.commands


def test_connect_prologix_disables_eot() -> None:
    """With a Prologix adapter, connect() must disable the EOT character, the instrument terminates the lines."""
    conn = FakePrologixConnection()

    run(conn, lambda device: asyncio.sleep(0))
    assert conn.eot is False


def test_connect_clears_messages_and_errors_from_boot() -> None:
    """Messages and errors left over from before connecting must be cleared, even unknown error codes."""
    conn = FakeConnection()
    conn.output_buffer.append(b"stale\n")
    conn.error = 999  # Neither an ErrorCode nor a SelfTestErrorCode

    run(conn, lambda device: asyncio.sleep(0))
    assert not conn.output_buffer
    assert conn.error == 0


def test_connect_waits_until_idle() -> None:
    """connect() must wait until a job running on the instrument has finished."""
    conn = FakeConnection()
    conn.states = [DeviceState.SELF_TEST_OVEN.value, DeviceState.SELF_TEST_OVEN.value]

    run(conn, lambda device: asyncio.sleep(0))
    assert not conn.states
    assert f"SSRQ {SrqMask.DOING_STATE_CHANGE.value}" in conn.commands


def test_disconnect_ignores_lost_connection() -> None:
    """A lost connection while returning to local must not prevent disconnecting."""
    conn = FakeConnection()
    conn.fail_local = True

    run(conn, lambda device: asyncio.sleep(0))
    assert conn.calls[-1] == "disconnect"


def test_get_id() -> None:
    """get_id() must emulate *IDN? using the firmware version."""
    assert run(FakeConnection(), lambda device: device.get_id()) == ("Fluke", "5440B", "0", "1.08")


@pytest.mark.parametrize("cmd", ["GOUT", b"GOUT"])
def test_write_accepts_str_and_bytes(cmd: str | bytes) -> None:
    """Commands can be given as str or bytes."""
    conn = FakeConnection()
    assert run(conn, lambda device: device.query(cmd)) == "1.5"
    assert conn.written[-1] == b"GOUT"


def test_write_rejects_other_types() -> None:
    """Commands of other types must raise a TypeError."""
    with pytest.raises(TypeError):
        run(FakeConnection(), lambda device: device.write(42))  # type: ignore[arg-type]


def test_write_rejects_long_commands() -> None:
    """The input buffer of the instrument holds 127 bytes, longer commands must be rejected."""
    with pytest.raises(ValueError):
        run(FakeConnection(), lambda device: device.write("X" * 128))


def test_query_splits_multiple_results() -> None:
    """Multiple results are returned as a list."""
    assert run(FakeConnection(), lambda device: device.query("GVLM")) == ["1100", "-1100"]


def test_write_raises_device_error() -> None:
    """An error reported by the instrument must raise a DeviceError with the error code."""
    conn = FakeConnection()
    conn.error_on = {"FOO": ErrorCode.UNKNOWN_COMMAND.value}

    with pytest.raises(DeviceError) as exc_info:
        run(conn, lambda device: device.write("FOO", test_error=True))
    assert exc_info.value.code is ErrorCode.UNKNOWN_COMMAND


def test_query_error_drops_the_reply() -> None:
    """If a command fails, the reply in the output buffer must be read and included in the error."""
    conn = FakeConnection()
    conn.error_on = {"GOUT": ErrorCode.INVALID_COMMAND.value}

    with pytest.raises(DeviceError, match="Message returned: 1.5"):
        run(conn, lambda device: device.query("GOUT", test_error=True))


@pytest.mark.parametrize(
    "code, expected",
    [
        (ErrorCode.CAL_SWITCH_LOCKED.value, ErrorCode.CAL_SWITCH_LOCKED),
        (
            SelfTestErrorCode.ANALOG_MEASURE_FAULT_GAIN_SHIFT_TOO_LARGE.value,
            SelfTestErrorCode.ANALOG_MEASURE_FAULT_GAIN_SHIFT_TOO_LARGE,
        ),
        (999, 999),
    ],
)
def test_device_error_keeps_unknown_codes(code: int, expected: ErrorCode | SelfTestErrorCode | int) -> None:
    """Error codes missing from ErrorCode must not be lost."""
    conn = FakeConnection()
    conn.error_on = {"SOUT": code}

    with pytest.raises(DeviceError) as exc_info:
        run(conn, lambda device: device.set_output(1))
    assert exc_info.value.code == expected


@pytest.mark.parametrize(
    "value, command",
    [
        (0, "SOUT 0"),
        (10, "SOUT 10.000000"),
        (0.1, "SOUT 0.10000000"),
        (12.3456789, "SOUT 12.345679"),
        (-12.3456789, "SOUT -12.345679"),
        (9.99999999, "SOUT 10.000000"),
        (0.99999999999, "SOUT 1.0000000"),
        (Decimal("-1000.5"), "SOUT -1000.5000"),
    ],
)
def test_set_output_rounds_to_8_digits(value: int | float | Decimal, command: str) -> None:
    """set_output() must round to 8 significant digits, not truncate."""
    conn = FakeConnection()
    run(conn, lambda device: device.set_output(value))
    assert conn.commands[-1] == command


@pytest.mark.parametrize(
    "value, command",
    [
        (1e-9, "SOUT 0"),
        (-1e-9, "SOUT 0"),
        (5e-9, "SOUT 0"),  # Rounded half to even
        (6e-9, "SOUT 0.00000001"),
        (-6e-9, "SOUT -0.00000001"),
    ],
)
def test_set_output_below_resolution(value: float, command: str) -> None:
    """Values below the 10 nV resolution are rounded to zero and sent like an exact zero."""
    conn = FakeConnection()
    run(conn, lambda device: device.set_output(value))
    assert conn.commands[-1] == command


@pytest.mark.parametrize("value", [1500.1, -1500.1])
def test_set_output_range(value: float) -> None:
    """set_output() must reject values outside of +-1500 V."""
    with pytest.raises(ValueError):
        run(FakeConnection(), lambda device: device.set_output(value))


def test_set_output_outside_limits() -> None:
    """A value outside the limits set on the instrument must raise a ValueError."""
    conn = FakeConnection()
    conn.error_on = {"SOUT": ErrorCode.OUTPUT_OUTSIDE_LIMITS.value}

    with pytest.raises(ValueError):
        run(conn, lambda device: device.set_output(100))


def test_get_output() -> None:
    """get_output() must return the output as a Decimal."""
    assert run(FakeConnection(), lambda device: device.get_output()) == Decimal("1.5")


@pytest.mark.parametrize(
    "method, args, commands",
    [
        ("set_voltage_limit", (100,), ["SVLM 100.00000"]),
        ("set_voltage_limit", (100, -50), ["SVLM -50.000000", "SVLM 100.00000"]),
        ("set_current_limit", (0.01,), ["SCLM 0.01000000"]),
        ("set_current_limit", (0.01, -0.02), ["SCLM -0.02000000", "SCLM 0.01000000"]),
    ],
)
def test_set_limits(method: str, args: tuple[float, ...], commands: list[str]) -> None:
    """The limits must be sent as one command each, the second limit first."""
    conn = FakeConnection()
    run(conn, lambda device: getattr(device, method)(*args))
    assert conn.commands[-len(commands) :] == commands


@pytest.mark.parametrize(
    "method, args",
    [
        ("set_voltage_limit", (1501,)),
        ("set_voltage_limit", (100, -1501)),
        ("set_voltage_limit", (100, 50)),  # Both limits positive
        ("set_current_limit", (21,)),
        ("set_current_limit", (0.01, -21)),
        ("set_current_limit", (0.01, 0.02)),
    ],
)
def test_set_limits_invalid(method: str, args: tuple[float, ...]) -> None:
    """Limits out of range, or two limits of the same sign, must be rejected."""
    with pytest.raises(ValueError):
        run(FakeConnection(), lambda device: getattr(device, method)(*args))


@pytest.mark.parametrize("method, header", [("set_voltage_limit", "SVLM"), ("set_current_limit", "SCLM")])
def test_set_limits_rejected_by_instrument(method: str, header: str) -> None:
    """A limit rejected by the instrument must raise a ValueError."""
    conn = FakeConnection()
    conn.error_on = {header: ErrorCode.LIMIT_OUT_OF_RANGE.value}

    with pytest.raises(ValueError, match="Invalid .* limit"):
        run(conn, lambda device: getattr(device, method)(1))


@pytest.mark.parametrize(
    "method, header",
    [
        ("set_voltage_limit", "SVLM"),
        ("set_current_limit", "SCLM"),
        ("set_internal_sense", "ISNS"),
        ("set_internal_guard", "IGRD"),
    ],
)
def test_other_errors_are_passed_on(method: str, header: str) -> None:
    """Errors, that are not translated to a ValueError, must be raised as a DeviceError."""
    conn = FakeConnection()
    conn.error_on = {header: ErrorCode.INVALID_COMMAND.value}

    with pytest.raises(DeviceError) as exc_info:
        run(conn, lambda device: getattr(device, method)(1))
    assert exc_info.value.code is ErrorCode.INVALID_COMMAND


@pytest.mark.parametrize(
    "reply, expected",
    [
        ("1100,-1100", (Decimal("-1100"), Decimal("1100"))),
        ("1100", Decimal("1100")),
    ],
)
def test_get_limits(reply: str, expected: Decimal | tuple[Decimal, Decimal]) -> None:
    """The limits are returned as a tuple, or as a single value if the instrument returns only one."""
    conn = FakeConnection()
    conn.replies["GVLM"] = conn.replies["GCLM"] = reply

    assert run(conn, lambda device: device.get_voltage_limit()) == expected
    assert run(conn, lambda device: device.get_current_limit()) == expected


@pytest.mark.parametrize(
    "method, enabled, command",
    [
        ("set_output_enabled", True, "OPER"),
        ("set_output_enabled", False, "STBY"),
        ("set_internal_sense", True, "ISNS"),
        ("set_internal_sense", False, "ESNS"),
        ("set_internal_guard", True, "IGRD"),
        ("set_internal_guard", False, "EGRD"),
        ("set_divider", True, "DIVY"),
        ("set_divider", False, "DIVN"),
        ("set_enable_rs232", True, "MONY"),
        ("set_enable_rs232", False, "MONN"),
    ],
)
def test_switches(method: str, enabled: bool, command: str) -> None:
    """Each boolean setting must send the matching command."""
    conn = FakeConnection()
    run(conn, lambda device: getattr(device, method)(enabled))
    assert conn.commands[-1] == command


@pytest.mark.parametrize(
    "method, code",
    [
        ("set_internal_sense", ErrorCode.INVALID_SENSE_MODE),
        ("set_internal_guard", ErrorCode.INVALID_GUARD_MODE),
    ],
)
def test_invalid_terminal_mode(method: str, code: ErrorCode) -> None:
    """A sense or guard mode not allowed by the instrument must raise a ValueError."""
    conn = FakeConnection()
    conn.error_on = {"I": code.value}

    with pytest.raises(ValueError, match="mode not allowed"):
        run(conn, lambda device: getattr(device, method)(True))


@pytest.mark.parametrize("mode, command", [(ModeType.NORMAL, "BSTO"), (ModeType.VOLTAGE_BOOST, "BSTV")])
def test_set_mode(mode: ModeType, command: str) -> None:
    """set_mode() must send the command of the mode."""
    conn = FakeConnection()
    run(conn, lambda device: device.set_mode(mode))
    assert conn.commands[-1] == command


def test_get_status() -> None:
    """get_status() must decode the status flags."""
    status = run(FakeConnection(), lambda device: device.get_status())
    assert status == StatusFlags.VOLTAGE_MODE | StatusFlags.OUTPUT_ENABLED


def test_get_terminator_and_separator() -> None:
    """The terminator and separator set by connect() must be reported back."""
    conn = FakeConnection()
    assert run(conn, lambda device: device.get_terminator()) is TerminatorType.LF_EOI
    assert run(conn, lambda device: device.get_separator()).value == 0


def test_serial_poll_keeps_unknown_bits() -> None:
    """Undefined bits of the serial poll register must not raise an error."""
    conn = FakeConnection()

    async def scenario(device: Fluke_5440B) -> SerialPollFlags:
        conn.extra_status = 0b1000_0011  # Bits 0, 1 and 7 are not defined
        return await device.serial_poll()

    assert run(conn, scenario).value == 0b1000_0011


def test_srq_mask() -> None:
    """The SRQ mask must be read and written as a bit field, keeping undefined bits."""
    conn = FakeConnection()
    conn.replies["GSRQ"] = str(SrqMask.DOING_STATE_CHANGE.value | 0b1000_0000)

    assert run(conn, lambda device: device.get_srq_mask()).value == SrqMask.DOING_STATE_CHANGE.value | 0b1000_0000
    run(conn, lambda device: device.set_srq_mask(SrqMask.ERROR_CONDITION | SrqMask.MSG_RDY))
    assert conn.commands[-1] == "SSRQ 40"


def test_get_calibration_constants() -> None:
    """The 20 constants must be queried in two parts, that fit the input buffer, and mapped in order."""
    conn = FakeConnection()
    constants = run(conn, lambda device: device.get_calibration_constants())

    queries = [cmd for cmd in conn.commands if cmd.startswith("GCAL")]
    assert queries == [",".join(f"GCAL {i}" for i in range(10)), ",".join(f"GCAL {i}" for i in range(10, 20))]
    assert all(len(query) <= 127 for query in queries)  # The input buffer of the instrument
    assert isinstance(constants, CalibrationConstants)
    assert constants.gain_10V == 1  # GCAL 0
    assert constants.gain_2V == 5  # GCAL 4
    assert constants.gain_02V == 6  # GCAL 5
    assert constants.offset_10V_neg == 11  # GCAL 10
    assert constants.adc_gain == 20  # GCAL 19
    assert "ADC gain" in str(constants)


@pytest.mark.parametrize("baud_rate, index", [(50, 0), (134.5, 3), (9600, 12)])
def test_set_rs232_baud_rate(baud_rate: int | float, index: int) -> None:
    """The baud rate must be sent as an index and the driver must wait until it is written to the NVRAM."""
    conn = FakeConnection()
    # Writing to the NVRAM takes a while, so the driver waits for a state change
    run(conn, with_states(conn, [DeviceState.WRITING_TO_NVRAM, DeviceState.IDLE], "set_rs232_baud_rate", baud_rate))
    assert not conn.states
    assert f"SBDR {index}" in conn.commands
    assert conn.commands[-1] == "SSRQ 0"


def test_set_rs232_baud_rate_invalid() -> None:
    """Baud rates not supported by the instrument must be rejected."""
    with pytest.raises(ValueError):
        run(FakeConnection(), lambda device: device.set_rs232_baud_rate(115200))


def test_get_rs232_baud_rate() -> None:
    """The index returned by the instrument must be converted to the baud rate."""
    assert run(FakeConnection(), lambda device: device.get_rs232_baud_rate()) == 9600


def test_reset() -> None:
    """reset() must send a device clear, wait for the reset and configure the instrument again."""
    conn = FakeConnection()
    run(conn, with_states(conn, [DeviceState.RESETTING, DeviceState.IDLE], "reset"))
    assert not conn.state_change  # The driver waited for the state change of the device clear
    assert not conn.states
    assert "clear" in conn.calls
    assert conn.commands[-3:] == ["STRM 2", "SSEP 0", "SSRQ 0"]


@pytest.mark.parametrize(
    "method, command, states",
    [
        (
            "selftest_digital",
            "TSTD",
            [DeviceState.SELF_TEST_MAIN_CPU, DeviceState.SELF_TEST_FRONTPANEL_CPU, DeviceState.SELF_TEST_GUARD_CPU],
        ),
        ("selftest_analog", "TSTA", [DeviceState.CALIBRATING_ADC, DeviceState.SELF_TEST_LOW_VOLTAGE]),
        ("selftest_hv", "TSTH", [DeviceState.CALIBRATING_ADC, DeviceState.SELF_TEST_HIGH_VOLTAGE]),
        ("acal", "CALI", [DeviceState.CALIBRATING_ADC, DeviceState.ZEROING_10V_POS, DeviceState.WRITING_TO_NVRAM]),
    ],
)
def test_long_jobs(method: str, command: str, states: list[DeviceState]) -> None:
    """Self-tests and ACAL must follow the state changes until the instrument is idle again."""
    conn = FakeConnection()
    # The first state is read before starting the job, then once after each state change
    run(conn, with_states(conn, [DeviceState.IDLE, *states, DeviceState.IDLE], method))
    assert command in conn.commands
    assert not conn.states
    assert conn.commands[-1] == "SSRQ 0"  # SRQs are disabled again


@pytest.mark.parametrize("method", ["selftest_digital", "selftest_analog", "selftest_hv", "acal"])
def test_long_job_reports_unexpected_state(method: str, caplog: pytest.LogCaptureFixture) -> None:
    """An unexpected state during a self-test or ACAL must be logged."""
    conn = FakeConnection()

    with caplog.at_level(logging.WARNING):
        run(conn, with_states(conn, [DeviceState.IDLE, DeviceState.PRINTING, DeviceState.IDLE], method))
    assert "Invalid state: DeviceState.PRINTING" in caplog.text
    assert not conn.states


@pytest.mark.parametrize("method", ["selftest_digital", "selftest_analog", "selftest_hv", "acal"])
def test_long_job_survives_wait_timeout(method: str, caplog: pytest.LogCaptureFixture) -> None:
    """A wait, that times out, must be logged and the driver must keep waiting for the job to finish."""
    conn = FakeConnection()

    async def scenario(device: Fluke_5440B) -> None:
        conn.wait_timeouts = 1
        await with_states(conn, [DeviceState.IDLE, DeviceState.CALIBRATING_ADC, DeviceState.IDLE], method)(device)

    with caplog.at_level(logging.WARNING):
        run(conn, scenario)
    assert "Timeout during wait" in caplog.text
    assert not conn.states  # The job was followed until the instrument was idle again


def test_selftest_all() -> None:
    """selftest_all() must run the digital, the analog and the high voltage self-test."""
    conn = FakeConnection()
    run(conn, lambda device: device.selftest_all())
    assert [cmd for cmd in conn.commands if cmd.startswith("TST")] == ["TSTD", "TSTA", "TSTH"]


@pytest.mark.parametrize("method", ["selftest_digital", "selftest_analog", "selftest_hv"])
def test_selftest_failure(method: str) -> None:
    """A failed self-test must raise a SelftestError and disable the SRQs again."""
    conn = FakeConnection()
    conn.error_during_wait = SelfTestErrorCode.DAC_ANALOG_FAULT_CHECK_REFERENCE.value

    with pytest.raises(SelftestError) as exc_info:
        run(conn, lambda device: getattr(device, method)())
    assert exc_info.value.code is SelfTestErrorCode.DAC_ANALOG_FAULT_CHECK_REFERENCE
    assert conn.commands[-1] == "SSRQ 0"  # SRQs are disabled again


def test_acal_failure() -> None:
    """A fault during ACAL must raise a DeviceError with the fault code."""
    conn = FakeConnection()
    conn.error_during_wait = SelfTestErrorCode.ANALOG_MEASURE_FAULT_UNABLE_TO_ZERO_RANGE.value

    with pytest.raises(DeviceError) as exc_info:
        run(conn, lambda device: device.acal())
    assert exc_info.value.code is SelfTestErrorCode.ANALOG_MEASURE_FAULT_UNABLE_TO_ZERO_RANGE


def test_wait_ignores_prologix_handshake_errors() -> None:
    """GPIB handshake errors caused by the polling of Prologix adapters must be ignored."""
    conn = FakeConnection()
    conn.error_during_wait = ErrorCode.GPIB_HANDSHAKE_ERROR.value

    run(conn, with_states(conn, [DeviceState.IDLE, DeviceState.CALIBRATING_ADC, DeviceState.IDLE], "acal"))
    assert not conn.states


def test_set_log_level() -> None:
    """set_log_level() must change the level of the library logger."""

    async def scenario(device: Fluke_5440B) -> None:
        device.set_log_level(logging.DEBUG)

    run(FakeConnection(), scenario)
    assert logging.getLogger("fluke5440b_async.fluke_5440b").level == logging.DEBUG


@pytest.mark.parametrize(
    "method, header",
    [
        ("get_status", "GSTS"),
        ("get_state", "GDNG"),
        ("get_error", "GERR"),
        ("get_terminator", "GTRM"),
        ("get_separator", "GSEP"),
        ("get_srq_mask", "GSRQ"),
        ("get_rs232_baud_rate", "GBDR"),
    ],
)
@pytest.mark.parametrize("reply", ["junk", "1,2"])
def test_invalid_integer_reply(method: str, header: str, reply: str) -> None:
    """A reply that is not a single integer must raise a ValueError naming the reply."""
    conn = FakeConnection()

    async def scenario(device: Fluke_5440B) -> Any:
        conn.overrides[header] = reply
        return await getattr(device, method)()

    with pytest.raises(ValueError, match="Invalid reply received"):
        run(conn, scenario)


def test_concurrent_queries() -> None:
    """Queries from concurrent tasks must not read the replies of each other."""
    conn = FakeConnection()

    async def scenario(device: Fluke_5440B) -> list[Any]:
        # A query without the error check takes fewer steps, so without a lock its read would overtake the others
        return await asyncio.gather(*(coro for _ in range(5) for coro in (device.get_id(), device.query("GOUT"))))

    results = run(conn, scenario)
    assert results == [("Fluke", "5440B", "0", "1.08"), "1.5"] * 5


def test_concurrent_errors() -> None:
    """An error must be reported to the task that sent the failing command, not to a concurrent task."""
    conn = FakeConnection()
    conn.error_on = {"FOO": ErrorCode.UNKNOWN_COMMAND.value}

    async def scenario(device: Fluke_5440B) -> tuple[None | BaseException, Decimal | BaseException]:
        return await asyncio.gather(device.write("FOO", test_error=True), device.get_output(), return_exceptions=True)

    failing, output = run(conn, scenario)
    assert isinstance(failing, DeviceError) and failing.code is ErrorCode.UNKNOWN_COMMAND
    assert output == Decimal("1.5")


@pytest.mark.parametrize("reply", ["13", "-1"])
def test_get_rs232_baud_rate_invalid_reply(reply: str) -> None:
    """An index outside the table of baud rates must raise a ValueError instead of returning a wrong rate."""
    conn = FakeConnection()
    conn.replies["GBDR"] = reply

    with pytest.raises(ValueError, match="baud rate index"):
        run(conn, lambda device: device.get_rs232_baud_rate())


def test_set_rs232_baud_rate_logs_fractional_rate(caplog: pytest.LogCaptureFixture) -> None:
    """134.5 baud must not be logged as 134."""
    conn = FakeConnection()

    async def scenario(device: Fluke_5440B) -> None:
        device.set_log_level(logging.INFO)
        await device.set_rs232_baud_rate(134.5)

    with caplog.at_level(logging.INFO, logger="fluke5440b_async.fluke_5440b"):
        run(conn, scenario)
    assert "Setting baud rate to 134.5 " in caplog.text
