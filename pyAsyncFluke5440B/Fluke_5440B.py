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

class SeparatorType(Enum):
    COMMA = 0
    COLON = 1

class TerminatorType(Enum):
    EOI       = 0
    CR_LF_EOI = 1
    LF_EOI    = 2
    CR_LF     = 3
    LF        = 4

class ModeType(Enum):
    NORMAL = "BSTO"
    VOLTAGE_BOOST = "BSTV"
    CURRENT_BOOST = "BSTC"

class SrqMask(Flag):
    NONE                = 0b0
    DOING_STATE_CHANGE  = 0b100
    MSG_RDY             = 0b1000
    OUTPUT_SETTLED      = 0b10000
    ERROR_CONDITION     = 0b100000

class SerialPollFlags(Flag):
    NONE                  = 0b0
    SRQ_ON_STATE_CHANGE   = 0b100
    SRQ_ON_MSG_RDY        = 0b1000
    SRQ_ON_OUTPUT_SETTLED = 0b10000
    SRQ_ON_ERROR          = 0b100000
    SRQ                   = 0b1000000

class StatusFlags(Flag):
    VOLTAGE_MODE           = 0b1
    CURRENT_BOOST_MODE     = 0b10
    VOLTAGE_BOOST_MODE     = 0b100
    DIVIDER_ENABLED        = 0b1000
    INTERNAL_SENSE_ENABLED = 0b10000
    OUTPUT_ENABLED         = 0b100000
    INTERNAL_GUARD_ENABLED = 0b1000000
    REAR_OUTPUT_ENABLED    = 0b10000000

BAUD_RATES_AVAILABLE = (50, 75, 110, 134.5, 150, 200, 300, 600, 1200, 1800, 2400, 4800, 9600)

class Fluke_5440B:
    @property
    def connection(self):
        return self.__conn

    def __init__(self, connection):
        self.__conn = connection

    async def get_id(self):
        version = (await self._get_software_version()).strip()
        return "Fluke 5440B, software version {version}".format(version=version)

    async def connect(self):
        await self.__conn.connect()
        if hasattr(self.__conn, "set_eot"):
            # Used by the Prologix adapters
            await self.__conn.set_eot(False)
        await asyncio.gather(
            self.__set_terminator(TerminatorType.LF_EOI),   # terminate lines with \n
            self.__set_separator(SeparatorType.COMMA),      # use a comma as the separator
        )

    async def disconnect(self):
        await self.__conn.disconnect()

    async def write(self, cmd):
        assert isinstance(cmd, str) or isinstance(cmd, bytes)
        try:
            cmd = cmd.encode("ascii")
        except AttributeError:
            pass    # cmd is already a bytestring
        await self.__conn.write(cmd)

    async def read(self):
        return (await self.__conn.read())[:-1].decode("utf-8")  # strip \n

    async def query(self, cmd):
        await self.write(cmd)
        return await self.read()

    async def reset(self):
        await self.__write("RESET")

    async def get_terminator(self):
        return TerminatorType(int(await self.query("GTRM")))

    async def __set_terminator(self, value):
        assert isinstance(value, TerminatorType)
        await self.write("STRM {value:d}".format(value=value.value))

    async def get_separator(self):
        return SeparatorType(int(await self.query("GSEP")))

    async def __set_separator(self, value):
        assert isinstance(value, SeparatorType)
        await self.write("SSEP {value:d}".format(value=value.value))

    async def set_mode(self, value):
        assert isinstance(value, ModeType)
        await self.write("{value}".format(value=value.value))

    async def set_output_enabled(self, enabled):
        await self.write("OPER" if enabled else "STBY")

    async def set_internal_sense(self, enabled):
        await self.write("ISNS" if enabled else "ESNS")

    async def set_internal_guard(self, enabled):
        await self.write("IGRD" if enabled else "EGRD")

    async def get_voltage_limit(self):
        # TODO catch error when in current boost mode
        return Decimal(await self.query("GVLM"))

    async def set_voltage_limit(self, value):
        assert (-1100. <= value <= 1100.)
        pass

    async def get_current_limit(self):
        # TODO catch error when in voltage boost mode
        return Decimal(await self.query("GCLM"))

    async def set_current_limit(self, value):
        pass

    async def _get_software_version(self):
        return await self.query("GVRS")

    async def get_status(self):
        return StatusFlags(await self.query("GSTS"))

    async def get_baud_rate(self):
        return BAUD_RATES_AVAILABLE[int(await self.query("GBDR"))]

    async def set_baud_rate(self, value):
        assert (value in BAUD_RATES_AVAILABLE)
        await self.write("SBDR {value:d}".format(value=value))

    async def set_enable_rs232(self, enabled):
        await self.write("MONY" if enabled else "MONN")
