#!/usr/bin/env python3
# pylint: disable=duplicate-code
# ##### BEGIN GPL LICENSE BLOCK #####
#
# Copyright (C) 2023  Patrick Baus
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# ##### END GPL LICENSE BLOCK #####
"""This example is used to test the majority of instrument functions"""

import asyncio
import logging
import sys
import warnings
from decimal import Decimal
from math import isclose
from typing import TYPE_CHECKING, cast

# Devices
from fluke5440b_async import Fluke_5440B

if TYPE_CHECKING:
    from async_gpib import AsyncGpib
    from prologix_gpib_async import AsyncPrologixGpibEthernetController
else:
    # Uncomment if using a Prologix GPIB Ethernet adapter
    from prologix_gpib_async import AsyncPrologixGpibEthernetController

    # Uncomment if using linux-gpib
    # from async_gpib import AsyncGpib

if "prologix_gpib_async" in sys.modules:
    IP_ADDRESS = "127.0.0.1"
    # Set the timeout to 300 seconds, State.SELF_TEST_LOW_VOLTAGE takes a little more than 3 minutes.
    # pylint: disable=used-before-assignment  # false positive
    gpib_device = AsyncPrologixGpibEthernetController(
        IP_ADDRESS, pad=7, timeout=300, wait_delay=0.25
    )  # Prologix GPIB Adapter
elif "async_gpib" in sys.modules:
    # Set the timeout to 300 seconds, State.SELF_TEST_LOW_VOLTAGE takes a little more than 3 minutes.
    gpib_device = AsyncGpib(name=0, pad=7, timeout=300)  # NI GPIB adapter, pylint: disable=used-before-assignment
    from gpib_ctypes.Gpib import Gpib

    gpib_board = Gpib(name=0)
    gpib_board.config(0x7, True)  # enable wait for SRQs to speed up waiting for state changes
    gpib_board.close()
else:
    raise ModuleNotFoundError("No GPIB library loaded.")


async def test_getters(device: Fluke_5440B):
    """
    Test the instrument getter functions.
    Parameters
    ----------
    device: Fluke_5440B
        A connected instrument.

    Raises
    ------
    DeviceError
        If test_error is set to True and there was an error processing the command.
    """
    print("ID             :", await device.get_id())
    print("Terminator     :", await device.get_terminator())
    print("Separator      :", await device.get_separator())
    print("Output         :", await device.get_output())
    print("Voltage limit  :", await device.get_voltage_limit())
    print("Current limit  :", await device.get_current_limit())
    print("RS232 baud rate:", await device.get_rs232_baud_rate())
    print("SRQ mask       :", await device.get_srq_mask())
    print("Calibration constants:", await device.get_calibration_constants())  # needs a lock, when running


async def test_setters(device: Fluke_5440B):
    """
    Test the instrument setter functions.
    Parameters
    ----------
    device: Fluke_5440B
        A connected instrument.

    Raises
    ------
    DeviceError
        If test_error is set to True and there was an error processing the command.
    ValueError
        Raised if the limits are out of bounds.
    """
    # voltage limit
    output_limit = (-10.0, 10.0)
    await device.set_voltage_limit(*output_limit)
    assert output_limit == await device.get_voltage_limit()
    output_limit = (-1100.0, 1100.0)
    await device.set_voltage_limit(*output_limit)
    assert output_limit == await device.get_voltage_limit()

    # current limit
    current_limit = 35 / 1000
    await device.set_current_limit(current_limit)
    assert isclose(abs(current_limit), cast(Decimal, await device.get_current_limit()))
    current_limit = 65 / 1000
    await device.set_current_limit(current_limit)
    assert isclose(abs(current_limit), cast(Decimal, await device.get_current_limit()))

    # baud rate
    baud_rate = 4800
    await device.set_rs232_baud_rate(baud_rate)
    assert baud_rate == await device.get_rs232_baud_rate()
    baud_rate = 9600
    await device.set_rs232_baud_rate(baud_rate)
    assert baud_rate == await device.get_rs232_baud_rate()


async def main():
    """Run the example and test all getters first, then test the setters."""
    # No need to explicitly bring up the GPIB connection. This will be done by the instrument.
    async with Fluke_5440B(connection=gpib_device, log_level=logging.DEBUG) as fluke5440b:
        await test_getters(fluke5440b)
        await test_setters(fluke5440b)


# Report all mistakes managing asynchronous resources.
warnings.simplefilter("always", ResourceWarning)
logging.basicConfig(
    format="%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s",
    level=logging.INFO,  # Enable logs from the ip connection. Set to debug for even more info
    datefmt="%Y-%m-%d %H:%M:%S",
)

try:
    asyncio.run(main(), debug=True)
except KeyboardInterrupt:
    # The loop will be canceled on a KeyboardInterrupt by the run() method, we just want to suppress the exception
    pass
