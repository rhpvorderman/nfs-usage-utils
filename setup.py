# Copyright (c) 2020 Leiden University Medical Center
# Copyright (c) 2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009, 2010,
# 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022
# Python Software Foundation; All Rights Reserved

# This file is part of python-isal which is distributed under the
# PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2.

from setuptools import Extension, setup

setup(
    ext_modules=[
        Extension("nfs._nfs", ["src/nfs/_nfsmodule.c"]),
    ]
)
