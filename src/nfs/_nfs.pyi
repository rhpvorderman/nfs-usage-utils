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
