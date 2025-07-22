# Copyright (c) 2025 Leiden University Medical Center
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
import argparse
import os.path
import typing
from typing import Iterable, Iterator, Tuple

"""
Parse a path and an fstab file with nfs mounts to into a libnfs url.
"""

class FSTabEntry(typing.NamedTuple):
    source: str  # Source
    target: str  # target
    type: str
    mount_options: Tuple[str, ...]
    dump: int
    passno: int

    @classmethod
    def from_fstab_line(cls, line:str):
        line = line.strip()
        source, target, type, mnt_opts, dump, passno = line.split()
        mount_options = tuple(mnt_opts.split(","))
        return cls(
            source,
            target,
            type,
            mount_options,
            int(dump),
            int(passno)
        )

    def to_fstab_line(self):
        return (
            f"{self.source}\t{self.target}\t{self.type}\t"
            f"{','.join(self.mount_options)}\t{self.dump}\t{self.passno}\n"
        )


def parse_fstab(fstab: str = "/etc/fstab") -> Iterator[FSTabEntry]:
    with open(fstab, "rt") as f:
        for line in f:
            if line.startswith("#"):
                continue
            if not line.strip():
                # empty line
                continue
            yield FSTabEntry.from_fstab_line(line)


def fstab_mount_options_to_url_options(mount_options: Iterable[str]):
    url_options = []
    for option in mount_options:
        if "=" in option:
            key, value = option.split("=", maxsplit=1)
        else:
            key = option
            value = ""

        if key in ("timeo", "rsize", "wsize", "sec", "retrans", "mountport"):
            url_options.append(option)
            continue
        if key in ("nfsvers", "vers"):
            url_options.append(f"version={value}")
            continue
        if key == "port":
            url_options.append(f"nfsport={value}")
            continue
    if not url_options:
        return ""
    return f"?{'&'.join(url_options)}"


def path_to_nfs_url(path: str, fstab: str = "/etc/fstab") -> str:
    path = os.path.abspath(path)  # Also gets rid of trailing slashes.
    for entry in parse_fstab(fstab):
        if not entry.type == "nfs":
            continue
        mount_path = os.path.normpath(entry.target)  # get rid of trailing slashes.
        # Either path is a mount path, or path is a nested subdirectory.
        # Prevent /mynfs/myshare/subdir matching to /mynfs/myshare2/subdir if
        # /mynfs/myshare and /mynfs/myshare2 are both mount points.
        if path == mount_path or path.startswith(mount_path + "/"):
            if ":" in entry.source:
                server, folder = entry.source.split(":")
            else:
                server = entry.source
                folder = "/"
            if not folder.startswith("/"):
                raise RuntimeError(
                    f"Parsed folder, "f"'{folder}' does not start with '/'. "
                    f"This was not anticipated.")
            path_in_folder = os.path.relpath(path, mount_path)
            folder = os.path.normpath(os.path.join(folder, path_in_folder))
            url_options = fstab_mount_options_to_url_options(entry.mount_options)
            return f"nfs://{server}{folder}{url_options}"
    raise RuntimeError("Matching fstab entry not found")


def argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("path", help="Path on the filesystem.")
    parser.add_argument("--fstab", default="/etc/fstab",
                        help="Location of fstab. Default: '/etc/fstab'")
    return parser


def main():
    args = argument_parser().parse_args()
    print(path_to_nfs_url(args.path, args.fstab))


if __name__ == "__main__":
    main()
