# Copyright (C) 2025 Leiden University Medical Center
# This file is part of nfs-usage-utils
#
# nfs-usage-utils is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# nfs-usage-utils is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with nfs-usage-utils.  If not, see <https://www.gnu.org/licenses/

"""
Utility to create a ncdu.json file from an export
"""
import dataclasses
import json
from typing import Dict, List, Optional, Union

from . import _nfs

# See https://dev.yorhel.nl/ncdu/jsonfmt

class Info:
    name: str
    asize: int = 0
    dsize: int = 0
    ino: int = 0
    nlink: int = 0
    dev: int = 0
    read_error: bool = False
    not_reg: bool = False
    excluded: str = ""
    children: Optional[List] = None

    __slots__ = ("name", "asize", "dsize", "ino", "nlink", "dev", "read_error", "not_reg", "excluded", "children")


    def to_json_repr(self, parent_dev: int = 0) -> str:
        answer: Dict[str, Union[int, str, bool]] = {"name": self.name}
        if self.asize:
            answer["asize"] = self.asize
        if self.dsize:
            answer["dsize"] = self.dsize
        if parent_dev != self.dev:
            answer["dev"] = self.dev
        if self.nlink > 1:
            answer["ino"] = self.ino
            answer["nlink"] = self.nlink
            answer["hlnkc"] = True
        if self.read_error:
            answer["read_error"] = True
        if self.not_reg:
            answer["not_reg"] = True

        return json.dumps(answer)

