import logging

logger = logging.getLogger(__name__)

# Numpy scalar type names — matched by name so we never need to import numpy.
# This covers int8/16/32/64, uint variants, float16/32/64, bool_, and complex.
_NUMPY_INT_TYPES = frozenset({
    "int8", "int16", "int32", "int64",
    "uint8", "uint16", "uint32", "uint64",
    "intp", "intc",
})
_NUMPY_FLOAT_TYPES = frozenset({"float16", "float32", "float64", "float128", "longdouble"})
_NUMPY_BOOL_TYPES  = frozenset({"bool_"})


def sanitize_for_json(obj):
    """
    Recursively convert numpy/pandas types to Python native types so that
    Pydantic's TypeAdapter.dump_json() (and standard json.dumps) never sees
    a numpy scalar.

    Fast-path by type name (no numpy import needed):
        numpy.int64  → int
        numpy.float64 → float
        numpy.bool_  → bool
        numpy arrays → list (via .tolist())
    Module-path fallback for anything else from numpy/pandas.
    """
    # ── Fast-path: numpy scalar by type name ──────────────────────────────────
    type_name = type(obj).__name__
    if type_name in _NUMPY_INT_TYPES:
        return int(obj)
    if type_name in _NUMPY_FLOAT_TYPES:
        return float(obj)
    if type_name in _NUMPY_BOOL_TYPES:
        return bool(obj)

    # ── Recursive containers ──────────────────────────────────────────────────
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple, set)):
        return type(obj)(sanitize_for_json(i) for i in obj)

    # ── Module-path fallback for numpy arrays and pandas objects ─────────────
    module_name = (type(obj).__module__ or "")
    if module_name.startswith("numpy"):
        if hasattr(obj, "item"):    # scalar (catches anything missed above)
            return obj.item()
        elif hasattr(obj, "tolist"):  # ndarray
            return obj.tolist()
        return str(obj)
    elif module_name.startswith("pandas"):
        if hasattr(obj, "to_list"):
            return obj.to_list()
        return str(obj)

    return obj
