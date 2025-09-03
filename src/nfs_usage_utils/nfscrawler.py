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
import select
import warnings
from typing import Dict, Iterator, List

from . import _nfs as nfs

DEFAULT_MAX_REQUESTS = 10_000


def crawlnfs_simple(nfs_mount: nfs.NFSMount, path: str = "/"
                    ) -> Iterator[nfs.NFSDirEntry]:
    try:
        d = nfs.scandir(nfs_mount, path)
    except OSError as e:
        warnings.warn(f"{type(e).__name__}: {e}")
        return
    with d:
        for entry in d:
            yield entry
            if entry.is_dir():
                yield from crawlnfs_simple(nfs_mount, entry.path)


def crawlnfs_async(
    nfs_mount: nfs.NFSMount,
    path: str ="/",
    max_requests: int = DEFAULT_MAX_REQUESTS,
) -> Iterator[nfs.NFSDirEntry]:
    if max_requests < 1:
        raise ValueError("max_requests should be 1 or higher")
    todo_dirs = [path]
    requested_dirs: Dict[str, nfs.ScandirIterator] = {}

    poller = select.poll()
    while requested_dirs or todo_dirs:
        while todo_dirs and len(requested_dirs) < max_requests:
            p = todo_dirs.pop()
            requested_dirs[p] = nfs.scandir_async(nfs_mount, p)
        # Wait for some requests to finish
        fd = nfs_mount.get_fd()
        events = nfs_mount.which_events()
        poller.register(fd, events)
        finished_polls = poller.poll(nfs_mount.get_timeout())
        if not finished_polls:
            raise TimeoutError("Timed out while waiting for connection.")
        if len(finished_polls) != 1:
            raise RuntimeError(f"Only one poll was registered, what is going on? {finished_polls}")
        fd, revents = finished_polls[0]
        nfs_mount.service(revents)

        # Check which of the dirobjects are ready
        ready_dirs: List[nfs.ScandirIterator] = []
        to_remove_paths: List[str] = []
        for path, dirobj in requested_dirs.items():
            try:
                if dirobj.ready():
                    ready_dirs.append(dirobj)
                    to_remove_paths.append(path)
            except OSError as e:
                warnings.warn(f"{type(e).__name__}: {e}")
                to_remove_paths.append(path)
                continue
        for path in to_remove_paths:
            del requested_dirs[path]

        # Iterate over all the ready dirs
        for dir in ready_dirs:
            with dir:
                for entry in dir:  # type: nfs.NFSDirEntry
                    yield entry
                    if entry.is_dir():
                        if len(requested_dirs) < max_requests:
                            requested_dirs[entry.path] = nfs.scandir_async(
                                nfs_mount, entry.path)
                        else:
                            todo_dirs.append(entry.path)

def crawlnfs(nfs_mount: nfs.NFSMount, path: str = "/",
             max_requests: int = DEFAULT_MAX_REQUESTS,
             ) -> Iterator[nfs.NFSDirEntry]:
    """
    Recursively crawl through the NFS mount at a given path (default '/').
    Yield nfs.NFSDirEntry objects. Raises warnings on permission errors.
    Threads indicate the number of worker threads that send the READDIR
    request to the server and wait for its response. This happens outside the
    GIL.
    When threads is 0 all request to the server are made by the main thread.
    """
    return crawlnfs_async(nfs_mount, path, max_requests)
