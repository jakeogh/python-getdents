#include <Python.h>
#include <dirent.h>
#include <fcntl.h>
#include <stddef.h>
#include <stdbool.h>
#include <stdio.h>
#include <unistd.h>
#include <stdlib.h>
#include <time.h>
#include <sys/stat.h>
#include <sys/syscall.h>
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
    char  *buff;
    int    bpos;
    int    fd;
    int    rand;
    int    nread;
    size_t buff_size;
    bool   ready_for_next_batch;
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
    size_t buff_size;
    int fd;
    int rand;

    // https://docs.python.org/3/c-api/arg.html#c.PyArg_ParseTuple
    if (!PyArg_ParseTuple(args, "ini", &fd, &buff_size, &rand))
        return NULL;

    if (!(fcntl(fd, F_GETFL) & O_DIRECTORY)) {
        PyErr_SetString(
            PyExc_NotADirectoryError,
            "fd must be opened with O_DIRECTORY flag"
        );
        return NULL;
    }

    if (buff_size < MIN_GETDENTS_BUFF_SIZE) {
        PyErr_SetString(
            PyExc_ValueError,
            "buff_size is too small"
        );
        return NULL;
    }

    //fprintf(stderr, "rand: %d\n", rand);
    if ((rand != 1) & (rand != 0)) {
        PyErr_SetString(
            PyExc_ValueError,
            "random must be 0 or 1"
        );
        return NULL;
    }

    struct getdents_state *state = (void *) type->tp_alloc(type, 0);

    if (!state)
        return NULL;

    void *buff = malloc(buff_size);

    if (!buff)
        return PyErr_NoMemory();

    state->buff = buff;
    state->buff_size = buff_size;
    state->fd = fd;
    state->rand = rand;
    state->bpos = 0;
    state->nread = 0;
    state->ready_for_next_batch = true;
    return (PyObject *) state;
}

static void
getdents_dealloc(struct getdents_state *state)
{
    free(state->buff);
    Py_TYPE(state)->tp_free(state);
}

static PyObject *
getdents_next(struct getdents_state *s)
{
    // bool s->ready_for_next_batch
    // int  s->bpos
    // int  s->nread
    s->ready_for_next_batch = s->bpos >= s->nread;

    if (s->ready_for_next_batch) {
        s->bpos = 0;
        // man getdents64:
        //     int getdents64(unsigned int fd, struct linux_dirent64 *dirp, unsigned int count);  # count is the buffer size
        //         int    s->fd
        //         char*  s->buff  (linux_dirent64 entries)
        //         size_t s->buff_size
        s->nread = syscall(SYS_getdents64, s->fd, s->buff, s->buff_size);
        //         int    s->nread (number of bytes read)

        if (s->nread == 0)
            return NULL;

        if (s->nread == -1) {
            PyErr_SetString(PyExc_OSError, "getdents64");
            return NULL;
        }

        if (s->rand) {
            void *buff = malloc(s->buff_size);
            if (!buff)
                return PyErr_NoMemory();

            void *random_buff = malloc(s->buff_size);
            if (!random_buff)
                return PyErr_NoMemory();
            // each struct linux_dirent64 in s->buff has a different d->d_reclen

            int bpos = 0;
            int index = 0;
            unsigned long *dents[s->nread/24];  // 24 appears the be the min linux_dirent64 size
            unsigned long *random_dents[s->nread/24];

            // calculate index, the number of dents in the struct
            while(1) {
                struct linux_dirent64 *dd = (struct linux_dirent64 *)(s->buff + bpos);
                //fprintf(stderr, "%p %p %lu %d %hu dd->name: %s\n", &dd, s->buff + bpos, s->buff + bpos, bpos, dd->d_reclen, dd->d_name);
                dents[index] = s->buff + bpos;
                //fprintf(stderr, "%lu\n", dents[index]);
                bpos += dd->d_reclen;
                if (bpos >= s->nread)
                    break;
                index += 1;
            }

            int idx = 0;

            //for (idx=0; idx<=index; idx++) {
            //    fprintf(stderr, "%d %lu\n", idx, dents[idx]);
            //}

            size_t size = index + 1;
            //fprintf(stderr, "size: %d\n", size);

            struct timeval tv;
            gettimeofday(&tv, NULL);
            int usec = tv.tv_usec;

            struct shuffle_ctx ctx;
            //shuffle_init(&ctx, size, 0xBAD5EEED);
            shuffle_init(&ctx, size, usec);

            //size_t i, j, k;
            size_t i, j;
            for (i = 0; i < size; ++i) {
                    j = shuffle_index(&ctx, i);
                    //k = shuffle_index_invert(&ctx, j);
                    //k = 0;
                    //fprintf(stderr, "%2zu %6lu   %2zu %6lu\n", j, dents[j], k, dents[k]);
                    random_dents[i] = dents[j];
            }

            bpos = 0;
            idx = 0;
            for (idx=0; idx<=index; idx++) {
                //fprintf(stderr, "%d %lu\n", idx, random_dents[idx]);
                struct linux_dirent64 *dd = (struct linux_dirent64 *)(random_dents[idx]);
                fprintf(stderr, "%lu %hu dd->name: %s\n", random_dents[idx], dd->d_reclen, dd->d_name);
                memcpy(&random_buff + bpos, random_dents[idx], dd->d_reclen);
                struct linux_dirent64 *ddd = (struct linux_dirent64 *)(&random_buff + bpos);
                fprintf(stderr, "%hu ddd->name: %s\n", ddd->d_reclen, ddd->d_name); //works as expected

                bpos += dd->d_reclen;
                fprintf(stderr, "bpos: %d\n", bpos);
            }
            fprintf(stderr, "about to memcpy\n");
            //memcpy(s->buff, &random_buff, s->nread);
            fprintf(stderr, "after memcpy\n");

            //free(random_buff);
            //free(buff);
            fprintf(stderr, "after frees\n");
        }

    }

    struct linux_dirent64 *d = (struct linux_dirent64 *)(s->buff + s->bpos);
    //printf("nread: %d d_reclen: %d\n", s->nread, d->d_reclen);

    PyObject *py_name = PyBytes_FromString(d->d_name);  // want bytes
//  PyObject *py_name = PyUnicode_DecodeFSDefault(d->d_name);

    // https://docs.python.org/3/c-api/arg.html#c.Py_BuildValue
    // K (int) [unsigned long long]     Convert a C unsigned long long to a Python integer object
    // b (int) [char]                   Convert a plain C char to a Python integer object
    // O (object) [PyObject *]          Pass a Python object untouched (except for its reference count, which is incremented by one)
    PyObject *result = Py_BuildValue("KbO", d->d_ino, d->d_type, py_name);

    // unsigned short  d->d_reclen  //always even
    s->bpos += d->d_reclen;

    return result;
};

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
    PyModule_AddObject(module, "getdents_raw", (PyObject *) &getdents_type);
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
