import sys

import numpy as np

import numba.core.typing.cffi_utils as cffi_support
from numba.tests.support import import_dynamic, temp_directory
from numba.core.types import complex128


def load_inline_module():
    """
    Create an inline module, return the corresponding ffi and dll objects.
    """
    from cffi import FFI

    # We can't rely on libc availability on Windows anymore, so we use our
    # own compiled wrappers (see https://bugs.python.org/issue23606).

    defs = """
    double _numba_test_sin(double x);
    double _numba_test_cos(double x);
    double _numba_test_funcptr(double (*func)(double));
    bool _numba_test_boolean(void);
    """

    ffi = FFI()
    ffi.cdef(defs)
    # Load the _helperlib namespace
    from numba import _helperlib
    return ffi, ffi.dlopen(_helperlib.__file__)


def load_ool_module():
    """
    Compile an out-of-line module, return the corresponding ffi and
    module objects.
    """
    from cffi import FFI

    numba_complex = """
    typedef struct _numba_complex {
        double real;
        double imag;
    } numba_complex;
    """

    bool_define = """
    #ifdef _MSC_VER
        #define false 0
        #define true 1
        #define bool int
    #else
        #include <stdbool.h>
    #endif
    """

    defs = numba_complex + """
    bool boolean(void);
    double sin(double x);
    double cos(double x);
    int foo(int a, int b, int c);
    void vsSin(int n, float* x, float* y);
    void vdSin(int n, double* x, double* y);
    void vector_real(numba_complex *c, double *real, size_t n);
    void vector_imag(numba_complex *c, double *imag, size_t n);
    """

    source = numba_complex + bool_define + """
    static bool boolean(void)
    {
        return true;
    }

    static int foo(int a, int b, int c)
    {
        return a + b * c;
    }

    void vsSin(int n, float* x, float* y) {
        int i;
        for (i=0; i<n; i++)
            y[i] = sin(x[i]);
    }

    void vdSin(int n, double* x, double* y) {
        int i;
        for (i=0; i<n; i++)
            y[i] = sin(x[i]);
    }

    static void vector_real(numba_complex *c, double *real, size_t n) {
        size_t i;
        for (i = 0; i < n; i++)
            real[i] = c[i].real;
    }

    static void vector_imag(numba_complex *c, double *imag, size_t n) {
        size_t i;
        for (i = 0; i < n; i++)
            imag[i] = c[i].imag;
    }
    """

    ffi = FFI()
    ffi.set_source('cffi_usecases_ool', source)
    ffi.cdef(defs, override=True)
    tmpdir = temp_directory('test_cffi')
    ffi.compile(tmpdir=tmpdir)
    sys.path.append(tmpdir)
    try:
        mod = import_dynamic('cffi_usecases_ool')
        cffi_support.register_module(mod)
        cffi_support.register_type(mod.ffi.typeof('struct _numba_complex'),
                                   complex128)
        return mod.ffi, mod
    finally:
        sys.path.remove(tmpdir)


def load_ool_linkedlist():
    from cffi import FFI

    structs = """
    typedef struct Node {
        int32_t value;
        struct Node* next;
    } Node;

    typedef struct Head {
        Node* node;
    } Head;
    """

    declr = """

    Node* find_by_val(int32_t value, Node* node);
    Head* list_new(void);
    void delete_node(Node* node);
    void delete_list(Head* head);
    int32_t list_len(Head* head);
    int32_t list_sum(Head* head);
    void list_append(Head* head, int32_t value);

    """

    impl = """
    Node* find_by_val(int32_t value, Node* node) {
        if (node == NULL) {
            return NULL;
        }
        if (node->value == value) {
            return node;
        }
        return find_by_val(value, node->next);
    }

    Head* list_new(void) {
        Head* head = (Head*)malloc(sizeof(Head));
        head->node = NULL;
        return head;
    }

    void delete_node(Node* node) {
        if (node != NULL) {
            delete_node(node->next);
            free(node);
        }
    }

    int32_t list_len(Head* head) {
        Node* n = head->node;
        int32_t len = 0;
        while (++len, (n = n->next) != NULL);
        return len;
    }

    int32_t list_sum(Head* head) {
        Node* n = head->node;
        int32_t sum = 0;
        do {
            sum += n->value;
            n = n->next;
        } while (n != NULL);
        return sum;
    }

    void delete_list(Head* head) {
        delete_node(head->node);
        free(head);
    }

    void list_append(Head* head, int32_t value) {
        Node** node_ptr = &head->node;
        while (*node_ptr != NULL) node_ptr = &(*node_ptr)->next;
        *node_ptr = (Node*)malloc(sizeof(Node));
        (*node_ptr)->next = NULL;
        (*node_ptr)->value = value;
    }

    """
    ffi = FFI()
    ffi.cdef(structs + declr)
    ffi.set_source('cffi_linkedlist_ool', structs + impl)
    tmpdir = temp_directory('test_cffi')
    ffi.compile(tmpdir=tmpdir)
    sys.path.append(tmpdir)
    try:
        mod = import_dynamic('cffi_linkedlist_ool')
        cffi_support.register_module(mod)
        return mod
    finally:
        sys.path.remove(tmpdir)


def init():
    """
    Initialize module globals.  This can invoke external utilities, hence not
    being executed implicitly at module import.
    """
    global ffi, cffi_sin, cffi_cos, cffi_bool

    if ffi is None:
        ffi, dll = load_inline_module()
        cffi_sin = dll._numba_test_sin
        cffi_cos = dll._numba_test_cos
        cffi_bool = dll._numba_test_boolean
        del dll

def init_ool():
    """
    Same as init() for OOL mode.
    """
    global ffi_ool, cffi_sin_ool, cffi_cos_ool, cffi_foo, cffi_bool_ool
    global vsSin, vdSin, vector_real, vector_imag

    if ffi_ool is None:
        ffi_ool, mod = load_ool_module()
        cffi_sin_ool = mod.lib.sin
        cffi_cos_ool = mod.lib.cos
        cffi_foo = mod.lib.foo
        cffi_bool_ool = mod.lib.boolean
        vsSin = mod.lib.vsSin
        vdSin = mod.lib.vdSin
        vector_real = mod.lib.vector_real
        vector_imag = mod.lib.vector_imag
        del mod

ffi = ffi_ool = None


def use_cffi_sin(x):
    return cffi_sin(x) * 2

def use_two_funcs(x):
    return cffi_sin(x) - cffi_cos(x)

def use_cffi_sin_ool(x):
    return cffi_sin_ool(x) * 2

def use_cffi_boolean_true():
    return cffi_bool_ool()

def use_two_funcs_ool(x):
    return cffi_sin_ool(x) - cffi_cos_ool(x)

def use_func_pointer(fa, fb, x):
    if x > 0:
        return fa(x)
    else:
        return fb(x)

def use_user_defined_symbols():
    return cffi_foo(1, 2, 3)

# The from_buffer method is member of cffi.FFI, and also of CompiledFFI objects
# (cffi_usecases_ool.ffi is a CompiledFFI object) so we use both in these
# functions.

def vector_sin_float32(x, y):
    vsSin(len(x), ffi.from_buffer(x), ffi_ool.from_buffer(y))

def vector_sin_float64(x, y):
    vdSin(len(x), ffi.from_buffer(x), ffi_ool.from_buffer(y))


# For testing pointer to structs from buffers

def vector_extract_real(x, y):
    vector_real(ffi.from_buffer(x), ffi.from_buffer(y), len(x))

def vector_extract_imag(x, y):
    vector_imag(ffi.from_buffer(x), ffi.from_buffer(y), len(x))
