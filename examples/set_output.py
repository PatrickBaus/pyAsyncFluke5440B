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
import warnings
import sys

sys.path.append("..") # Adds main directory to python modules path.

# Devices
from pyAsyncFluke5440B.Fluke_5440B import Fluke_5440B
from pyAsyncGpib.pyAsyncGpib.AsyncGpib import AsyncGpib

# Set the timeout to 100 seconds (T100s=15)
fluke5440b = Fluke_5440B(connection=AsyncGpib(name=0, pad=7, timeout=15))
gpib_board = Gpib(name=0)
gpib_board.config(0x7, True)   # enable wait for SRQs to speed up waiting for state changes
gpib_board.close()

# This example will log resistance data to the console
async def main():
    try:
        # No need to explicitely bring up the GPIB connection. This will be done by the Fluke 5440B.
        await fluke5440b.connect()

        await fluke5440b.set_output(10.0)
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

asyncio.run(main(), debug=False)

