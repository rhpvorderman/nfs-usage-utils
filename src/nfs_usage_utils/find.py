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

from . import _nfs as nfs

from .common_arguments import add_common_arguments, nfs_url_and_prefix_from_args
from .nfscrawler import DEFAULT_MAX_REQUESTS, crawlnfs


def find(
        nfs_mount: nfs.NFSMount,
        predicates: List[Callable[[nfs.NFSDirEntry], bool]],
        max_requests: int = DEFAULT_MAX_REQUESTS):
    for entry in crawlnfs(nfs_mount, max_requests=max_requests):
        if not all(map(lambda func: func(entry), predicates)):
            continue
        yield entry.path


def argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(__doc__)
    add_common_arguments(parser)
    return parser


def main():
    args = argument_parser().parse_args()
    url, prefix = nfs_url_and_prefix_from_args(args)
    with nfs.NFSMount(url, hash_size=args.max_requests // 10) as nfs_mount:
        for path in find(nfs_mount, [], max_requests=args.max_requests):
            new_path = os.path.normpath(f"{prefix}/{path}")
            print(new_path)


if __name__ == "__main__":
    main()
