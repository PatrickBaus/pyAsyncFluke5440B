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
from pyAsyncGpib.pyAsyncGpib.AsyncGpib import AsyncGpib

fluke5440b = Fluke_5440B(connection=AsyncGpib(name=0, pad=7))

# This example will log resistance data to the console
async def main():
    try:
        # No need to explicitely bring up the GPIB connection. This will be done by the Fluke 5440B.
        await fluke5440b.connect()

        # First run the selftest
        print("Running selftest, then autocalibration.")
        await fluke5440b.selftest_all()
        print("Selftest done.")
        cal_constants = await fluke5440b.get_calibration_constants()
        print(("Calibration constants before running autocalibration:\n"
               f"Gain 0.2 V      : {cal_constants['gain_0.2V']}\n"
               f"Gain 2 V        : {cal_constants['gain_2V']}\n"
               f"Gain 10 V       : {cal_constants['gain_10V']}\n"
               f"Shift 10 V      : {cal_constants['gain_shift_10V']}\n"
               f"Gain 20 V       : {cal_constants['gain_20V']}\n"
               f"Shift 20 V      : {cal_constants['gain_shift_20V']}\n"
               f"Gain 250 V      : {cal_constants['gain_250V']}\n"
               f"Shift 250 V     : {cal_constants['gain_shift_250V']}\n"
               f"Gain 1000 V     : {cal_constants['gain_1000V']}\n"
               f"Shift 1000 V    : {cal_constants['gain_shift_1000V']}\n"
               f"Offset +10 V    : {cal_constants['offset_10V_pos']}\n"
               f"Offset -10 V    : {cal_constants['offset_10V_neg']}\n"
               f"Offset +20 V    : {cal_constants['offset_20V_pos']}\n"
               f"Offset -20 V    : {cal_constants['offset_20V_neg']}\n"
               f"Offset +250 V   : {cal_constants['offset_250V_pos']}\n"
               f"Offset -250 V   : {cal_constants['offset_250V_neg']}\n"
               f"Offset +1000 V  : {cal_constants['offset_10V_pos']}\n"
               f"Offset -1000 V  : {cal_constants['offset_10V_neg']}\n"
               f"Resolution ratio: {cal_constants['resolution_ratio']}\n"
               f"ADC gain        : {cal_constants['a/d_gain']}")
        )
        await fluke5440b.acal()
        cal_constants = await fluke5440b.get_calibration_constants()
        print(("Calibration constants after running autocalibration:\n"
               f"Gain 0.2 V      : {cal_constants['gain_0.2V']}\n"
               f"Gain 2 V        : {cal_constants['gain_2V']}\n"
               f"Gain 10 V       : {cal_constants['gain_10V']}\n"
               f"Shift 10 V      : {cal_constants['gain_shift_10V']}\n"
               f"Gain 20 V       : {cal_constants['gain_20V']}\n"
               f"Shift 20 V      : {cal_constants['gain_shift_20V']}\n"
               f"Gain 250 V      : {cal_constants['gain_250V']}\n"
               f"Shift 250 V     : {cal_constants['gain_shift_250V']}\n"
               f"Gain 1000 V     : {cal_constants['gain_1000V']}\n"
               f"Shift 1000 V    : {cal_constants['gain_shift_1000V']}\n"
               f"Offset +10 V    : {cal_constants['offset_10V_pos']}\n"
               f"Offset -10 V    : {cal_constants['offset_10V_neg']}\n"
               f"Offset +20 V    : {cal_constants['offset_20V_pos']}\n"
               f"Offset -20 V    : {cal_constants['offset_20V_neg']}\n"
               f"Offset +250 V   : {cal_constants['offset_250V_pos']}\n"
               f"Offset -250 V   : {cal_constants['offset_250V_neg']}\n"
               f"Offset +1000 V  : {cal_constants['offset_10V_pos']}\n"
               f"Offset -1000 V  : {cal_constants['offset_10V_neg']}\n"
               f"Resolution ratio: {cal_constants['resolution_ratio']}\n"
               f"ADC gain        : {cal_constants['a/d_gain']}")
        )
    finally:
        # Disconnect from the HP 3478A. We may safely call diconnect() on a non-connected device, even
        # in case of a connection error
        await fluke5440b.disconnect()

# Report all mistakes managing asynchronous resources.
warnings.simplefilter('always', ResourceWarning)
logging.basicConfig(
    format='%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s',
    level=logging.WARNING,    # Enable logs from the ip connection. Set to debug for even more info
    datefmt='%Y-%m-%d %H:%M:%S'
)

try:
    asyncio.run(main(), debug=False)
except KeyboardInterrupt:
    # The loop will be canceled on a KeyboardInterrupt by the run() method, we just want to suppress the exception
    pass

