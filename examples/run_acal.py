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
        logger = logging.getLogger(__name__)
        # No need to explicitely bring up the GPIB connection. This will be done by the Fluke 5440B.
        await fluke5440b.connect()

        # First run the selftest
        logger.info("Running selftest, then autocalibration.")
        await fluke5440b.selftest_all()
        cal_constants = fluke5440b.get_calibration_constants()
        logger.info(f"Calibration constants before running autocalibration:\nGain 0.2 V: {cal_constants[' 'gain_0.2V"]}")
    finally:
        # Disconnect from the HP 3478A. We may safely call diconnect() on a non-connected device, even
        # in case of a connection error
        await fluke5440b.disconnect()

# Report all mistakes managing asynchronous resources.
warnings.simplefilter('always', ResourceWarning)

try:
    asyncio.run(main(), debug=False)
except KeyboardInterrupt:
    # The loop will be canceled on a KeyboardInterrupt by the run() method, we just want to suppress the exception
    pass

