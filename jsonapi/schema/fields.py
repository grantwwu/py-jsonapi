#!/usr/bin/env python3

"""
jsonapi.schema.fields
=====================

.. note::

    Always remember that you can model the JSON API completly with the fields in
    :mod:`~jsonapi.schema.base_fields`.

.. sidebar:: Index

    *   :class:`String`
    *   :class:`Integer`
    *   :class:`Float`
    *   :class:`Complex`
    *   :class:`Decimal`
    *   :class:`Fraction`
    *   :class:`DateTime`
    *   :class:`TimeDelta`
    *   :class:`UUID`
    *   :class:`Boolean`
    *   :class:`URI`
    *   :class:`EMail`
    *   :class:`Dict`
    *   :class:`List`
    *   :class:`Number`
    *   :class:`Str`
    *   :class:`Bool`

This module contains fields for several standard Python types and classes
from the standard library.
"""

__all__ = [
    "String",
    "Integer",
    "Float",
    "Complex",
    "Decimal",
    "Fraction",
    "DateTime",
    "TimeDelta",
    "UUID",
    "Boolean",
    "URI",
    "EMail",
    "Dict",
    "List",

    "Number",
    "Str",
    "Bool"
]

# std
import collections
import datetime
import decimal
import fractions
import logging
import re
import uuid

# third party
import dateutil.parser
import rfc3986

# local
from .base_fields import Attribute
from jsonapi.errors import InvalidType, InvalidValue


logger = logging.getLogger(__file__)


class String(Attribute):
    """
    :arg str regex:
        If given, the string must match this regex.
    """

    def __init__(self, *, regex=None, **kargs):
        super().__init__(**kargs)
        self.regex = re.compile(regex)
        return None

    def validate_pre_decode(self, schema, data, sp, context):
        if not isinstance(data, str):
            detail = "Must be a string."
            raise InvalidType(detail=detail, source_pointer=sp)
        if self.regex is not None and self.regex.fullmatch(data):
            detail = "Did not match regex."
            raise InvalidValue(detail=detail, source_pointer=sp)
        return super().validate_pre_decode(schema, data, sp, context)

    def encode(self, schema, data):
        return str(data)


class Integer(Attribute):
    """
    :arg int min:
        The integer must be greater or equal than this value.
    :arg int max:
        The integer must be less or equal than this value.
    """

    def __init__(self, *, min=None, max=None, **kargs):
        super().__init__(**kargs)

        # min must be <= max
        assert min is None or max is None or min <= max

        self.min = min
        self.max = max
        return None

    def validate_pre_decode(self, schema, data, sp, context):
        if not isinstance(data, int) \
            and not (isinstance(data, float) and data.is_integer()):
            detail = "Must be an integer."
            raise InvalidType(detail=detail, source_pointer=sp)

        if self.min is not None and self.min > data:
            detail = "Must be >= {}.".format(self.min)
            raise InvalidValue(detail=detail, source_pointer=sp)

        if self.max is not None and self.max < data:
            detail = "Must be <= {}.".format(self.max)
            raise InvalidValue(detail=detail, source_pointer=sp)
        return super().validate_pre_decode(schema, data, sp, context)

    def decode(self, schema, data, sp):
        return int(data)

    def encode(self, schema, data):
        return int(data)


class Float(Attribute):
    """
    :arg float min:
        The float must be greater or equal than this value.
    :arg float max:
        The float must be less or equal than this value.
    """

    def __init__(self, *, min=None, max=None, **kargs):
        super().__init__(**kargs)

        # min must be <= max
        assert min is None or max is None or min <= max

        self.min = min
        self.max = max
        return None

    def validate_pre_decode(self, schema, data, sp, context):
        if not isinstance(data, (int, float)):
            detail = "must be a real number."
            raise InvalidType(detail=detail, source_pointer=sp)

        if self.min is not None and self.min > data:
            detail = "Must be >= {}.".format(self.min)
            raise InvalidValue(detail=detail, source_pointer=sp)

        if self.max is not None and self.max < data:
            detail = "Must be <= {}.".format(self.max)
            raise InvalidValue(detail=detail, source_pointer=sp)
        return super().validate_pre_decode(schema, data, sp, context)

    def decode(self, schema, data, sp):
        return float(data)

    def encode(self, schema, data):
        return float(data)


class Complex(Attribute):
    """
    Encodes a :class:`complex` number as JSON object with a *real* and *imag*
    member::

        {"real": 1.2, "imag": 42}
    """

    def validate_pre_decode(self, schema, data, sp, context):
        detail="Must be an object with a 'real' and 'imag' member.'"

        if not isinstance(data, collections.Mapping):
            raise InvalidType(detail=detail, source_pointer=sp)
        if not "real" in data:
            detail = "Does not have a 'real' member."
            raise InvalidValue(detail=detail, source_pointer=sp)
        if not "imag" in data:
            detail = "Does not have an 'imag' member."
            raise InvalidValue(detail=detail, source_pointer=sp)

        if not isinstance(data["real"], (int, float)):
            detail = "The real part must be a number."
            raise InvalidValue(detail=detail, source_pointer=sp/"real")
        if not isinstance(data["imag"], (int, float)):
            detail = "The imaginar part must be a number."
            raise InvalidValue(detail=detail, source_pointer=sp/"imag")
        return super().validate_pre_decode(schema, data, sp, context)

    def decode(self, schema, data, sp):
        return complex(data["real"], data["imag"])

    def encode(self, schema, data):
        data = complex(data)
        return {"real": data.real, "imag": data.imag}


class Decimal(Attribute):
    """Encodes and decods a :class:`decimal.Decimal` as a string."""

    def validate_pre_decode(self, schema, data, sp, context):
        if not isinstance(data, str):
            detail = "Must be a number encoded as string."
            raise InvalidType(detail=detail, source_pointer=sp)

        try:
            decimal.Decimal(data)
        except decimal.InvalidOperation:
            detail = "Not a decimal number."
            raise InvalidValue(detail=detail, source_pointer=sp)
        return super().validate_pre_decode(schema, data, sp, context)

    def decode(self, schema, data, sp):
        return decimal.Decimal(data)

    def encode(self, schema, data):
        return str(data)


class Fraction(Attribute):
    """Stores a :class:`fractions.Fraction` in an object with a *numerator*
    and *denominator* member::

        # 1.5
        {"numerator": 2, "denominator": 3}

    :arg float min:
        The fraction must be greater or equal than this value.
    :arg float max:
        The fraction must be less or equal than this value.
    """

    def __init__(self, *, min=None, max=None, **kargs):
        super().__init__(**kargs)

        # min must be <= max
        assert min is None or max is None or min <= max

        self.min = min
        self.max = max
        return None

    def validate_pre_decode(self, schema, data, sp, context):
        if not isinstance(data, dict):
            detail = "Must be an object with a 'numerator' and 'denominator' "\
                "member."
            raise InvalidType(detail=detail, source_pointer=sp)
        if not "numerator" in data:
            detail = "Does not have a 'numerator' member."
            raise InvalidValue(detail=detail, source_pointer=sp)
        if not "denominator" in data:
            detail = "Does not have a 'denominator' member."
            raise InvalidValue(detail=detail, source_pointer=sp)

        if not isinstance(data["numerator"], int):
            detail = "The numerator must be an integer."
            raise InvalidValue(detail=detail, source_pointer=sp/"numerator")
        if not isinstance(data["denominator"], int):
            detail = "The denominator must be an integer."
            raise InvalidValue(detail=detail, source_pointer=sp/"denominator")
        if data["denominator"] == 0:
            detail = "The denominator must be not equal to zero."
            raise InvalidValue(detail=detail, source_pointer=sp/"denominator")

        val = data["numerator"]/data["denominator"]
        if self.min is not None and self.min > val:
            detail = "Must be >= {}.".format(self.min)
            raise InvalidValue(detail=detail, source_pointer=sp)
        if self.max is not None and self.max < val:
            detail = "Must be <= {}.".format(self.max)
            raise InvalidValue(detail=detail, source_pointer=sp)
        return super().validate_pre_decode(schema, data, sp, context)

    def decode(self, schema, data, sp):
        return fractions.Fraction(int(data[0]), int(data[1]))

    def encode(self, schema, data):
        return {"numerator": data.numerator, "denominator": data.denominator}


class DateTime(Attribute):
    """Stores a :class:`datetime.datetime` in ISO-8601 as recommeded in
    http://jsonapi.org/recommendations/#date-and-time-fields.
    """

    def validate_pre_decode(self, schema, data, sp, context):
        try:
            dateutil.parser.parse(data)
        except ValueError:
            detail = "Must be an ISO-8601 formatted date/time stamp."
            raise InvalidValue(detail=detail, source_pointer=sp)
        return super().validate_pre_decode(schema, data, sp, context)

    def decode(self, schema, data, sp):
        return dateutil.parser.parse(data)

    def encode(self, schema, data):
        return data.isoformat()


class TimeDelta(Attribute):
    """Stores a :class:`datetime.timedelta` as total number of seconds.

    :arg datetime.timedelta min:
        The timedelta must be greater or equal than this value.
    :arg datetime.timedelta max:
        The timedelta must be less or equal than this value.
    """

    def __init__(self, *, min=None, max=None, **kargs):
        super().__init__(**kargs)

        # min must be <= max
        assert min is None or max is None or min <= max

        self.min = min
        self.max = max
        return None

    def validate_pre_decode(self, schema, data, sp, context):
        try:
            data = float(data)
        except TypeError:
            detail = "Must be a number."
            raise InvalidType(detail=detail, source_pointer=sp)

        data = datetime.timedelta(seconds=data)

        if self.min is not None and self.min > data:
            detail = "The timedelta must be >= {}.".format(self.min)
            raise InvalidValue(detail=detail, source_pointer=sp)
        if self.max is not None and self.max < data:
            detail = "The timedelta must be <= {}.".format(self.max)
        return super().validate_pre_decode(schema, data, sp, context)

    def decode(self, schema, data, sp):
        return datetime.timedelta(seconds=float(data))

    def encode(self, schema, data):
        return data.total_seconds()


class UUID(Attribute):
    """Encodes and decodes a :class:`uuid.UUID`.

    :arg str version:
        The required version of the UUID.
    """

    def __init__(self, *, version=None, **kargs):
        super().__init__(**kargs)
        self.version = version
        return None

    def validate_pre_decode(self, schema, data, sp, context):
        if not isinstance(data, str):
            detail = "The UUID must be a hexadecimal string."
            raise InvalidType(detail=detail, source_pointer=sp)

        try:
            data = uuid.UUID(hex=data)
        except ValueError:
            detail = "The UUID is badly formed (the representation as "\
                "hexadecimal string is needed)."
            raise InvalidValue(detail=detail, source_pointer=sp)

        if self.version is not None and self.version != data.version:
            detail = "Not a UUID{}.".format(self.version)
            raise InvalidValue(detail=detail, source_pointer=sp)
        return super().validate_pre_decode(schema, data, sp, context)

    def decode(self, schema, data, sp):
        return uuid.UUID(hex=data)

    def encode(self, schema, data):
        return data.hex


class Boolean(Attribute):
    """Ensures that the input is a :class:`bool`."""

    def validate_pre_decode(self, schema, data, sp, context):
        if not isinstance(data, bool):
            detail = "Must be either 'true' or 'false'."
            raise InvalidType(detail=detail, source_pointer=sp)
        return super().validate_pre_decode(schema, data, sp, context)

    def encode(self, schema, data):
        return bool(data)


class URI(Attribute):
    """Parses the URI with :func:`rfc3986.urlparse` and returns the result."""

    def validate_pre_decode(self, schema, data, sp, context):
        if not isinstance(data, str):
            detail = "Must be a string."
            raise InvalidType(detail=detail, source_pointer=sp)
        if not rfc3986.is_valid_uri(data):
            detail = "Not a valid URI."
            raise InvalidValue(detail=detail, source_pointer=sp)
        return super().validate_pre_decode(schema, data, sp, context)

    def decode(self, schema, data):
        return rfc3986.urlparse(data)

    def encode(self, schema, data):
        try:
            return data.geturl()
        except AttributeError:
            return str(data)


class EMail(Attribute):
    """Checks if a string is syntactically correct EMail address."""

    #: Taken from http://emailregex.com/
    #:
    #: .. todo::
    #:
    #:      This regex fails if the domain contains only one host: me@localhost.
    #:      find a better alternative.

    EMAIL_RE = re.compile(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)")

    def validate_pre_decode(self, schema, data, sp, context):
        if not isinstance(data, str):
            detail = "Must be a string."
            raise InvalidType(detail=detail, source_pointer=sp)
        if not EMail.EMAIL_RE.fullmatch(data):
            detail = "Not a valid EMail address."
            raise InvalidValue(detail=detail, source_pointer=sp)
        return super().validate_pre_decode(schema, data, sp, context)


class Dict(Attribute):
    """
    Realises a dictionary which has only values of a special field::

        todo = Dict(String(regex=".*[A-z0-9].*"))

    .. note::

        If you deal with dictionaries with values of different types, you can
        still use the more general
        :class:`~jsonapi.schema.base_fields.Attribute` field to model this data.

        *You are not forced to use a* :class:`Dict` *field*! It is only a
        helper.

    :arg Attribute field:
        All values of the dictionary are encoded and decoded using this
        field.
    """

    def __init__(self, field, **kargs):
        super().__init__(**kargs)
        self.field = field
        return None

    def decode(self, schema, data, sp):
        return {
            key: self.field.decode(schema, value, sp/key)\
            for key, value in data.items()
        }

    def encode(self, schema, data):
        return {
            key: self.field.encode(schema, value)\
            for key, value in data.items()
        }


class List(Attribute):
    """
    Realises a list which has only values of a special type::

        todo = List(String(regex=".*[A-z0-9].*"))

    .. note::

        If your list has items of different types, you can still use the more
        general :class:`~jsonapi.schema.base_fields.Attribute` field to model
        this data.

        *You are not forced to use a* :class:`List` *field*! It is only a
        helper.

    :arg Attribute field:
        All values of the list are encoded and decoded using this field.
    """

    def __init__(self, field, **kargs):
        super().__init__(**kargs)
        self.field = field
        return None

    def decode(self, schema, data, sp):
        return [
            self.field.decode(schema, item, sp/i) for item, i in enumerate(data)
        ]

    def encode(self, schema, data):
        return [self.field.encode(schema, item) for item in data]


# Some aliases.
Number = Float
Str = String
Bool = Boolean
