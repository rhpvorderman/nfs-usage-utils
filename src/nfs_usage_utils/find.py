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
Simple utility to list all the files present on the NFS filesystem. As of yet
no predicates are implemented.
"""

import argparse
import os
from typing import Callable, List

import nfs

from .fstab import path_to_nfs_url
from .nfscrawler import crawlnfs


def find(
        nfs_url: str,
        predicates: List[Callable[[nfs.NFSDirEntry], bool]],
        async_connections: int = 1):
    for entry in crawlnfs(nfs_url, async_connections=async_connections):
        if not all(map(lambda func: func(entry), predicates)):
            continue
        yield entry.path


def argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("path", help="Path or URL")
    parser.add_argument("--fstab", default="/etc/fstab")
    parser.add_argument("-c", "--connections", type=int, default=1)
    return parser


def main():
    args = argument_parser().parse_args()
    path = args.path
    if path.startswith("nfs://"):
        prefix = "/"
        url = path
    else:
        prefix = path
        url = path_to_nfs_url(path, args.fstab)

    for path in find(url, [], async_connections=args.connections):
        new_path = os.path.normpath(f"{prefix}/{path}")
        print(new_path)


if __name__ == "__main__":
    main()
