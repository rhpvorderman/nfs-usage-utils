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

import os
import shutil
import subprocess
import sys
import tempfile

from setuptools.command.build_ext import build_ext
from setuptools import Extension, setup

LIBNFS_SOURCE = os.path.join("src", "libnfs")


class BuildNFSExt(build_ext):
    def build_extension(self, ext):
        # Add option to link dynamically for packaging systems such as conda.
        # Always link dynamically on readthedocs to simplify install.
        if os.getenv("LIBNFS_LINK_DYNAMIC"):
            # Check for libnfs include directories. This is useful when
            # installing in a conda environment.
            possible_prefixes = [sys.exec_prefix, sys.base_exec_prefix]
            for prefix in possible_prefixes:
                if os.path.exists(os.path.join(prefix, "include", "nfsc")):
                    ext.include_dirs = [os.path.join(prefix, "include")]
                    ext.library_dirs = [os.path.join(prefix, "lib")]
                    break   # Only one include directory is needed.
            ext.libraries = ["nfs"]
        else:
            libnfs_build_dir = build_libnfs()
            ext.extra_objects = [
                os.path.join(libnfs_build_dir, "lib", "libnfs.a")]
            ext.include_dirs = [
                os.path.join(libnfs_build_dir, "prefix", "include")
            ]
        super().build_extension(ext)


def build_libnfs():
    # Creating temporary directories
    build_dir = tempfile.mktemp()
    shutil.copytree(LIBNFS_SOURCE, build_dir)
    prefix_dir = os.path.join(build_dir, "prefix")
    os.mkdir(prefix_dir)


    # Build environment is a copy of OS environment to allow user to influence
    # it.
    build_env = os.environ.copy()
    build_env["CFLAGS"] = build_env.get("CFLAGS", "") + " -fPIC"
    subprocess.run(
        [
            "cmake",
            "--install-prefix", prefix_dir,
            "-DCMAKE_BUILD_TYPE=Release",
            "-DBUILD_SHARED_LIBS=OFF",
            build_dir
        ],
                   cwd=build_dir, env=build_env, check=True)
    subprocess.run(["make", "-j", "nfs"],
                   cwd=build_dir, env=build_env, check=True)
    subprocess.run(["make", "-j", "install"],
                   cwd=build_dir, env=build_env, check=True)
    return build_dir


setup(
    ext_modules=[
        Extension(
            "nfs_usage_utils._nfs", ["src/nfs_usage_utils/_nfsmodule.c"]),
    ],
    cmdclass = {"build_ext": BuildNFSExt},
)
