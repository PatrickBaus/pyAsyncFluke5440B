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

sys.path.append("..") # Adds main directory to python modules path.

# Devices
from pyAsyncFluke5440B.Fluke_5440B import Fluke_5440B

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

# This example will run the internal calibration routine of the calibrator
async def main():
    try:
        # No need to explicitly bring up the GPIB connection. This will be done by the instrument.
        await fluke5440b.connect()

        # First run the selftest
        print("Running selftest, then autocalibration.")
        #await fluke5440b.selftest_all()
        print("Selftest done.")
        cal_constants = await fluke5440b.get_calibration_constants()
        print(("Calibration constants before running autocalibration:\n"
               f"Gain 0.2 V      : {cal_constants['gain_0.2V']*1000:.8f} mV\n"
               f"Gain 2 V        : {cal_constants['gain_2V']*1000:.8f} mV\n"
               f"Gain 10 V       : {cal_constants['gain_10V']*1000:.8f} mV\n"
               f"Shift 10 V      : {cal_constants['gain_shift_10V']} ppm\n"
               f"Gain 20 V       : {cal_constants['gain_20V']*1000:.8f} mV\n"
               f"Shift 20 V      : {cal_constants['gain_shift_20V']} ppm\n"
               f"Gain 250 V      : {cal_constants['gain_250V']*1000:.8f} mV\n"
               f"Shift 250 V     : {cal_constants['gain_shift_250V']} ppm\n"
               f"Gain 1000 V     : {cal_constants['gain_1000V']*1000:.8f} mV\n"
               f"Shift 1000 V    : {cal_constants['gain_shift_1000V']} ppm\n"
               f"Offset +10 V    : {cal_constants['offset_10V_pos']*1000:.8f} mV\n"
               f"Offset -10 V    : {cal_constants['offset_10V_neg']*1000:.8f} mV\n"
               f"Offset +20 V    : {cal_constants['offset_20V_pos']*1000:.8f} mV\n"
               f"Offset -20 V    : {cal_constants['offset_20V_neg']*1000:.8f} mV\n"
               f"Offset +250 V   : {cal_constants['offset_250V_pos']*1000:.8f} mV\n"
               f"Offset -250 V   : {cal_constants['offset_250V_neg']*1000:.8f} mV\n"
               f"Offset +1000 V  : {cal_constants['offset_10V_pos']*100000:.8f} mV\n"
               f"Offset -1000 V  : {cal_constants['offset_10V_neg']*100000:.8f} mV\n"
               f"Resolution ratio: {cal_constants['resolution_ratio']}\n"
               f"ADC gain        : {cal_constants['adc_gain']*1000:.8f} mV")
        )
        #await fluke5440b.acal()
        cal_constants = await fluke5440b.get_calibration_constants()
        print(("Calibration constants after running autocalibration:\n"
               f"Gain 0.2 V      : {cal_constants['gain_0.2V']*1000:.8f} mV\n"
               f"Gain 2 V        : {cal_constants['gain_2V']*1000:.8f} mV\n"
               f"Gain 10 V       : {cal_constants['gain_10V']*1000:.8f} mV\n"
               f"Shift 10 V      : {cal_constants['gain_shift_10V']} ppm\n"
               f"Gain 20 V       : {cal_constants['gain_20V']*1000:.8f} mV\n"
               f"Shift 20 V      : {cal_constants['gain_shift_20V']} ppm\n"
               f"Gain 250 V      : {cal_constants['gain_250V']*1000:.8f} mV\n"
               f"Shift 250 V     : {cal_constants['gain_shift_250V']} ppm\n"
               f"Gain 1000 V     : {cal_constants['gain_1000V']*1000:.8f} mV\n"
               f"Shift 1000 V    : {cal_constants['gain_shift_1000V']} ppm\n"
               f"Offset +10 V    : {cal_constants['offset_10V_pos']*1000:.8f} mV\n"
               f"Offset -10 V    : {cal_constants['offset_10V_neg']*1000:.8f} mV\n"
               f"Offset +20 V    : {cal_constants['offset_20V_pos']*1000:.8f} mV\n"
               f"Offset -20 V    : {cal_constants['offset_20V_neg']*1000:.8f} mV\n"
               f"Offset +250 V   : {cal_constants['offset_250V_pos']*1000:.8f} mV\n"
               f"Offset -250 V   : {cal_constants['offset_250V_neg']*1000:.8f} mV\n"
               f"Offset +1000 V  : {cal_constants['offset_10V_pos']*100000:.8f} mV\n"
               f"Offset -1000 V  : {cal_constants['offset_10V_neg']*100000:.8f} mV\n"
               f"Resolution ratio: {cal_constants['resolution_ratio']}\n"
               f"ADC gain        : {cal_constants['adc_gain']*1000:.8f} mV")
        )
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
    asyncio.run(main(), debug=False)
except KeyboardInterrupt:
    # The loop will be canceled on a KeyboardInterrupt by the run() method, we just want to suppress the exception
    pass

