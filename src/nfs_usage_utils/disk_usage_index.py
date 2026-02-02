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
Utility to create a disk usage index for ncdu and krona.

Creates a ncdu.json file which can be opened with '''ncdu -f ncdu.json'''

Creates a krona.xml file which can be converted to krona html with
'''ktImportXML krona.xml'''

"""
import argparse
import html
import json
import math
import os.path
import sys
import time
from typing import Any, Dict, Iterator, List, Tuple

from . import _nfs
from .common_arguments import add_common_arguments, nfs_url_and_prefix_from_args
from .nfscrawler import crawlnfs
from ._version import __version__

# See https://dev.yorhel.nl/ncdu/jsonfmt


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


def sorted_direntries_to_ncdu_index(
        entries: List[_nfs.NFSDirEntry], prefix: str, outfile: str) -> None:
    with open(outfile, "wt") as out:
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


def file_age_days(entry: _nfs.NFSDirEntry, current_time: float = time.time()):
    return round((current_time - entry.st_mtime) / (24 * 60 * 60))


def file_size(entry: _nfs.NFSDirEntry):
    return entry.st_blocks * entry.st_blksize


def size_to_magnitude(filesize: int):
    return filesize / (1024 ** 3)


def file_to_magnitude(entry: _nfs.NFSDirEntry):
    return size_to_magnitude(file_size(entry))


def dirnode_start(entry: _nfs.NFSDirEntry, prefix: str, magnitude: float) -> str:
    age_days = file_age_days(entry)
    # If entry has no name it is the root folder
    name = html.escape(entry.name or "root")
    path = html.escape(entry.path)
    return (
        f'<node name="{name}" '
        f'href="file://{prefix}/{path}">\n'
        f'<age><val>{age_days}</val></age>\n'
        f'<score><val>{math.log(age_days + 1)}</val></score>\n'
        f'<magnitude><val>{magnitude}</val></magnitude>\n'
    )


def dirnode_end() -> str:
    return '</node>\n'


def filenode(entry: _nfs.NFSDirEntry, prefix: str,):
    magnitude = file_to_magnitude(entry)
    return dirnode_start(entry, prefix, magnitude) + dirnode_end()


def small_files_and_folders_node(filesize, minimum_age):
    return (
        f'<node name="[Small files or folders]">\n'
        f'<magnitude><val>{size_to_magnitude(filesize)}</val></magnitude>\n'
        f'<age><val>{minimum_age}</val></age>\n'
        f'<score><val>{math.log(minimum_age + 1)}</val></score>\n'
        f'</node>\n'
    )


def sorted_direntries_to_total_size_and_dir_sizes(
    entries: List[_nfs.NFSDirEntry],
) -> Tuple[int, Dict[str, int]]:
    entry_iter: Iterator[_nfs.NFSDirEntry] = iter(entries)
    first_entry: _nfs.NFSDirEntry = next(entry_iter)
    assert (first_entry.is_dir())
    current_dirs = [first_entry]
    dir_magnitudes = [0]
    total_size = 0
    dir_sizes: Dict[str, int] = {}
    for entry in entries:
        current_dir = current_dirs[-1]
        while os.path.dirname(entry.path) != current_dir.path:
            # Exiting dir
            total_magnitude = dir_magnitudes.pop()
            sized_dir_entry = current_dirs.pop()
            dir_sizes[sized_dir_entry.path] = total_magnitude
            current_dir = current_dirs[-1]
        if entry.is_dir():
            current_dirs.append(entry)
            dir_magnitudes.append(0)
        elif entry.is_file():
            magnitude = entry.st_blksize * entry.st_blocks
            for i, size in enumerate(dir_magnitudes):
                dir_magnitudes[i] = size + magnitude
            total_size += magnitude
    while len(current_dirs) > 0:
        dir_sizes[current_dirs.pop().path] = dir_magnitudes.pop()
    return total_size, dir_sizes


def sorted_direntries_to_krona_index(
        entries: List[_nfs.NFSDirEntry],
        prefix: str,
        outfile: str,
) -> None:
    total_size, dir_sizes = sorted_direntries_to_total_size_and_dir_sizes(entries)
    size_threshold = total_size // 1000

    with open(outfile, "wt") as out:
        out.write('<krona collapse="false" key="true">\n')
        out.write('<attributes magnitude="magnitude">\n')
        out.write('<attribute display="Size (GiB)">magnitude</attribute>\n')
        out.write('<attribute display="Age (days since modified)">age</attribute>\n')
        out.write('<attribute display="Log(Age+1)">score</attribute>\n')
        out.write("</attributes>\n")
        out.write(
            '<color attribute="score" '
            'hueStart="300" '
            'hueEnd="240" '
            'valueStart="0.602059991327962" '
            'valueEnd="2.27415784926368" '
            'default="false" >'
            '</color>')

        current_time = time.time()
        entry_iter: Iterator[_nfs.NFSDirEntry] = iter(entries)
        first_entry: _nfs.NFSDirEntry = next(entry_iter)
        current_dirs = [first_entry]
        out.write(dirnode_start(
            entry=first_entry,
            prefix=prefix,
            magnitude=size_to_magnitude(dir_sizes[first_entry.path]))
        )
        small_files_and_folders_sizes = [0]
        small_files_and_folders_ages = [0]
        skipped_dirs = set()
        for entry in entry_iter:  # type: _nfs.NFSDirEntry
            current_dir = current_dirs[-1]
            if os.path.dirname(entry.path) in skipped_dirs:
                if entry.is_dir():
                    skipped_dirs.add(entry.path)
                continue
            while os.path.dirname(entry.path) != current_dir.path:
                # Exiting dir
                small_sizes = small_files_and_folders_sizes.pop()
                small_ages = small_files_and_folders_ages.pop()
                if small_sizes > 0:
                    out.write(small_files_and_folders_node(small_sizes, small_ages))
                out.write(dirnode_end())
                current_dirs.pop()
                current_dir = current_dirs[-1]
            if entry.is_dir():
                dir_bytes = dir_sizes[entry.path]
                if dir_bytes < size_threshold:
                    skipped_dirs.add(entry.path)
                    small_files_and_folders_sizes[-1] += dir_bytes
                    age_days = file_age_days(entry)
                    small_files_and_folders_ages[-1] = min(
                        small_files_and_folders_ages[-1], age_days)
                    continue
                out.write(dirnode_start(
                    entry=entry,
                    prefix=prefix,
                    magnitude=size_to_magnitude(dir_sizes[entry.path])
                ))
                small_files_and_folders_sizes.append(0)
                small_files_and_folders_ages.append(sys.maxsize)
                current_dirs.append(entry)
            elif entry.is_file():
                filesize = entry.st_blksize * entry.st_blocks
                if filesize < size_threshold:
                    small_files_and_folders_sizes[-1] += filesize
                    age_days = file_age_days(entry)
                    small_files_and_folders_ages[-1] = min(
                        small_files_and_folders_ages[-1], age_days)
                    continue
                out.write(filenode(entry, prefix))
        while len(current_dirs) > 0:
            current_dirs.pop()
            small_sizes = small_files_and_folders_sizes.pop()
            small_ages = small_files_and_folders_ages.pop()
            out.write(small_files_and_folders_node(small_sizes, small_ages))
            out.write(dirnode_end())
        out.write("</krona>")


def main():
    parser = argparse.ArgumentParser(__doc__)
    add_common_arguments(parser)
    parser.add_argument("--ncdu-out", default="ncdu.json",
                        help="output file")
    parser.add_argument("--krona-out", default="krona.xml",
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
    sorted_direntries_to_ncdu_index(
        entries=entries,
        prefix=prefix,
        outfile=args.ncdu_out,
    )
    sorted_direntries_to_krona_index(
        entries=entries,
        prefix=prefix,
        outfile=args.krona_out,
    )


if __name__ == "__main__":
    main()
