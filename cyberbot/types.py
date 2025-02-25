from typing import Any, Generic, TypeVar

"""
Variant-like return value handling for Python.

usage of Result:

def rofl(a: str) -> Result[str, str]:
    if a.startswith("lol"):
        return Err("no fun allowed")
    return Ok(a * 3)

match rofl("lol"):
    case Ok(v):
        print(f"good: {v}")
    case Err(e):
        print(f"bad: {e}")
"""

T_co = TypeVar("T_co", covariant=True)
E_co = TypeVar("E_co", covariant=True)


class Ok(Generic[T_co]):
    _value: T_co
    __match_args__ = ("_value",)

    def __init__(self, value: T_co):
        self._value = value

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Ok):
            return self._value == other._value
        return False

    def __repr__(self) -> str:
        return f"Ok({repr(self._value)})"


class Err(Generic[E_co]):
    _err: E_co
    __match_args__ = ("_err",)

    def __init__(self, err: E_co):
        self._err = err

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Err):
            return self._err == other._err
        return False

    def __repr__(self) -> str:
        return f"Err({repr(self._err)})"


Result = Ok[T_co] | Err[E_co]
