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
import contextlib
import select
import warnings
from typing import Iterator, List, Optional


import nfs


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
    nfs_url: str,
    path: str ="/",
    async_connections: int = 1,
    timeout_millisecs: int = 5000,
) -> Iterator[nfs.NFSDirEntry]:

    exit_stack = contextlib.ExitStack()
    nfs_mounts = []
    for _ in range(async_connections):
        mount = nfs.NFSMount(nfs_url)
        exit_stack.enter_context(mount)
        nfs_mounts.append(mount)
    todo_dirs = [path]
    requested_dirs: List[Optional[nfs.ScandirIterator]] = [
        None for _ in range(async_connections)]

    poller = select.poll()

    with exit_stack:
        fd_to_nfs_mount = {mount.get_fd(): mount for mount in nfs_mounts}
        while todo_dirs or any(requested_dirs):
            # Check which slots are empty and fill them with requests
            for i, dirobj in enumerate(requested_dirs):
                if todo_dirs and dirobj is None:
                    dirpath = todo_dirs.pop()
                    request = nfs.scandir_async(nfs_mounts[i], dirpath)
                    requested_dirs[i] = request

            for nfs_mount in nfs_mounts:
                fd = nfs_mount.get_fd()
                events = nfs_mount.which_events()
                poller.register(fd, events)
            finished_polls = poller.poll(timeout_millisecs)
            if not finished_polls:
                raise TimeoutError("Timed out while waiting for connection.")
            for fd, revents in finished_polls:
                nfs_mount = fd_to_nfs_mount[fd]
                nfs_mount.service(revents)

            # Check which of the dirobjects are ready
            ready_dirs: List[nfs.ScandirIterator] = []
            for i, dirobj in enumerate(requested_dirs):
                if dirobj is None:
                    continue
                try:
                    ready = dirobj.ready()
                except OSError as e:
                    warnings.warn(f"{type(e).__name__}: {e}")
                    requested_dirs[i] = None
                    continue
                if not ready:
                    continue
                requested_dirs[i] = None
                ready_dirs.append(dirobj)

            # Iterate over all the ready dirs
            for dir in ready_dirs:
                with dir:
                    for entry in dir:  # type: nfs.NFSDirEntry
                        yield entry
                        if entry.is_dir():
                            todo_dirs.append(entry.path)


def crawlnfs(nfs_url: str, path: str = "/", async_connections: int = 1
             ) -> Iterator[nfs.NFSDirEntry]:
    """
    Recursively crawl through the NFS mount at a given path (default '/').
    Yield nfs.NFSDirEntry objects. Raises warnings on permission errors.
    Threads indicate the number of worker threads that send the READDIR
    request to the server and wait for its response. This happens outside the
    GIL.
    When threads is 0 all request to the server are made by the main thread.
    """
    if async_connections == 1:
        with nfs.NFSMount(nfs_url) as nfs_mount:
            return crawlnfs_simple(nfs_mount, path)
    else:
        return crawlnfs_async(nfs_url, path, async_connections)
