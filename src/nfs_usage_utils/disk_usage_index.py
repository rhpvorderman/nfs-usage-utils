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


def node_start(entry: _nfs.NFSDirEntry, current_time: float) -> str:
    age_days = round(entry.st_mtime - current_time / (24 * 60 * 60))
    name = html.escape(entry.name)
    path = html.escape(entry.path)
    return (
        f'<node name="{name}" '
        f'href="file://{path}">\n'
        f'<age><val>{age_days}</val></age>\n'
        f'<score><val>{math.log(age_days + 1)}</val></score>\n'
    )


def node_end(magnitude: float) -> str:
    return (
        f'<magnitude><val>{magnitude}</val></magnitude>\n'
        f'</node>\n'
    )


def sorted_direntries_to_krona_index(
        entries: List[_nfs.NFSDirEntry],
        prefix: str,
        outfile: str,
) -> None:
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
        assert (first_entry.is_dir())
        current_dirs = [first_entry]
        dir_magnitudes = [0]
        out.write(node_start(first_entry, current_time))

        for entry in entry_iter:  # type: _nfs.NFSDirEntry
            current_dir = current_dirs[-1]
            while os.path.dirname(entry.path) != current_dir.path:
                # Exiting dir
                total_magnitude = dir_magnitudes.pop()
                out.write(node_end(magnitude=total_magnitude))
                current_dirs.pop()
                current_dir = current_dirs[-1]
            if entry.is_dir():
                out.write(node_start(entry, current_time))
                current_dirs.append(entry)
                dir_magnitudes.append(0)
            else:
                out.write(node_start(entry, current_time))
                magnitude = entry.st_blksize * entry.st_blocks / 1024 ** 3
                for i, size in enumerate(dir_magnitudes):
                    dir_magnitudes[i] = size + magnitude
                out.write(node_end(magnitude))
        while len(current_dirs) > 0:
            current_dirs.pop()
            magnitude = dir_magnitudes.pop()
            out.write(node_end(magnitude))
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
