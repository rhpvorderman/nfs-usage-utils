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
Simple utility to get the disk usage per file.
"""
import argparse
from collections import defaultdict

from .common_arguments import add_common_arguments, nfs_url_and_prefix_from_args
from .nfscrawler import crawlnfs
from . import _nfs as nfs

def main():
    parser = argparse.ArgumentParser(__doc__)
    add_common_arguments(parser)
    args = parser.parse_args()
    compressed_exts = ("gz", "bz2", "xz")
    size_by_extension = defaultdict(lambda: 0)
    url, prefix = nfs_url_and_prefix_from_args(args)
    with nfs.NFSMount(url) as nfs_mount:
        for entry in crawlnfs(nfs_mount, max_requests=args.max_requests):
            if not entry.is_file():
                continue
            name_parts = entry.name.rsplit(".", maxsplit=2)
            if len(name_parts) == 1:
                extension = "No extension"
            elif len(name_parts) == 3 and name_parts[2] in compressed_exts:
                extension = ".".join(name_parts[1:])
            else:
                extension = name_parts[-1]
            size = entry.st_blocks * entry.st_blksize
            size_by_extension[extension] += size

    total_size = sum(size_by_extension.values())
    sorted_by_size = sorted(size_by_extension.items(),
                            key=lambda x: x[1],
                            reverse=True)
    remaining_index = len(sorted_by_size)
    for i, (extension, size) in enumerate(sorted_by_size):
        if (size / total_size) < 0.001:
            remaining_index = i
            break
    sorted_by_size_truncated = sorted_by_size[:remaining_index]
    sorted_by_size_truncated.append(
        ("other", sum(size for ext, size in sorted_by_size[remaining_index:])))
    print(f"Total\t{total_size / (1024 ** 3):.2f} GiB\t100.00%")
    for extension, size in sorted_by_size_truncated:
        print(f"{extension}\t{size / 1024 **3:.2f} GiB\t{size / total_size:.2%}")


if __name__ == "__main__":
    main()