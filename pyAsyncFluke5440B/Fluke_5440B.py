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

class TerminatorType(Enum):
    EOI       = 0
    CR_LF_EOI = 1
    LF_EOI    = 2
    CR_LF     = 3
    LF        = 4

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

class Fluke_5440b:
    @property
    def connection(self):
        return self.__conn

    def __init__(self, connection):
        self.__conn = connection

    async def get_id(self):
        return "Fluke 5440B"

    async def connect(self):
        await self.__conn.connect()
        if hasattr(self.__gpib, "set_eot"):
            # Used by the Prologix adapters
            await self.__gpib.set_eot(False)
        await self.set_terminator(TerminatorType.LF_EOI)    # terminate lines with \n

    async def disconnect(self):
        await self.__conn.disconnect()

    async def write(self, cmd):
        await self.__conn.write(cmd)

    async def read(self):
        return (await self.__conn.read())[:-1].decode("utf-8")  # strip \n

    async def query(self, cmd):
        await self.write(cmd)
        return await self.read()

    async def get_terminator(self):
        return TerminatorType(await self.query("GSEP"))

    async def set_terminator(self, value):
        assert isinstance(value, TerminatorType)
        await self.write("STRM{value:d}".format(value=value.value).encode('ascii'))
