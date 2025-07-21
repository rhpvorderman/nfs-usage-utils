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
    tp->tp_free(self);
}

static PyObject *
NFSMount__new__(PyTypeObject *type, PyObject *args, PyObject *kwargs) 
{
    PyObject *url = NULL;
    static char *format = "U|:NFSMount.__new__";
    static char *keywords[] = {"url", NULL};
    if (!PyArg_ParseTupleAndKeywords(
        args, kwargs, format, keywords,
        &url)) {
            return NULL;
        }

    NFSMount *self = PyObject_New(NFSMount, type);
    self->context = NULL;
    self->url = NULL;
    self->context = nfs_init_context();
    if (self->context == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "Failed to create context");
        return NULL;
    }
    self->url = nfs_parse_url_dir(self->context, PyUnicode_AsUTF8(url));
    if (self->url == NULL) {
        PyErr_Format(PyExc_RuntimeError, "Failed to parse URL: %R", url);
        return NULL;
    } 
    
    int ret = nfs_mount(self->context, self->url->server, self->url->path);
    if (ret != 0) {
        PyErr_SetString(PyExc_IOError, nfs_get_error(self->context));
        return NULL;
    }
    return (PyObject *)self; 
}

static PyObject *
NFSMount_close(NFSMount *self, PyObject *args) {
    struct nfs_context *context = self->context;
    if (context == NULL) {
        Py_RETURN_NONE;
    }
    nfs_umount(context);
    Py_RETURN_NONE;
}

static PyObject *
NFSMount_enter(NFSMount *self, PyObject *args) {
    return Py_NewRef(self);
}

static PyObject *
NFSMount_exit(NFSMount *self, PyObject *args) {
    return NFSMount_close(self, args);
}

static PyMethodDef NFSMount_methods[] = {
    {"close", (PyCFunction)NFSMount_close, METH_NOARGS, NULL},
    {"__enter__", (PyCFunction)NFSMount_enter, METH_NOARGS, NULL},
    {"__exit__", (PyCFunction)NFSMount_exit, METH_VARARGS, NULL},
    {NULL},
};

static PyTypeObject NFSMount_Type = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "_nfs.NFSMount", 
    .tp_basicsize = sizeof(NFSMount),
    .tp_dealloc = (destructor)NFSMount_dealloc,
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_new = (newfunc)NFSMount__new__,
    .tp_methods = NFSMount_methods,
};


typedef struct NFSDirEntry_struct {
    PyObject_HEAD
    PyObject *name;
    PyObject *path;
    uint64_t inode;
    uint32_t type;
    uint32_t mode;
    uint64_t size;
    uint32_t uid;
    uint32_t gid;
    uint32_t nlink;
    uint64_t dev;
    uint64_t rdev;
    uint64_t blksize;
    uint64_t blocks;
    double atime;
    double mtime;
    double ctime;
} NFSDirEntry;

static void 
NFSDirEntry_dealloc(NFSDirEntry *self) 
{
    PyTypeObject *tp = Py_TYPE(self);
    Py_XDECREF(self->name);
    Py_XDECREF(self->path);
    tp->tp_free(self);
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
    {"st_ino", T_ULONGLONG, offsetof(NFSDirEntry, inode), READONLY, NULL},
    {"type", T_UINT, offsetof(NFSDirEntry, type), READONLY,
     "Type information as returned by NFS READDIR call. "
     "Can be checked using the constants  NF4REG, NF4DIR etc."},
    {"st_mode", T_UINT, offsetof(NFSDirEntry, mode), READONLY, NULL },
    {"st_size", T_ULONGLONG, offsetof(NFSDirEntry, size), READONLY, NULL},
    {"st_uid", T_UINT, offsetof(NFSDirEntry, uid), READONLY, NULL},
    {"st_gid", T_UINT, offsetof(NFSDirEntry, gid), READONLY, NULL},
    {"st_nlink", T_UINT, offsetof(NFSDirEntry, nlink), READONLY, NULL},
    {"st_dev", T_ULONGLONG, offsetof(NFSDirEntry, dev), READONLY, NULL},
    {"st_rdev", T_ULONGLONG, offsetof(NFSDirEntry, rdev), READONLY, NULL},
    {"st_blksize", T_ULONGLONG, offsetof(NFSDirEntry, blksize), READONLY, NULL},
    {"st_blocks", T_ULONGLONG, offsetof(NFSDirEntry, blocks), READONLY, NULL},
    {"st_atime", T_DOUBLE, offsetof(NFSDirEntry, atime), READONLY, NULL},
    {"st_mtime", T_DOUBLE, offsetof(NFSDirEntry, mtime), READONLY, NULL},
    {"st_ctime", T_DOUBLE, offsetof(NFSDirEntry, ctime), READONLY, NULL},
    {NULL,},
};

static PyObject *
NFSDirEntry_is_file(NFSDirEntry *self, PyObject *args)
{
    /* Constants are the same in current source. Do a compile time check and
       use one of them for the comparison, with a not-implemented fallback if
       the libnfs implementation changes. */
    #if NF2REG == NF3REG && NF3REG == NF4REG
    return PyBool_FromLong(self->type == NF4REG);
    #else
    PyErr_SetString(PyExc_NotImplementedError, "is_file not implemented");
    #endif
}


static PyObject *
NFSDirEntry_is_dir(NFSDirEntry *self, PyObject *args)
{
    /* Constants are the same in current source. Do a compile time check and
       use one of them for the comparison, with a not-implemented fallback if
       the libnfs implementation changes. */
    #if NF2DIR == NF3DIR && NF3DIR == NF4DIR
    return PyBool_FromLong(self->type == NF4DIR);
    #else
    PyErr_SetString(PyExc_NotImplementedError, "is_dir not implemented");
    #endif
}

static PyObject *
NFSDirEntry_is_symlink(NFSDirEntry *self, PyObject *args)
{
    /* Constants are the same in current source. Do a compile time check and
       use one of them for the comparison, with a not-implemented fallback if
       the libnfs implementation changes. */
    #if NF2LNK == NF3LNK && NF3LNK == NF4LNK
    return PyBool_FromLong(self->type == NF4LNK);
    #else
    PyErr_SetString(PyExc_NotImplementedError, "is_symlink not implemented");
    #endif
}

static PyObject *NFSDirEntry_inode(NFSDirEntry *self, PyObject *args)
{
    return PyLong_FromUnsignedLongLong(self->inode);
}

static PyMethodDef NFSDirEntry_methods[] = {
    {"is_dir", (PyCFunction)NFSDirEntry_is_dir, METH_NOARGS, 
     "Return true if the entry is a directory; does NOT follow symlinks."},
    {"is_file", (PyCFunction)NFSDirEntry_is_file, METH_NOARGS, 
     "Return true if the entry is a directory; does NOT follow symlinks."},
    {"is_symlink", (PyCFunction)NFSDirEntry_is_symlink, METH_NOARGS,
     "Return true if the entry is a directory."},
    {"inode", (PyCFunction)NFSDirEntry_inode, METH_NOARGS, 
     "Return the inode of the entry; same as entry.st_ino."},
    {NULL},
};

static PyTypeObject NFSDirEntry_Type = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "_nfs.NFSDirEntry",
    .tp_basicsize = sizeof(NFSDirEntry),
    .tp_dealloc = (destructor)NFSDirEntry_dealloc,
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_DISALLOW_INSTANTIATION,
    .tp_members =  NFSDirEntry_members,
    .tp_methods = NFSDirEntry_methods,
};


static PyObject *
NFSDirEntry_from_dirpath_and_dirent(PyObject *dirpath, struct nfsdirent *dirent)
{
    NFSDirEntry *self = PyObject_New(NFSDirEntry, &NFSDirEntry_Type);
    if (self == NULL) {
        return NULL;
    }
    PyObject *name = PyUnicode_FromString(dirent->name);
    if (name == NULL) {
        return NULL;
    }

    PyObject *path = PyUnicode_FromFormat("%S/%S", dirpath, name);

    if (path == NULL) {
        return NULL;
    }
    self->name = name;
    self->path = path;
    self->inode = dirent->inode;
    self->type = dirent->type;
    self->mode = dirent->mode;
    self->size = dirent->size;
    self->uid = dirent->uid, 
    self->gid = dirent->gid,
    self->nlink = dirent->nlink, 
    self->dev = dirent->dev;
    self->rdev = dirent->rdev;
    self->blksize = dirent->blksize;
    self->blocks = dirent->blocks;
    self->atime = (double)(dirent->atime.tv_sec) + 1e-9 * (double)(dirent->atime_nsec);
    self->mtime = (double)(dirent->mtime.tv_sec) + 1e-9 * (double)(dirent->mtime_nsec);
    self->ctime = (double)(dirent->ctime.tv_sec) + 1e-9 * (double)(dirent->ctime_nsec);
    return (PyObject *)self;
}


typedef struct ScandirIterator_struct {
    PyObject_HEAD
    PyObject *nfs_mount;
    PyObject *path;
    struct nfs_context *context;
    struct nfsdir *dirp;
} ScandirIterator;

static void
ScandirIterator_dealloc(ScandirIterator *iterator)
{
    PyTypeObject *tp = Py_TYPE(iterator);
    Py_XDECREF(iterator->nfs_mount);
    Py_XDECREF(iterator->path);
    tp->tp_free(iterator);
}

static void
ScandirIterator_closedir(ScandirIterator *iterator)
{
    struct nfsdir *dirp = iterator->dirp;

    if (!dirp) {
        return;
    }
    iterator->dirp = NULL;
    Py_BEGIN_ALLOW_THREADS
    nfs_closedir(iterator->context, dirp);
    Py_END_ALLOW_THREADS
    return;
}

static PyObject *
ScandirIterator_iternext(ScandirIterator *iterator) 
{
    if (!iterator->dirp) {
        return NULL;
    }
    
    while (1) {
        struct nfsdirent *entry = nfs_readdir(iterator->context, iterator->dirp);
        if (entry == NULL) {
            break;
        }
        char *name = entry->name;
        size_t name_length = strlen(name); 
        if (name[0] == '.') {
            if (name_length == 1) {
                continue;
            }
            if (name_length == 2 && name[1] == '.') {
                continue;
            }
        }
        return NFSDirEntry_from_dirpath_and_dirent(iterator->path, entry);
    }
    ScandirIterator_closedir(iterator);
    return NULL;
}

static PyObject *
ScandirIterator_close(ScandirIterator *self, PyObject *args)
{
    ScandirIterator_closedir(self);
    Py_RETURN_NONE;
}

static PyObject *
ScandirIterator_enter(PyObject *self, PyObject *args)
{
    Py_INCREF(self);
    return self;
}

static PyObject *
ScandirIterator_exit(ScandirIterator *self, PyObject *args)
{
    ScandirIterator_closedir(self);
    Py_RETURN_NONE;
}

static PyMethodDef ScandirIterator_methods[] = {
    {"__enter__", (PyCFunction)ScandirIterator_enter, METH_NOARGS},
    {"__exit__", (PyCFunction)ScandirIterator_exit, METH_VARARGS},
    {"close", (PyCFunction)ScandirIterator_close, METH_NOARGS},
    {NULL}
};


static PyTypeObject ScandirIterator_Type = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "_nfs.ScandirIterator",
    .tp_basicsize = sizeof(ScandirIterator),
    .tp_dealloc = (destructor)ScandirIterator_dealloc,
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_DISALLOW_INSTANTIATION,
    .tp_iter = PyObject_SelfIter,
    .tp_iternext = (iternextfunc)ScandirIterator_iternext,
    .tp_methods = ScandirIterator_methods,
};

PyDoc_STRVAR(_nfs_scandir__doc__,
"scandir($module, nfs_mount, /, path=None)\n"
"--\n"
"\n"
"Return an iterator of NfsDirEntry objects for given path on given nfs_mount.\n"
"\n"
"nfs_mount must be an initialized, unclosed NFSMount object."
"path can be specified as either str, or a path-like object.\n"
"\n"
"If path is None, uses the path=\'/\'.");

static PyObject *
scandir(PyObject *module, PyObject *args, PyObject *kwargs) 
{
    PyObject *nfs_mount = NULL;
    PyObject *path_in = NULL; 
    static char *format = "O!|O:scandir";
    static char *keywords[] = {"nfs_mount", "path", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, format, keywords, 
     &NFSMount_Type, &nfs_mount, &path_in)) {
        return NULL;
    }
    PyObject *path;
    if (path_in == NULL) {
        path = PyUnicode_DecodeASCII("/", 1, NULL);
    } else {
        path = PyOS_FSPath(path_in);
    }
    if (path == NULL) {
        return NULL;
    }
    /* No supporting of bytes. */
    if (PyBytes_Check(path)) {
        PyErr_Format(PyExc_TypeError, "Path should be a string, not bytes: %R", path_in);
        return NULL;
    }

    ScandirIterator *iterator = PyObject_New(ScandirIterator, &ScandirIterator_Type);
    if (iterator == NULL) {
        return NULL;
    }
    struct nfs_context *context = ((NFSMount *)nfs_mount)->context;
    struct nfsdir *dirp = NULL;
    int ret;
    Py_BEGIN_ALLOW_THREADS
    ret = nfs_opendir(context, PyUnicode_AsUTF8(path), &dirp);
    Py_END_ALLOW_THREADS
    if (ret < 0) {
        PyErr_SetString(PyExc_IOError, nfs_get_error(context));
    }
    iterator->nfs_mount = Py_NewRef(nfs_mount);
    iterator->context = context;
    iterator->path = path;
    iterator->dirp = dirp;
    return (PyObject *)iterator;
}

static PyMethodDef _nfs_methods[] = {
    {"scandir", (PyCFunction)scandir, METH_VARARGS | METH_KEYWORDS, 
     _nfs_scandir__doc__},
    {NULL},
};

static struct PyModuleDef _nfs_module = {
    PyModuleDef_HEAD_INIT,
    "_nfs",   /* name of module */
    NULL, /* module documentation, may be NULL */
    0,
    _nfs_methods,
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

    if (PyModule_AddType(m, &ScandirIterator_Type)) {
        return NULL;
    }

    PyModule_AddIntMacro(m, NFS_V2);
    PyModule_AddIntMacro(m, NFS_V3);
    PyModule_AddIntMacro(m, NFS_V4);

    PyModule_AddIntMacro(m, NF4REG);
    PyModule_AddIntMacro(m, NF4DIR);
    PyModule_AddIntMacro(m, NF4BLK);
    PyModule_AddIntMacro(m, NF4CHR);
    PyModule_AddIntMacro(m, NF4LNK);
    PyModule_AddIntMacro(m, NF4SOCK);
    PyModule_AddIntMacro(m, NF4FIFO);
    PyModule_AddIntMacro(m, NF4ATTRDIR);
    PyModule_AddIntMacro(m, NF4NAMEDATTR);

    PyModule_AddIntMacro(m, NF3REG);
    PyModule_AddIntMacro(m, NF3DIR);
    PyModule_AddIntMacro(m, NF3BLK);
    PyModule_AddIntMacro(m, NF3CHR);
    PyModule_AddIntMacro(m, NF3LNK);
    PyModule_AddIntMacro(m, NF3SOCK);
    PyModule_AddIntMacro(m, NF3FIFO);

    PyModule_AddIntMacro(m, NF2NON);
    PyModule_AddIntMacro(m, NF2REG);
    PyModule_AddIntMacro(m, NF2DIR);
    PyModule_AddIntMacro(m, NF2BLK);
    PyModule_AddIntMacro(m, NF2CHR);
    PyModule_AddIntMacro(m, NF2LNK);

    return m;
}
