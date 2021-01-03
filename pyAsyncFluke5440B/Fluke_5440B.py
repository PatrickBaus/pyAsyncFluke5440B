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

class Fluke_5440B:
    @property
    def connection(self):
        return self.__conn

    def __init__(self, connection):
        self.__conn = connection

    async def get_id(self):
        version = await self._get_software_version()
        return "Fluke 5440B {version}".format(version=version)

    async def connect(self):
        await self.__conn.connect()
        if hasattr(self.__conn, "set_eot"):
            # Used by the Prologix adapters
            await self.__conn.set_eot(False)
        await self.set_terminator(TerminatorType.LF_EOI)    # terminate lines with \n

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

    async def set_terminator(self, value):
        assert isinstance(value, TerminatorType)
        await self.write("STRM {value:d}".format(value=value.value))

    async def get_separator(self):
        return SeparatorType(int(await self.query("GSEP")))

    async def set_separator(self, value):
        assert isinstance(value, SeparatorType)
        await self.write("SSEP {value:d}".format(value=value.value))

    async def set_mode(self, value):
        assert isinstance(value, ModeType)
        await self.write("{value}".format(value=value.value))

    async def set_output_enabled(self, enabled):
        if enabled:
            await self.write("OPER")
        else:
            await self.write("STBY")

    async def set_external_sense(self, enabled):
        if enabled:
            await self.write("ESNS")
        else:
            await self.write("ISNS")

    async def set_guard(self, enabled):
        if enabled:
            await self.write("EGRD")
        else:
            await self.write("IGRD")

    async def get_voltage_limit(self):
        return await self.query("GVLM")

    async def set_voltage_limit(self, value):
        assert (-1100. <= value <= 1100.)
        pass

    async def get_current_limit(self):
        return await self.query("GCLM")

    async def set_current_limit(self, value):
        pass

    async def _get_software_version(self):
        return await self.query("GVRS")
