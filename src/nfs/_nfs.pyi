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

NFS_V2: int
NFS_V3: int
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

NF3REG: int
NF3DIR: int
NF3BLK: int
NF3CHR: int
NF3LNK: int
NF3SOCK: int
NF3FIFO: int

NF2NON: int
NF2REG: int
NF2DIR: int
NF2BLK: int
NF2CHR: int
NF2LNK: int


class NFSMount:
    def __init__(self, url: str): ...
    def __enter__(self): ...
    def __exit__(self, *args): ...
    def close(self): ...


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
    def __enter__(self): ...
    def __exit__(self, *args): ...
    def __iter__(self): ...
    def __next__(self) -> NFSDirEntry: ...
    def close(self): ...


def scandir(mount: NFSMount, path: str = "/") -> ScandirIterator: ...
