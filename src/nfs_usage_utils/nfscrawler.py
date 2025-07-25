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
import queue
import select
import threading
import warnings
from typing import Iterator, List, Optional, Union


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


class MultiThreadedAsyncReaddir:
    def __init__(self, nfs_url, async_connections, timeout_millisecs: int = 5000):
        self.nfs_url = nfs_url
        self.nfs_mounts = [nfs.NFSMount(nfs_url) for _ in range(async_connections)]
        self.input_queues: List[queue.Queue[str]] = [queue.Queue() for _ in range(async_connections)]
        self.output_queue: queue.Queue[Union[nfs.ScandirIterator, Exception]] = queue.Queue(maxsize=async_connections * 3)
        self.running = True
        self.index = 0
        self.workers = [
            threading.Thread(target=self.worker, args=(mount, q, timeout_millisecs))
            for mount, q in zip(self.nfs_mounts, self.input_queues)
        ]
        for worker in self.workers:
            worker.start()

    def put(self, path: str):
        self.input_queues[self.index].put(path)
        self.index += 1
        self.index %= len(self.input_queues)

    def get(self):
        return self.output_queue.get()

    def task_done(self):
        self.output_queue.task_done()

    def stop(self):
        for q in self.input_queues:
            q.join()
        self.running = False
        for worker in self.workers:
            worker.join()

    def worker(self, nfs_mount, input_queue: queue.Queue[str] , timeout_millisecs):
        poller = select.poll()
        with nfs_mount:
            while self.running:
                try:
                    path = input_queue.get(timeout=0.001)
                except queue.Empty:
                    continue
                result = None
                dir = nfs.scandir_async(nfs_mount, path)
                ready = False
                while not ready:
                    fd = nfs_mount.get_fd()
                    events = nfs_mount.which_events()
                    poller.register(fd, events)
                    poll_results = poller.poll(timeout_millisecs)
                    if len(poll_results) == 0:
                        result =  TimeoutError(
                            f"Timeout while requesting {path}")
                        break
                    fd, revents = poll_results[0]
                    nfs_mount.service(revents)
                    try:
                        ready = dir.ready()
                    except Exception as e:
                        result = e
                        break
                if result is None:
                    result = dir
                self.output_queue.put(result)
                input_queue.task_done()


def crawl_nfs_async_threaded(
    nfs_url: str,
    path: str = "/",
    async_connections: int = 1,
    timeout_millisecs: int = 5000,
) -> Iterator[nfs.NFSDirEntry]:
    readdir_queue =  MultiThreadedAsyncReaddir(nfs_url, async_connections, timeout_millisecs)
    readdir_queue.put(path)
    directories_put = 1
    directories_got = 0
    while(directories_put - directories_got):
        try:
            dir_or_error = readdir_queue.get()
            directories_got += 1
            if isinstance(dir_or_error, Exception):
                warnings.warn(f"{type(dir_or_error).__name__}: {dir_or_error}")
                continue
            with dir_or_error:
                for entry in dir_or_error:  # type: nfs.NFSDirEntry
                    yield entry
                    if entry.is_dir():
                        readdir_queue.put(entry.path)
                        directories_put += 1
        finally:
            readdir_queue.task_done()
    readdir_queue.stop()
    assert readdir_queue.output_queue.qsize() == 0


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
        return crawl_nfs_async_threaded(nfs_url, path, async_connections)
