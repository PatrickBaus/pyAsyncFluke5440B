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
"""This is a simple example that uses the Prologix Ethernet adapter to set the output voltage of the calibrator."""

import asyncio

from prologix_gpib_async import AsyncPrologixGpibEthernetController

from fluke5440b_async import Fluke_5440B

IP_ADDRESS = "127.0.0.1"


async def main():
    """Set the output voltage and enable the outputs."""
    # No need to explicitly bring up the GPIB connection. This will be done by the instrument.
    async with Fluke_5440B(
        connection=AsyncPrologixGpibEthernetController(IP_ADDRESS, pad=7, timeout=300, wait_delay=0.25)
    ) as fluke5440b:
        await fluke5440b.set_output(10.0)
        # Enable the output binding posts
        # await fluke5440b.set_output_enabled(True)    # Use with caution at high voltages. Check cabling first.


asyncio.run(main(), debug=False)
