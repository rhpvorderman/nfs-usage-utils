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


NFS_V4: int

NF4REG: int
NF4DIR: int
NF4BLK: int
NF4CHR: int
NF4LNK: int
NF4SOCK: int
NF4FIFO: int
NF4ATTRDIR: int
NF4NAMEDATTR: int


class NFSMount:
    def __init__(self, url: str): ...
    def __enter__(self): ...
    def __exit__(self, *args): ...
    def close(self): ...
    def service(self, revents: int) -> None: ...
    def get_fd(self) -> int: ...
    def which_events(self) -> int: ...
    def queue_length(self) -> int: ...


class NFSDirEntry:
    name: str
    path: str
    st_ino: int
    type: int
    st_mode: int
    st_size: int
    st_uid: int
    st_gid: int
    st_nlink: int
    st_dev: int
    st_rdev: int
    st_blksize: int
    st_blocks: int
    st_atime: float
    st_mtime: float
    st_ctime: float

    def is_file(self): ...
    def is_dir(self): ...
    def is_symlink(self): ...
    def inode(self) -> int: ...


class ScandirIterator():
    def __enter__(self) -> ScandirIterator: ...
    def __exit__(self, *args): ...
    def __iter__(self) -> ScandirIterator: ...
    def __next__(self) -> NFSDirEntry: ...
    def close(self): ...
    def ready(self) -> bool: ...


def scandir(nfs_mount: NFSMount, path: str = "/") -> ScandirIterator: ...
def scandir_async(nfs_mount: NFSMount, path: str = "/") -> ScandirIterator: ...
