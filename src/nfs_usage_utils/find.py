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
"""
Simple utility to list all the files present on the NFS filesystem. As of yet
no predicates are implemented.
"""

import argparse
import os

import nfs

from .fstab import path_to_nfs_url
from .nfscrawler import crawlnfs


def find(nfs_url: str, threads: int = 0):
    for entry in crawlnfs(nfs_url, threads=threads):
        yield entry.path


def argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("path", help="Path or URL")
    parser.add_argument("--fstab", default="/etc/fstab")
    parser.add_argument("--threads", type=int, default=0)
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
    for path in find(url, threads=args.threads):
        new_path = os.path.normpath(f"{prefix}/{path}")
        print(new_path)


if __name__ == "__main__":
    main()
