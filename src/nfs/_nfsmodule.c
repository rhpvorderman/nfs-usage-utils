/*
Copyright (C) 2025 Leiden University Medical Center
This file is part of nfs-usage-utils

nfs-usage-utils is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as
published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

nfs-usage-utils is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with nfs-usage-utils.  If not, see <https://www.gnu.org/licenses/
*/

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "structmember.h"

#include <nfsc/libnfs-raw-nfs4.h>
#include <nfsc/libnfs.h>

static PyObject *
nfs_error_to_python_error(int nfs_error) {
    /* See https://datatracker.ietf.org/doc/html/rfc7530#section-13 */
    switch (nfs_error) {
        case NFS4ERR_EXIST:
            return PyExc_FileExistsError;
        case NFS4ERR_ISDIR:
            return PyExc_IsADirectoryError;
        case NFS4ERR_NOTDIR:
            return PyExc_NotADirectoryError;
        case NFS4ERR_NOENT:
            return PyExc_FileNotFoundError;
        case NFS4ERR_ACCESS:
        case NFS4ERR_PERM:
            return PyExc_PermissionError;
        case NFS4ERR_BADCHAR:
        case NFS4ERR_NAMETOOLONG:
            return PyExc_ValueError;
        default:
            return PyExc_OSError;
    }
}

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
    nfs_set_version(self->context, NFS_V4);
    self->url = nfs_parse_url_dir(self->context, PyUnicode_AsUTF8(url));
    if (self->url == NULL) {
        PyErr_Format(PyExc_ValueError, "Invalid URL: %R", url);
        return NULL;
    } 
    
    int ret = nfs_mount(self->context, self->url->server, self->url->path);
    if (ret != 0) {
        PyErr_SetString(nfs_error_to_python_error(-ret), nfs_get_error(self->context));
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

PyDoc_STRVAR(NFSMount_service__doc__,
"service($self, revents, /)\n"
"--\n"
"\n"
"Service the revents on the socket."
"\n"
"  revents\n"
"    bitmask as reported by select.poll on the file descriptor.\n"
);

static PyObject *
NFSMount_service(NFSMount *self, PyObject *revents_obj)
{
    if (!PyLong_CheckExact(revents_obj)) {
        PyErr_Format(
            PyExc_TypeError,
            "revents should be an int object, got %s", 
            Py_TYPE(revents_obj)->tp_name
        );
        return NULL;
    }
    int revents = PyLong_AsLong(revents_obj);
    int ret = nfs_service(self->context, revents);
    if (ret != 0) {
        PyErr_SetString(
            nfs_error_to_python_error(-ret), 
            nfs_get_error(self->context)
        );
        return NULL;
    }
    Py_RETURN_NONE;
}

PyDoc_STRVAR(NFSMount_get_fd__doc__,
"get_fd($self, /)\n"
"--\n"
"\n"
"Get the socket file descriptor for usage in select.poll\n"
);

static PyObject *
NFSMount_get_fd(NFSMount *self, PyObject *args) 
{
    return PyLong_FromLong(nfs_get_fd(self->context));
}

PyDoc_STRVAR(NFSMount_which_events__doc__,
"which_events($self, /)\n"
"--\n"
"\n"
"Returns which events need polling.\n"
"This is a combination of the POLLIN and POLLOUT flags.\n"
);

static PyObject *
NFSMount_which_events(NFSMount *self, PyObject *args) 
{
    return PyLong_FromLong(nfs_which_events(self->context));
}

PyDoc_STRVAR(NFSMount_queue_length__doc__,
"queue_length($self, /)\n"
"--\n"
"\n"
"Returns the number of commands in-flight. Can be used by the application\n"
"to check if there are any more responses awaiting for the server\n"
"or if the connection is completely idle.\n"
);

static PyObject *
NFSMount_queue_length(NFSMount *self, PyObject *args) 
{
    return PyLong_FromLong(nfs_queue_length(self->context));
}

static PyMethodDef NFSMount_methods[] = {
    {"close", (PyCFunction)NFSMount_close, METH_NOARGS, NULL},
    {"__enter__", (PyCFunction)NFSMount_enter, METH_NOARGS, NULL},
    {"__exit__", (PyCFunction)NFSMount_exit, METH_VARARGS, NULL},
    {"service", (PyCFunction)NFSMount_service, METH_O,
     NFSMount_service__doc__},
    {"get_fd", (PyCFunction)NFSMount_get_fd, METH_NOARGS, NFSMount_get_fd__doc__},
    {"which_events", (PyCFunction)NFSMount_which_events, METH_NOARGS, 
     NFSMount_which_events__doc__},
    {"queue_length", (PyCFunction)NFSMount_queue_length, METH_NOARGS, 
     NFSMount_queue_length__doc__},
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
    Py_ssize_t dirpath_length = PyUnicode_GET_LENGTH(dirpath);
    PyObject *path;
    if (PyUnicode_IS_COMPACT_ASCII(dirpath) && PyUnicode_IS_COMPACT_ASCII(name)) {
        /* ASCII Path names are the most common so use an optimal code path. */
        Py_ssize_t name_length = PyUnicode_GET_LENGTH(name);
        char *dirpath_ptr = PyUnicode_DATA(dirpath);
        char *name_ptr = PyUnicode_DATA(name);
        if (dirpath_ptr[dirpath_length - 1] == '/') {
            dirpath_length -= 1;
        }
        path = PyUnicode_New(dirpath_length + name_length + 1, 127);
        if (path == NULL) {
            return NULL;
        }
        char *path_ptr = PyUnicode_DATA(path);
        memcpy(path_ptr, dirpath_ptr, dirpath_length);
        path_ptr[dirpath_length] = '/';
        memcpy(path_ptr + dirpath_length + 1, name_ptr, name_length);
    } else {
        Py_UCS4 last_char = PyUnicode_READ_CHAR(dirpath, dirpath_length - 1);
        if (last_char == '/') {
            path = PyUnicode_Concat(dirpath, name);
        } else {
            path = PyUnicode_FromFormat("%S/%S", dirpath, name);
        }
        if (path == NULL) {
            return NULL;
        }
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
    int ready;
    int return_code;
    PyObject *nfs_mount;
    PyObject *path;
    struct nfs_context *context;
    struct nfsdir *dirp;
    char error_message[512];
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

PyDoc_STRVAR(ScandirIterator_ready__doc__, 
"ready($self, /)\n"
"--\n"
"\n"
"When called with scandir_async, check if the iterator is ready. Non-async\n"
"iterators are always ready. When an error was raised by the server calling\n"
"this function will raise that error."
);

static PyObject *
ScandirIterator_ready(ScandirIterator *self, PyObject *args)
{
    if (!self->ready) {
        Py_RETURN_FALSE;
    }
    if (self->return_code != 0) {
        PyErr_SetString(
            nfs_error_to_python_error(-self->return_code),
            self->error_message
        );
        return NULL;
    }
    Py_RETURN_TRUE;
}

static PyMethodDef ScandirIterator_methods[] = {
    {"__enter__", (PyCFunction)ScandirIterator_enter, METH_NOARGS},
    {"__exit__", (PyCFunction)ScandirIterator_exit, METH_VARARGS},
    {"close", (PyCFunction)ScandirIterator_close, METH_NOARGS},
    {"ready", (PyCFunction)ScandirIterator_ready, METH_NOARGS,
     ScandirIterator_ready__doc__},
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

static void 
scandir_async_callback(
    int status, struct nfs_context *context, void *data, void *private_data)
{
    ScandirIterator *iterator = (ScandirIterator *)private_data;
    struct nfsdir *dirp = (struct nfsdir *)data;
    iterator->return_code = status;
    iterator->dirp = dirp;
    if (status != 0) {
        strncpy(
            iterator->error_message, 
            nfs_get_error(context), 
            // -1 because error message is 0 initialized and this way there is
            // always a terminating 0.
            sizeof(iterator->error_message) - 1
        );
    }
    iterator->ready = 1;
}

static PyObject *scandir_impl(
    PyObject *module, PyObject *args, PyObject *kwargs, int async)
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
    iterator->nfs_mount = Py_NewRef(nfs_mount);
    iterator->dirp = NULL;
    memset(iterator->error_message, 0, sizeof(iterator->error_message));
    iterator->ready = 0;
    iterator->return_code = 0;
    iterator->path = path;
    iterator->context = context;
    const char *path_ptr = PyUnicode_AsUTF8(path);
    int ret;
    if (async) {
        ret = nfs_opendir_async(context, path_ptr, scandir_async_callback, iterator);
        if (ret != 0) {
            PyErr_SetString(nfs_error_to_python_error(-ret), nfs_get_error(context));
            return NULL;
        }
    } else {
        struct nfsdir *dirp = NULL;
        Py_BEGIN_ALLOW_THREADS
        ret = nfs_opendir(context, path_ptr, &dirp);
        Py_END_ALLOW_THREADS
        if (ret < 0) {
            PyErr_SetString(nfs_error_to_python_error(-ret), nfs_get_error(context));
            return NULL;
        }
        iterator->dirp = dirp;
        iterator->return_code = ret;
        iterator->ready = 1;
    }
    return (PyObject *)iterator;
}

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
    return scandir_impl(module, args, kwargs, 0);
}


PyDoc_STRVAR(_nfs_scandir_async__doc__,
"scandir_ascync($module, nfs_mount, /, path=None)\n"
"--\n"
"\n"
"Return an iterator of NfsDirEntry objects for given path on given nfs_mount.\n"
"The NFSMount object must be serviced using the service_nfs_mount function \n"
"before the iterator becomes usable."
"\n"
"nfs_mount must be an initialized, unclosed NFSMount object."
"path can be specified as either str, or a path-like object.\n"
"\n"
"If path is None, uses the path=\'/\'.");

static PyObject *
scandir_async(PyObject *module, PyObject *args, PyObject *kwargs) 
{
    return scandir_impl(module, args, kwargs, 1);
}
static PyMethodDef _nfs_methods[] = {
    {"scandir", (PyCFunction)scandir, METH_VARARGS | METH_KEYWORDS, 
     _nfs_scandir__doc__},
    {"scandir_async", (PyCFunction)scandir_async, METH_VARARGS | METH_KEYWORDS, 
     _nfs_scandir_async__doc__},
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

    return m;
}
