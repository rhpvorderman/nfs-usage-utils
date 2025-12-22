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
import argparse
import json
from typing import Dict, Optional, Union, Iterable, List

from . import _nfs
from .common_arguments import add_common_arguments, nfs_url_and_prefix_from_args
from .nfscrawler import crawlnfs
from ._version import __version__

# See https://dev.yorhel.nl/ncdu/jsonfmt

class Info:
    # use slots to save on space.
    __slots__ = ("name", "asize", "dsize", "ino", "nlink", "dev", "read_error",
                 "not_reg", "excluded", "children")

    def __init__(
        self,
        name: str,
        asize: int = 0,
        dsize: int = 0,
        ino: int = 0,
        nlink: int = 0,
        dev: int = 0,
        read_error: bool = False,
        not_reg: bool = False,
        excluded: Optional[str] = None,
        children: Optional[Dict] = None,
    ):
        self.name = name
        self.asize = asize
        self.dsize = dsize
        self.ino = ino
        self.nlink = nlink
        self.dev = dev
        self.read_error = read_error
        self.not_reg = not_reg
        self.excluded = excluded
        if self.children is None:
            self.children = {}
        else:
            self.children = self.children

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
        if self.excluded:
            answer["excluded"] = self.excluded
        return json.dumps(answer)


def NFSEntry_to_info(entry: _nfs.NFSDirEntry):
    answer = {
        "name": entry.name,
        "asize": entry.st_size,
        "dsize": entry.st_blocks * entry.st_blksize,
        "dev": entry.st_dev,
    }


def main():
    parser = argparse.ArgumentParser()
    add_common_arguments(parser)
    args = parser.parse_args()
    url, prefix = nfs_url_and_prefix_from_args(args)
    with _nfs.NFSMount(url) as mount:
        crawl = crawlnfs(mount, prefix)
        # Set the path separator to \x00 so it comes before all other characters.
        # This ensures that directories always come before the respective files.
        entries: List[_nfs.NFSDirEntry] = sorted(
            crawl, key=lambda x: x.path.replace("/", "\x00"))
    major_version = 1
    minor_version = 2  # ncdu 1.16 and higher
    metadata = dict(progname="nfs_usage_utils", progver=__version__)
    print(f"[{major_version}, {minor_version}, {json.dumps(metadata)},")
    for entry in entries:  # type: _nfs.NFSDirEntry
        pass


if __name__ == "__main__":
    main()