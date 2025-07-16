===============
nfs-usage-utils
===============
Python scripts using calls to libnfs for fast usage and dedup scripts.

This project aims to provide the following tools for nfs:

- A duplicate indexer using the [jdupes](https://codeberg.org/jbruchon/jdupes) 
  JSON output format.
- (Not currently worked on) a duc compatible disk usage indexer. See also
   https://github.com/zevv/duc/issues/342
- Any other utilities that are found to be incredibly slow on our NFSv4 
  share and for which my patience has run out.

Of course there are Python bindings for libnfs that can be used:
https://pypi.org/project/libnfs/. But these are very old. No NFSv4 
support. This program will only be provided as source so it can be compiled 
against whatever libnfs client is running on your systems.

Design
======

This is going to implement python bindings for libnfs where necessary using
Python C extensions. The rest of the program is going to be implemented in 
python because 

- Network latency is a more important factor than raw computational speed. 
  Most other indexers are sleeping 95% of the time waiting for responses, so 
  there is some compute budget. 
- Python has builtin hash maps, very little opportunity for segfaults and a 
  very good C-API.
