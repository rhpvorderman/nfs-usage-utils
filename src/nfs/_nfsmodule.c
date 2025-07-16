/*
Copyright (c) 2025 Leiden University Medical Center

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
*/

#define Py_LIMITED_API 0x030B0000
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "structmember.h"

#include <nfsc/libnfs-raw.h>
#include <nfsc/libnfs.h>


typedef struct NfsStat_struct {
    PyObject_HEAD;
    struct nfs_stat_64 stat; 
} NfsStat;

static void 
NfsStat_dealloc(NfsStat *self) 
{
    PyTypeObject *tp = Py_TYPE(self);
    freefunc free_func = PyType_GetSlot(tp, Py_tp_free);
    free_func(self);
    Py_DECREF(tp);
}

static PyMemberDef NfsStat_members[] = {

};


typedef struct NfsDirEntry_struct {
    PyObject_HEAD
    PyObject *name;
    PyObject *path;
    PyObject *stat;
} NfsDirEntry;

static void 
NfsDirEntry_dealloc(NfsDirEntry *self) 
{
    PyTypeObject *tp = Py_TYPE(self);
    Py_XDECREF(self->name);
    Py_XDECREF(self->path);
    Py_XDECREF(self->stat);
    freefunc free_func = PyType_GetSlot(tp, Py_tp_free);
    free_func(self);
    Py_DECREF(tp);
}

static PyMemberDef NfsDirEntry_members[] = {
    {"name", T_OBJECT_EX, offsetof(NfsDirEntry, name), READONLY,
     "the entry's base filename, relative to scandir() \"path\" argument"
    },
    {"path", T_OBJECT_EX, offsetof(NfsDirEntry, path), READONLY,
     "the entry's base filename, relative to scandir() \"path\" argument"
    },

    {NULL,}
};


int main() {
}


