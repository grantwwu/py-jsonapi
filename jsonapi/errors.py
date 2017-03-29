#!/usr/bin/env python3

# The MIT License (MIT)
#
# Copyright (c) 2016 Benedikt Schmitt
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
jsonapi.errors
==============

This module implements the base class for all JSON API exceptions:
http://jsonapi.org/format/#errors.

We also define frequently used HTTP errors and exceptions, which are
often used in *py-jsonapi*, like :exc:`ReadOnlyField` or
:exc:`ResourceNotFound`.
"""

# std
import json


__all__ = [
    "Error",
    "ErrorList",
    "error_to_response",

    # 4xx errors
    "BadRequest",
    "Unauthorized",
    "Forbidden",
    "NotFound",
    "MethodNotAllowed",
    "NotAcceptable",
    "Conflict",
    "Gone",
    "PreConditionFailed",
    "UnsupportedMediaType",
    "ImATeapot",
    "UnprocessableEntity",
    "Locked",
    "FailedDependency",
    "TooManyRequests",

    # 5xx errors
    "InternalServerError",
    "NotImplemented",
    "BadGateway",
    "ServiceUnavailable",
    "GatewayTimeout",
    "VariantAlsoNegotiates",
    "InsufficientStorage",
    "NotExtended",

    # JSONAPI errors
    "ValidationError",
    "InvalidType",
    "InvalidValue",
    "UnresolvableIncludePath",
    "UnsortableField",
    "UnsortableField",
    "ResourceNotFound"
]


class Error(Exception):
    """
    :seealso: http://jsonapi.org/format/#errors

    This is the base class for all exceptions thrown by the API. All subclasses
    of this exception are catched and converted into a response.
    All other exceptions will be replaced by an InternalServerError exception.

    :arg int http_status:
        The HTTP status code applicable to this problem.
    :arg str id:
        A unique identifier for this particular occurrence of the problem.
    :arg str about:
        A link that leeds to further details about this particular occurrence
        of the problem.
    :arg str code:
        An application specific error code, expressed as a string value.
    :arg str title:
        A short, human-readable summay of the problem that SHOULD not change
        from occurrence to occurrence of the problem, except for purposes
        of localization. The default value is the class name.
    :arg str detail:
        A human-readable explanation specific to this occurrence of the problem.
    :arg source_pointer:
        A JSON Pointer [RFC6901] to the associated entity in the request
        document [e.g. `"/data"` for a primary data object, or
        `"/data/attributes/title"` for a specific attribute].
    :arg str source_parameter:
        A string indicating which URI query parameter caused the error.
    :arg dict meta:
        A meta object containing non-standard meta-information about the error.
    """

    def __init__(
        self, *, http_status=500, id_=None, about="", code=None, title=None,
        detail="", source_parameter=None, source_pointer=None, meta=None
        ):
        """
        """
        self.http_status = http_status
        self.id = id_
        self.about = about
        self.code = code
        self.title = title if title is not None else type(self).__name__
        self.detail = detail
        self.source_pointer = str(source_pointer)
        self.source_parameter = source_parameter
        self.meta = meta if meta is not None else dict()
        return None

    def __str__(self):
        """
        Returns the :attr:`detail` attribute per default.
        """
        return json.dumps(self.json, indent=4, sort_keys=True)

    @property
    def json(self):
        """
        The serialized version of this error.
        """
        d = dict()
        if self.id is not None:
            d["id"] = str(self.id)
        d["status"] = self.http_status
        d["title"] = self.title
        if self.about:
            d["links"] = dict()
            d["links"]["about"] = self.about
        if self.code:
            d["code"] = self.code
        if self.detail:
            d["detail"] = self.detail
        if self.source_pointer or self.source_parameter:
            d["source"] = dict()
            if self.source_pointer:
                d["source"]["pointer"] = self.source_pointer
            if self.source_parameter:
                d["source"]["parameter"] = self.source_parameter
        if self.meta:
            d["meta"] = self.meta
        return d


class ErrorList(Exception):
    """
    Can be used to store a list of exceptions, which occur during the
    execution of a request.

    :seealso: http://jsonapi.org/format/#error-objects
    :seealso: http://jsonapi.org/examples/#error-objects-multiple-errors
    """

    def __init__(self, errors=None):
        self.errors = list()
        if errors:
            self.extend(errors)
        return None

    def __bool__(self):
        return bool(self.errors)

    def __len__(self):
        return len(self.errors)

    def __str__(self):
        return json.dumps(self.json, indent=4, sort_keys=True)

    @property
    def http_status(self):
        """
        The most specific http status code, which matches all exceptions.
        """
        if not self.errors:
            return None
        elif len(self.errors) == 1:
            return self.errors[0].http_status
        elif any(400 <= err.http_status < 500 for err in self.errors):
            return 400
        else:
            return 500

    def append(self, error):
        """
        Appends the :class:`Error` error to the error list.

        :arg Error error:
        """
        if not isinstance(error, Error):
            raise TypeError("*error* must be of type Error")
        self.errors.append(error)
        return None

    def extend(self, errors):
        """
        Appends all errors in *errors* to the list. *errors* must be an
        :class:`ErrorList` or a sequence of :class:`Error`.

        :arg errors:
        """
        if isinstance(errors, ErrorList):
            self.errors.extend(errors.errors)
        elif all(isinstance(err, Error) for err in errors):
            self.errors.extend(errors)
        else:
            raise TypeError(
                "*errors* must be of type ErrorList or a sequence of Error."
            )

    @property
    def json(self):
        """
        Creates the JSONapi error object.

        :seealso: http://jsonapi.org/format/#error-objects
        """
        d = [error.json for error in self.errors]
        return d


def error_to_response(error, dump_json=None):
    """
    Converts an :class:`Error` to a :class:`~jsonapi.response.Response`.

    :arg Error error:
        The error, which is converted into a response.
    :arg callable dump_json:
        The json serializer, which is used to serialize the error.

    :rtype: jsonapi.request.Request
    """
    assert isinstance(error, (Error, ErrorList))

    from .response import Response
    dump_json = dump_json or json.dumps

    if isinstance(error, Error):
        body = dump_json({"errors": [error.json]})
    elif isinstance(error, ErrorList):
        body = dump_json({"errors": error.json})

    resp = Response(
        status=error.http_status,
        headers={"content-type": "application/vnd.api+json"},
        body=body
    )
    return resp


# Common http errors
# ------------------

# 4xx errors
# ~~~~~~~~~~

class BadRequest(Error):

    def __init__(self, **kargs):
        super().__init__(http_status=400, **kargs)
        return None


class Unauthorized(Error):

    def __init__(self, **kargs):
        super().__init__(http_status=401, **kargs)
        return None


class Forbidden(Error):

    def __init__(self, **kargs):
        super().__init__(http_status=403, **kargs)
        return None


class NotFound(Error):

    def __init__(self, **kargs):
        super().__init__(http_status=404, **kargs)
        return None


class MethodNotAllowed(Error):

    def __init__(self, **kargs):
        super().__init__(http_status=405, **kargs)
        return None


class NotAcceptable(Error):

    def __init__(self, **kargs):
        super().__init__(http_status=406, **kargs)
        return None


class Conflict(Error):

    def __init__(self, **kargs):
        super().__init__(http_status=409, **kargs)
        return None


class Gone(Error):

    def __init__(self, **kargs):
        super().__init__(http_status=410, **kargs)
        return None


class PreConditionFailed(Error):

    def __init__(self, **kargs):
        super().__init__(http_status=412, **kargs)
        return None


class UnsupportedMediaType(Error):

    def __init__(self, **kargs):
        super().__init__(http_status=415, **kargs)
        return None


class ImATeapot(Error):

    def __init__(self, **kargs):
        super().__init__(http_status=418, **kargs)
        return None


class UnprocessableEntity(Error):

    def __init__(self, **kargs):
        super().__init__(http_status=422, **kargs)
        return None


class Locked(Error):

    def __init__(self, **kargs):
        super().__init__(http_status=423, **kargs)
        return None


class FailedDependency(Error):

    def __init__(self, **kargs):
        super().__init__(http_status=424, **kargs)
        return None


class TooManyRequests(Error):

    def __init__(self, **kargs):
        super().__init__(http_status=429, **kargs)
        return None


# 5xx errors
# ~~~~~~~~~~

class InternalServerError(Error):

    def __init__(self, **kargs):
        super().__init__(http_status=500, **kargs)
        return None


class NotImplemented(Error):

    def __init__(self, **kargs):
        super().__init__(http_status=501, **kargs)
        return None


class BadGateway(Error):

    def __init__(self, **kargs):
        super().__init__(http_status=502, **kargs)
        return None


class ServiceUnavailable(Error):

    def __init__(self, **kargs):
        super().__init__(http_status=503, **kargs)
        return None


class GatewayTimeout(Error):

    def __init__(self, **kargs):
        super().__init__(http_status=504, **kargs)
        return None


class VariantAlsoNegotiates(Error):

    def __init__(self, **kargs):
        super().__init__(http_status=506, **kargs)
        return None


class InsufficientStorage(Error):

    def __init__(self, **kargs):
        super().__init__(http_status=507, **kargs)
        return None


class NotExtended(Error):

    def __init__(self, **kargs):
        super().__init__(http_status=510, **kargs)
        return None


# special JSONAPI errors
# ----------------------

class ValidationError(BadRequest):
    """
    Raised, if the structure of a json document in a request body is invalid.

    Please note, that this does not include semantic errors, like an unknown
    typename.

    This type of exception is used often in the :mod:`jsonapi.validator`
    and :mod:`jsonapi.validation` modules.

    :seealso: http://jsonapi.org/format/#document-structure
    """


class InvalidValue(ValidationError):
    """
    Raised if an input value (part of a JSON API document) has an invalid
    value.

    :seealso: http://jsonapi.org/format/#document-structure
    """


class InvalidType(ValidationError):
    """
    Raised if an input value (part of a JSON API document) has the wrong type.

    This type of exception is often raised during decoding.

    :seealso: http://jsonapi.org/format/#document-structure
    """


class MissingField(ValidationError):
    """
    Raised if a field is required but not part of the input data.

    :seealso: http://jsonapi.org/format/#document-structure
    """

    def __init__(self, type, field, **kargs):
        kargs.setdefault(
            "detail", "The field '{}.{}' is required.".format(type, field)
        )
        super().__init__(**kargs)
        return None


class UnresolvableIncludePath(BadRequest):
    """
    Raised if an include path does not exist. The include path is part
    of the ``include`` query argument. (An include path is invalid, if a
    relationship mentioned in it is not defined on a resource).

    :seealso: http://jsonapi.org/format/#fetching-includes
    """

    def __init__(self, path, **kargs):
        if not isinstance(path, str):
            path = ".".join(path)

        kargs.setdefault(
            "detail", "The include path '{}' does not exist.".format(path)
        )
        kargs.setdefault("source_parameter", "include")
        super().__init__(**kargs)
        return None


class UnsortableField(BadRequest):
    """
    If a field is used as sort key, but sorting is not supported on this field.

    :seealso: http://jsonapi.org/format/#fetching-sorting
    """

    def __init__(self, type, field, **kargs):
        kargs.setdefault(
            "detail",
            "The field '{}.{}' can not be used for sorting.".format(type, field)
        )
        kargs.setdefault("source_parameter", "sort")
        super().__init__(**kargs)
        return None


class UnfilterableField(BadRequest):
    """
    If a filter should be used on a field, which does not support the
    filter.

    :seealso: http://jsonapi.org/format/#fetching-filtering
    """

    def __init__(self, type, field, filtername, **kargs):
        kargs.setdefault(
            "detail",
            "The field '{}.{}' does not support the '{}' filter."\
            .format(type, field, filtername)
        )
        kargs.setdefault("source_parameter", "filter[{}]".format(field))
        super().__init__(**kargs)
        return None


class ResourceNotFound(NotFound):
    """
    Raised, if a resource does not exist.
    """

    def __init__(self, type, id, **kargs):
        kargs.setdefault(
            "detail",
            "The resource (type='{}', id='{}') does not exist.".format(type, id)
        )
        super().__init__(**kargs)
        return None
