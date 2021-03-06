import sys
import re
import contextvars
from itertools import chain
from collections import defaultdict

from .base import lib, ffi, _gb_from_name, _check
from . import types

current_monoid = contextvars.ContextVar('current_monoid')

class Monoid:

    _auto_monoids = defaultdict(dict)

    __slots__ = ('name', 'monoid', 'token')

    def __init__(self, op, typ, monoid, udt=None, boolean=False):
        if udt is not None:
            o = ffi.new('GrB_Monoid*')
            udt = udt.gb_type
            lib.GrB_Monoid_new(
                o,
                ffi.cast('GxB_binary_function', monoid.address),
                lib.GrB_BOOL if boolean else udt, udt, udt)
            self.monoid = o[0]
        else:
            self.monoid = monoid
        self.name = '_'.join((op, typ, 'monoid'))
        self.token = None
        self.__class__._auto_monoids[op+'_MONOID'][_gb_from_name(typ)] = monoid
        cls = getattr(types, typ, None)
        if cls is not None:
            setattr(cls, op+'_MONOID', self)

    def __enter__(self):
        self.token = current_monoid.set(self)
        return self

    def __exit__(self, *errors):
        current_monoid.reset(self.token)
        return False

    def get_monoid(self, operand1=None, operand2=None):
        return self.monoid

class AutoMonoid(Monoid):

    def __init__(self, name):
        self.name = name
        self.token = None

    def get_monoid(self, operand1=None, operand2=None):
        return Monoid._auto_monoids[self.name][operand1.gb_type]

__all__ = ['Monoid', 'AutoMonoid', 'current_monoid']

gxb_monoid_re = re.compile(
    '^GxB_(MIN|MAX|PLUS|TIMES)_'
    '(UINT8|UINT16|UINT32|UINT64|INT8|INT16|INT32|INT64|FP32|FP64)_MONOID$')

pure_bool_re = re.compile('^GxB_(LOR|LAND|LXOR|EQ)_(BOOL)_MONOID$')

def monoid_group(reg):
    srs = []
    for n in filter(None, [reg.match(i) for i in dir(lib)]):
        op, typ = n.groups()
        srs.append(Monoid(op, typ, getattr(lib, n.string)))
    return srs

def build_monoids():
    this = sys.modules[__name__]
    for r in chain(monoid_group(gxb_monoid_re), monoid_group(pure_bool_re)):
        setattr(this, r.name, r)
        __all__.append(r.name)
    for name in Monoid._auto_monoids:
        bo = AutoMonoid(name)
        setattr(this, name, bo)
        __all__.append(name)
        
