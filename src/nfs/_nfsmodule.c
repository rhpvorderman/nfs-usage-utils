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

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "structmember.h"

#include <nfsc/libnfs-raw-nfs.h>
#include <nfsc/libnfs-raw-nfs4.h>
#include <nfsc/libnfs.h>

// typedef struct NFSStat_struct {
//     PyObject_HEAD;
//     struct nfs_stat_64 stat; 
// } NFSStat;

// static void 
// NFSStat_dealloc(NFSStat *self) 
// {
//     PyTypeObject *tp = Py_TYPE(self);
//     freefunc free_func = PyType_GetSlot(tp, Py_tp_free);
//     free_func(self);
//     Py_DECREF(tp);
// }

// static PyMemberDef NFSStat_members[] = {

// };

typedef struct NFSMount_struct {
    PyObject_HEAD
    struct nfs_context *context;
    struct nfs_url *url;
} NFSMount;

static void NFSMount_dealloc(NFSMount *self) 
{
    PyTypeObject *tp = Py_TYPE(self);
    if (self->context != NULL) {
        nfs_destroy_context(self->context);
    }
    if (self->url != NULL) {
        nfs_destroy_url(self->url);
    }
    freefunc free_func = PyType_GetSlot(tp, Py_tp_free);
    free_func(self);
    Py_DECREF(tp);
}

static PyObject *
NFSMount__new__(PyTypeObject *type, PyObject *args, PyObject *kwargs) 
{
    PyObject *url = NULL;
    static char *format = "U|IIi:NFSMount.__new__";
    static char *keywords[] = {"url", NULL};
    if (PyArg_ParseTupleAndKeywords(
        args, kwargs, format, keywords,
        &url) < 0) {
            return NULL;
        }
    if (!PyUnicode_IS_COMPACT_ASCII(url)) {
        PyErr_Format(
            PyExc_ValueError, 
            "url must be an ASCII only string. Got %R", 
            url
        );
        return NULL;
    }
    NFSMount *self = PyObject_New(NFSMount, type);
    self->context = NULL;
    self->url = NULL;
    self->context = nfs_init_context();
    if (self->context == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "Failed to create context");
    }
    self->url = nfs_parse_url_dir(self->context, PyUnicode_DATA(url));
    if (self->url == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "Failed to parse URL.");
    } 
    
    int ret = nfs_mount(self->context, self->url->server, self->url->path);
    if (ret != 0) {
        PyErr_SetString(PyExc_IOError, nfs_get_error(self->context));
        return NULL;
    }
    return (PyObject *)self; 
}

static PyTypeObject NFSMount_Type = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "_nfs.NFSMount", 
    .tp_basicsize = sizeof(NFSMount),
    .tp_dealloc = (destructor)NFSMount_dealloc,
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_new = NFSMount__new__,
};


typedef struct NFSDirEntry_struct {
    PyObject_HEAD
    PyObject *name;
    PyObject *path;
    struct nfsdirent entry;
} NFSDirEntry;

static void 
NFSDirEntry_dealloc(NFSDirEntry *self) 
{
    PyTypeObject *tp = Py_TYPE(self);
    Py_XDECREF(self->name);
    Py_XDECREF(self->path);
    freefunc free_func = PyType_GetSlot(tp, Py_tp_free);
    free_func(self);
    Py_DECREF(tp);
}

#define DIRENT_OFFSET(x) (offsetof(NFSDirEntry, entry) + offsetof(struct nfsdirent, x))

static PyMemberDef NFSDirEntry_members[] = {
    {
        "name", T_OBJECT_EX, offsetof(NFSDirEntry, name), READONLY,
        "the entry's base filename, relative to scandir() \"path\" argument"
    },
    {
        "path", T_OBJECT_EX, offsetof(NFSDirEntry, path), READONLY,
        "the entry's full path name; equivalent to "
        "os.path.join(scandir_path, entry.name)"
    },
    {"st_ino", T_ULONGLONG, DIRENT_OFFSET(inode), READONLY, NULL},
    {"type", T_UINT, DIRENT_OFFSET(type), READONLY, NULL},
    {"st_mode", T_UINT, DIRENT_OFFSET(mode), READONLY, NULL },
    {"st_size", T_ULONGLONG, DIRENT_OFFSET(size), READONLY, NULL},
    {"st_uid", T_UINT, DIRENT_OFFSET(uid), READONLY, NULL},
    {"st_gid", T_UINT, DIRENT_OFFSET(gid), READONLY, NULL},
    {"st_nlink", T_UINT, DIRENT_OFFSET(nlink), READONLY, NULL},
    {"st_dev", T_ULONGLONG, DIRENT_OFFSET(dev), READONLY, NULL},
    {"st_rdev", T_ULONGLONG, DIRENT_OFFSET(rdev), READONLY, NULL},
    {"st_blksize", T_ULONGLONG, DIRENT_OFFSET(blksize), READONLY, NULL},
    {"st_blocks", T_ULONGLONG, DIRENT_OFFSET(blocks), READONLY, NULL},
    {"st_atime_ns", T_UINT, DIRENT_OFFSET(atime_nsec), READONLY, NULL},
    {"st_mtime_ns", T_UINT, DIRENT_OFFSET(mtime_nsec), READONLY, NULL},
    {"st_ctime_ns", T_UINT, DIRENT_OFFSET(ctime_nsec), READONLY, NULL}, 
    {NULL,}
};

static PyTypeObject NFSDirEntry_Type = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "_nfs.NFSDirEntry",
    .tp_basicsize = sizeof(NFSDirEntry),
    .tp_dealloc = (destructor)NFSDirEntry_dealloc,
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_DISALLOW_INSTANTIATION,
    .tp_members =  NFSDirEntry_members,
};


static struct PyModuleDef _nfs_module = {
    PyModuleDef_HEAD_INIT,
    "_nfs",   /* name of module */
    NULL, /* module documentation, may be NULL */
    0,
    NULL,
};

PyMODINIT_FUNC
PyInit__nfs(void)
{
    PyObject *m = PyModule_Create(&_nfs_module);
    if (m == NULL) {
        return NULL;
    }
    if (PyModule_AddType(m, &NFSDirEntry_Type) < 0) {
        return NULL;
    }
    if (PyModule_AddType(m, &NFSMount_Type) < 0) {
        return NULL;
    }

    return m;
}
