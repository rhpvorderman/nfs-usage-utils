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
import queue
import threading
import warnings
from queue import Queue
from typing import Iterator, Tuple

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


class ThreadedNfsCrawler:
    def __init__(self, nfs_url, path, threads: int = 1):
        self.input_queue: Queue[str] = Queue()
        self.output_queue: Queue[Tuple[nfs.NFSDirEntry, ...]] = Queue(maxsize=threads * 3)
        self.mounts = [nfs.NFSMount(nfs_url) for _ in range(threads)]
        self.worker_busy = [threading.Event() for _ in range(threads)]
        self.workers = [
            threading.Thread(target=self._worker, args=(mount, busy), daemon=False)
            for mount, busy in zip(self.mounts, self.worker_busy)]
        self.lock = threading.Lock()
        self.running = True
        for worker in self.workers:
            worker.start()
        self.input_queue.put(path)

    def close(self):
        for mount in self.mounts:
            mount.close()


    def stop(self):
        self.running = False
        while True:
            try:
                self.output_queue.get(timeout=0.05)
            except queue.Empty:
                break
        for worker in self.workers:
            worker.join()


    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __enter__(self):
        return self

    def _worker(self, nfs_mount: nfs.NFSMount, busy: threading.Event):
        while self.running:
            try:
                path = self.input_queue.get(timeout=0.05)
            except queue.Empty:
                continue
            if not self.running:
                return
            busy.set()
            try:
                iterator = nfs.scandir(nfs_mount, path)
                result = tuple(iterator)
            except OSError as e:
                warnings.warn(f"{type(e).__name__}: {e}")
                continue
            self.output_queue.put(result)
            for entry in result:
                if entry.is_dir() and self.running:
                    self.input_queue.put(entry.path)
            self.input_queue.task_done()
            busy.clear()

    def __iter__(self) -> Iterator[nfs.NFSDirEntry]:
        while True:
            try:
                dirlist = self.output_queue.get(timeout=0.05)
            except queue.Empty:
                if not self.input_queue.empty():
                    continue
                if any(b.is_set() for b in self.worker_busy):
                    continue
                if not self.output_queue.empty():
                    continue
                self.stop()
                return
            yield from dirlist
            self.output_queue.task_done()


def crawlnfs(nfs_url: str, path: str = "/", threads: int = 0
             ) -> Iterator[nfs.NFSDirEntry]:
    """
    Recursively crawl through the NFS mount at a given path (default '/').
    Yield nfs.NFSDirEntry objects. Raises warnings on permission errors.
    Threads indicate the number of worker threads that send the READDIR
    request to the server and wait for its response. This happens outside the
    GIL.
    When threads is 0 all request to the server are made by the main thread.
    """
    if threads == 0:
        with nfs.NFSMount(nfs_url) as nfs_mount:
            return crawlnfs_simple(nfs_mount, path)
    else:
        with ThreadedNfsCrawler(nfs_url, path, threads) as crawler:
            return iter(crawler)
