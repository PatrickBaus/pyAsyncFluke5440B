#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ##### BEGIN GPL LICENSE BLOCK #####
#
# Copyright (C) 2021  Patrick Baus
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

import asyncio
import logging
import warnings
import sys

from math import isclose

sys.path.append("..") # Adds main directory to python modules path.

# Devices
from pyAsyncFluke5440B.Fluke_5440B import Fluke_5440B, SrqMask, SerialPollFlags, ModeType

# Uncomment if using a Prologix GPIB Ethernet adapter
from pyAsyncPrologixGpib.pyAsyncPrologixGpib.pyAsyncPrologixGpib import AsyncPrologixGpibEthernetController
if 'pyAsyncPrologixGpib.pyAsyncPrologixGpib.pyAsyncPrologixGpib' in sys.modules:
    ip_address = '127.0.0.1'
    # Set the timeout to 300 seconds, State.SELF_TEST_LOW_VOLTAGE takes a little more than 3 minutes.
    gpib_device = AsyncPrologixGpibEthernetController('127.0.0.1', pad=7, timeout=300*1000, wait_delay=250)   # Prologix GPIB Adapter

# Uncomment if using linux-gpib
#from pyAsyncGpib.pyAsyncGpib.AsyncGpib import AsyncGpib
if 'pyAsyncGpib.pyAsyncGpib.AsyncGpib' in sys.modules:
    # Set the timeout to 300 seconds (T300s=16), State.SELF_TEST_LOW_VOLTAGE takes a little more than 3 minutes.
    gpib_device = AsyncGpib(name=0, pad=7, timeout=16)    # NI GPIB adapter
    from Gpib import Gpib
    gpib_board = Gpib(name=0)
    gpib_board.config(0x7, True)   # enable wait for SRQs to speed up waiting for state changes
    gpib_board.close()

fluke5440b = Fluke_5440B(connection=gpib_device)

async def test_getters():
    print('ID             :', await fluke5440b.get_id())
    print('Terminator     :', await fluke5440b.get_terminator())
    print('Separator      :', await fluke5440b.get_separator())
    print('Output         :', await fluke5440b.get_output())
    print('Voltage limit  :', await fluke5440b.get_voltage_limit())
    print('Current limit  :', await fluke5440b.get_current_limit())
    print('RS232 baud rate:', await fluke5440b.get_rs232_baud_rate())
    print('SRQ mask       :', await fluke5440b.get_srq_mask())
    print('Calibration constants:', await fluke5440b.get_calibration_constants())  # needs a lock, when running

async def test_setters():
    # voltage limit
    output_limit = (-10., 10.)
    await fluke5440b.set_voltage_limit(*output_limit)
    assert(output_limit == await fluke5440b.get_voltage_limit())
    output_limit = (-1100., 1100.)
    await fluke5440b.set_voltage_limit(*output_limit)
    assert(output_limit == await fluke5440b.get_voltage_limit())

    # current limit
    output_limit = 35/1000
    await fluke5440b.set_current_limit(output_limit)
    assert(isclose(abs(output_limit), await fluke5440b.get_current_limit()))
    output_limit = 65/1000
    await fluke5440b.set_current_limit(output_limit)
    assert(isclose(abs(output_limit), await fluke5440b.get_current_limit()))

    # baud rate
    baud_rate = 4800
    await fluke5440b.set_rs232_baud_rate(baud_rate)
    assert(baud_rate == await fluke5440b.get_rs232_baud_rate())
    baud_rate = 9600
    await fluke5440b.set_rs232_baud_rate(baud_rate)
    assert(baud_rate == await fluke5440b.get_rs232_baud_rate())

# This example will test most function of the calibrator
async def main():
    try:
        # No need to explicitly bring up the GPIB connection. This will be done by the instrument.
        await fluke5440b.connect()
        await test_getters()
        await test_setters()
    finally:
        # Disconnect from the instrument. We may safely call disconnect() on a non-connected device, even
        # in case of a connection error
        await fluke5440b.disconnect()

# Report all mistakes managing asynchronous resources.
warnings.simplefilter('always', ResourceWarning)
logging.basicConfig(
    format='%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s',
    level=logging.INFO,    # Enable logs from the ip connection. Set to debug for even more info
    datefmt='%Y-%m-%d %H:%M:%S'
)

try:
    asyncio.run(main(), debug=True)
except KeyboardInterrupt:
    # The loop will be canceled on a KeyboardInterrupt by the run() method, we just want to suppress the exception
    pass

