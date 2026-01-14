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
import os.path
import struct
import typing
from typing import Any, Dict, Iterator, List

from . import _nfs
from .common_arguments import add_common_arguments, nfs_url_and_prefix_from_args
from .nfscrawler import crawlnfs
from ._version import __version__

# See https://dev.yorhel.nl/ncdu/jsonfmt

NOTREG = 0
DIR = 1
FILE = 2

class Info(typing.NamedTuple):
    """Little helper class to make NFSDirEntry's less memory intensive"""
    path: str
    asize: int
    dsize: int
    dev: int
    ino: int
    nlink: int
    filetype: int

    def name(self) -> str:
        """Retrieves the name from the path as it is redundant."""
        return os.path.basename(self.path)

    def to_bytes(self) -> bytes:
        path = self.path.encode("utf-8")
        data = struct.pack(
            "<QQQQIB",
            self.asize,  # uint64_t
            self.dsize,      # uint64_t
            self.dev,        # uint64_t
            self.ino,        # uint64_t
            self.nlink,      # uint32_t
            self.filetype,   # uint8_t
        )
        return path + b"\x00" + data

    @classmethod
    def from_bytes(cls, buffer: bytes):
        path, data = buffer.split(b"\x00")
        asize, dsize, dev, ino, nlink, filetype = struct.unpack("<QQQQIB", data)
        return cls(
            path = path.decode("utf-8"),
            asize=asize,
            dsize=dsize,
            dev=dev,
            ino=ino,
            nlink=nlink,
            filetype=filetype,
        )

    @classmethod
    def from_nfs_dir_entry(cls, entry: _nfs.NFSDirEntry):
        # Data compression is based on this assumption, so test it.
        if os.path.basename(entry.path) != entry.name:
            raise RuntimeError(
                f"Path and name basename do not match. {entry.path} | {entry.name}"
            )
        if entry.is_file():
            tp = FILE,
        elif entry.is_dir():
            tp = DIR
        else:
            tp = NOTREG
        return cls(
            path=entry.path,
            asize=entry.st_size,
            dsize=entry.st_blocks * entry.st_blksize,
            dev=entry.st_dev,
            ino=entry.st_ino,
            nlink = entry.st_nlink,
            filetype=tp,
        )

    def to_json(self, parent_dev: int = 0) -> Dict[str, Any]:
        answer = {
            "name": self.name(),
            "asize": self.asize,
            "dsize": self.dsize,
        }
        if self.dev != parent_dev:
            answer["dev"] = self.dev
        if self.nlink > 1:
            answer["ino"] = self.ino
            answer["nlink"] = self.nlink
            answer["hlnkc"] = True
        if self.filetype == NOTREG:
            answer["notreg"] = True
        return answer


def NFSDirEntry_to_info_block(entry: _nfs.NFSDirEntry, parent_dev: int = 0) -> Dict[str, Any]:
    answer = {
        "name": entry.name,
        "asize": entry.st_size,
        "dsize": entry.st_blocks * entry.st_blksize,
    }
    if entry.st_dev != parent_dev:
        answer["dev"] = entry.st_dev
    if entry.st_nlink > 1:
        answer["ino"] = entry.st_ino
        answer["nlink"] = entry.st_nlink
        answer["hlnkc"] = True
    if not (entry.is_dir() or entry.is_file()):
        answer["notreg"] = True
    return answer


def main():
    parser = argparse.ArgumentParser()
    add_common_arguments(parser)
    parser.add_argument("-o", "--out", default="/dev/stdout",
                        help="output file")
    args = parser.parse_args()
    url, prefix = nfs_url_and_prefix_from_args(args)
    with _nfs.NFSMount(url, hash_size = args.max_requests // 10) as mount:
        crawl = crawlnfs(mount, max_requests=args.max_requests)
        # Set the path separator to \x00 so it comes before all other characters.
        # This ensures that after sorting directories always come before the
        # respective files.
        entries: List[_nfs.NFSDirEntry] = sorted(
            crawl, key=lambda x: x.path.replace("/", "\x00"))
    if len(entries) < 1:
        return

    with open(args.out, "wt") as out:
        major_version = 1
        minor_version = 2  # ncdu 1.16 and higher
        metadata = dict(progname="nfs_usage_utils", progver=__version__)

        out.write(f"[{major_version}, {minor_version}, {json.dumps(metadata)},\n")

        entry_iter: Iterator[_nfs.NFSDirEntry] = iter(entries)
        first_entry: _nfs.NFSDirEntry = next(entry_iter)
        assert (first_entry.is_dir())
        first_entry_info = NFSDirEntry_to_info_block(first_entry, -1)
        # The top level entry should have the full path according to the spec.
        first_entry_info["name"] = prefix
        out.write("[")
        out.write(json.dumps(first_entry_info))
        current_dirs = [first_entry]
        for entry in entry_iter:  # type: _nfs.NFSDirEntry
            current_dir = current_dirs[-1]
            while os.path.dirname(entry.path) != current_dir.path:

                out.write("]")
                current_dirs.pop()
                current_dir = current_dirs[-1]
            if entry.is_dir():
                out.write(",\n[")
                current_dirs.append(entry)
                current_dir = entry
                out.write(json.dumps(NFSDirEntry_to_info_block(
                    entry, parent_dev=current_dir.st_dev)))
            else:
                out.write(",\n")
                out.write(json.dumps(NFSDirEntry_to_info_block(
                    entry, parent_dev=current_dir.st_dev)))
        while len(current_dirs) > 0:
            current_dirs.pop()
            out.write("]")  # Finish open directories
        out.write("]")  # Finish total array.


if __name__ == "__main__":
    main()