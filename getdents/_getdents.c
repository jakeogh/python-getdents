#include <Python.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stddef.h>
#include <stdbool.h>
#include <stdio.h>
#include <unistd.h>
#include <stdlib.h>
#include <time.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/time.h>
#define SHUFFLE_IMPLEMENTATION
#include "shuffle.h"

struct linux_dirent64 {
    uint64_t        d_ino;      /* 64-bit inode number */
    int64_t         d_off;      /* 64-bit offset to next structure */
    unsigned short  d_reclen;   /* Size of this dirent */
    unsigned char   d_type;     /* File type */
    char            d_name[];   /* Filename (null-terminated) */
};

struct getdents_state {
    PyObject_HEAD
    char      *buff;
    Py_ssize_t bpos;
    int        fd;
    int        rand;
    Py_ssize_t nread;
    size_t     buff_size;
};

#ifndef O_GETDENTS
# define O_GETDENTS (O_DIRECTORY | O_RDONLY | O_NONBLOCK | O_CLOEXEC)
#endif

#ifndef MIN_GETDENTS_BUFF_SIZE
# define MIN_GETDENTS_BUFF_SIZE (MAXNAMLEN + sizeof(struct linux_dirent64))
#endif

static PyObject *
getdents_new(PyTypeObject *type, PyObject *args, PyObject *kwargs)
{
    Py_ssize_t buff_size;
    int fd;
    int rand = 0;

    // i (int)        -> fd
    // n (Py_ssize_t) -> buff_size
    // |              -> following args optional
    // i (int)        -> rand (validated to 0/1 below)
    if (!PyArg_ParseTuple(args, "in|i", &fd, &buff_size, &rand))
        return NULL;

    struct stat st;
    if (fstat(fd, &st) == -1) {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }
    if (!S_ISDIR(st.st_mode)) {
        PyErr_SetString(
            PyExc_NotADirectoryError,
            "fd must refer to a directory"
        );
        return NULL;
    }

    if (buff_size < (Py_ssize_t) MIN_GETDENTS_BUFF_SIZE) {
        PyErr_SetString(
            PyExc_ValueError,
            "buff_size is too small"
        );
        return NULL;
    }

    if (rand != 0 && rand != 1) {
        PyErr_SetString(
            PyExc_ValueError,
            "random must be 0 or 1"
        );
        return NULL;
    }

    struct getdents_state *state =
        (struct getdents_state *) type->tp_alloc(type, 0);

    if (!state)
        return NULL;

    void *buff = malloc((size_t) buff_size);

    if (!buff) {
        Py_DECREF(state);
        return PyErr_NoMemory();
    }

    state->buff = buff;
    state->buff_size = (size_t) buff_size;
    state->fd = fd;
    state->rand = rand;
    state->bpos = 0;
    state->nread = 0;
    return (PyObject *) state;
}

static void
getdents_dealloc(struct getdents_state *state)
{
    free(state->buff);
    Py_TYPE(state)->tp_free(state);
}

/* Shuffle the linux_dirent64 records contained in s->buff in place, using a
 * format-preserving permutation seeded from the wall clock. Operates only on
 * the records of the current syscall batch (s->nread bytes). */
static int
getdents_shuffle_batch(struct getdents_state *s)
{
    if (s->nread <= 0)
        return 0;

    void *random_buff = malloc(s->buff_size);
    if (!random_buff) {
        PyErr_NoMemory();
        return -1;
    }

    /* Upper bound on record count. The smallest representable record is the
     * fixed header plus a 1-byte name and its NUL; using a conservative
     * minimum guarantees we never under-allocate the index arrays. */
    size_t min_reclen = offsetof(struct linux_dirent64, d_name) + 2;
    size_t max_records = (size_t) s->nread / min_reclen + 1;

    char **dents = malloc(max_records * sizeof(char *));
    char **random_dents = malloc(max_records * sizeof(char *));
    if (!dents || !random_dents) {
        free(dents);
        free(random_dents);
        free(random_buff);
        PyErr_NoMemory();
        return -1;
    }

    size_t count = 0;
    Py_ssize_t bpos = 0;
    while (bpos < s->nread) {
        struct linux_dirent64 *dd =
            (struct linux_dirent64 *)(s->buff + bpos);
        if (dd->d_reclen == 0)  /* defensive: avoid infinite loop */
            break;
        dents[count++] = s->buff + bpos;
        bpos += dd->d_reclen;
    }

    struct timeval tv;
    gettimeofday(&tv, NULL);

    struct shuffle_ctx ctx;
    shuffle_init(&ctx, count, (size_t) tv.tv_usec);

    for (size_t i = 0; i < count; ++i)
        random_dents[i] = dents[shuffle_index(&ctx, i)];

    bpos = 0;
    for (size_t i = 0; i < count; ++i) {
        struct linux_dirent64 *dd =
            (struct linux_dirent64 *)(random_dents[i]);
        memcpy(random_buff + bpos, random_dents[i], dd->d_reclen);
        bpos += dd->d_reclen;
    }
    memcpy(s->buff, random_buff, (size_t) s->nread);

    free(dents);
    free(random_dents);
    free(random_buff);
    return 0;
}

static PyObject *
getdents_next(struct getdents_state *s)
{
    if (s->bpos >= s->nread) {
        s->bpos = 0;
        Py_ssize_t nread;
        do {
            errno = 0;
            nread = syscall(SYS_getdents64, s->fd, s->buff, s->buff_size);
        } while (nread == -1 && errno == EINTR);

        if (nread == -1) {
            PyErr_SetFromErrno(PyExc_OSError);
            return NULL;
        }

        s->nread = nread;

        if (s->nread == 0)
            return NULL;  /* StopIteration */

        if (s->rand) {
            if (getdents_shuffle_batch(s) == -1)
                return NULL;
        }
    }

    struct linux_dirent64 *d =
        (struct linux_dirent64 *)(s->buff + s->bpos);

    PyObject *py_name = PyBytes_FromString(d->d_name);
    if (!py_name)
        return NULL;

    PyObject *result = Py_BuildValue("KbO", d->d_ino, d->d_type, py_name);
    Py_DECREF(py_name);

    s->bpos += d->d_reclen;

    return result;
}

PyTypeObject getdents_type = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "getdents_raw",                 /* tp_name */
    sizeof(struct getdents_state),  /* tp_basicsize */
    0,                              /* tp_itemsize */
    (destructor) getdents_dealloc,  /* tp_dealloc */
    0,                              /* tp_print */
    0,                              /* tp_getattr */
    0,                              /* tp_setattr */
    0,                              /* tp_reserved */
    0,                              /* tp_repr */
    0,                              /* tp_as_number */
    0,                              /* tp_as_sequence */
    0,                              /* tp_as_mapping */
    0,                              /* tp_hash */
    0,                              /* tp_call */
    0,                              /* tp_str */
    0,                              /* tp_getattro */
    0,                              /* tp_setattro */
    0,                              /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT,             /* tp_flags */
    0,                              /* tp_doc */
    0,                              /* tp_traverse */
    0,                              /* tp_clear */
    0,                              /* tp_richcompare */
    0,                              /* tp_weaklistoffset */
    PyObject_SelfIter,              /* tp_iter */
    (iternextfunc) getdents_next,   /* tp_iternext */
    0,                              /* tp_methods */
    0,                              /* tp_members */
    0,                              /* tp_getset */
    0,                              /* tp_base */
    0,                              /* tp_dict */
    0,                              /* tp_descr_get */
    0,                              /* tp_descr_set */
    0,                              /* tp_dictoffset */
    0,                              /* tp_init */
    PyType_GenericAlloc,            /* tp_alloc */
    getdents_new,                   /* tp_new */
};

static struct PyModuleDef getdents_module = {
    PyModuleDef_HEAD_INIT,
    "getdents",                      /* m_name */
    "",                              /* m_doc */
    -1,                              /* m_size */
};

PyMODINIT_FUNC
PyInit__getdents(void)
{
    if (PyType_Ready(&getdents_type) < 0)
        return NULL;

    PyObject *module = PyModule_Create(&getdents_module);

    if (!module)
        return NULL;

    Py_INCREF(&getdents_type);
    if (PyModule_AddObject(module, "getdents_raw",
                           (PyObject *) &getdents_type) < 0) {
        Py_DECREF(&getdents_type);
        Py_DECREF(module);
        return NULL;
    }
    PyModule_AddIntMacro(module, DT_BLK);
    PyModule_AddIntMacro(module, DT_CHR);
    PyModule_AddIntMacro(module, DT_DIR);
    PyModule_AddIntMacro(module, DT_FIFO);
    PyModule_AddIntMacro(module, DT_LNK);
    PyModule_AddIntMacro(module, DT_REG);
    PyModule_AddIntMacro(module, DT_SOCK);
    PyModule_AddIntMacro(module, DT_UNKNOWN);
    PyModule_AddIntMacro(module, O_GETDENTS);
    PyModule_AddIntMacro(module, MIN_GETDENTS_BUFF_SIZE);
    return module;
}
