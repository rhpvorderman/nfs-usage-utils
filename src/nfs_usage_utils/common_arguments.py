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
import argparse

from .nfscrawler import DEFAULT_MAX_REQUESTS
from .fstab import path_to_nfs_url

def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path", help="Path or URL")
    parser.add_argument("--fstab", default="/etc/fstab")
    parser.add_argument("--max-requests", type=int,
                        default=DEFAULT_MAX_REQUESTS)


def nfs_url_and_prefix_from_args(args: argparse.Namespace):
    path = args.path
    if path.startswith("nfs://"):
        prefix = "/"
        url = path
    else:
        prefix = path
        url = path_to_nfs_url(path, args.fstab)
    return url, prefix

