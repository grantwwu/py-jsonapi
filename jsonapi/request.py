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
jsonapi.request
===============

This module contains a class for representing HTTP requests. It helps to get
and parse the various query arguments, which are defined in the JSON API
specification.
"""

# std
import logging
import re
import urllib.parse

# third party
from cached_property import cached_property

# local
from .errors import BadRequest, UnsupportedMediaType


LOG = logging.getLogger(__file__)


__all__ = [
    "Request"
]


class Request(object):
    """
    Describes an HTTP request. A request can be used to call an API's
    :meth:`~jsonapi.api.API.handle_request` method.

    :arg str uri:
        The requested URI
    :arg str method:
        The HTTP method (GET, POST, PATCH, ...)
    :arg dict headers:
        The HTTP request headers
    :arg bytes body:
        The HTTP request body
    :arg ~jsonapi.api.API api:
        The api object, which handles the request (can be set later)
    :arg dict settings:
        A dictionary, containing custom information associated with the
        request.
    """

    def __init__(self, uri, method, headers, body, api=None, settings=None):
        """
        """
        #: The requested uri
        self.uri = uri

        #: The HTTP method (get, patch, delete, ...)
        self.method = method.lower()

        #: The HTTP headers
        self.headers = {key.lower(): value for key, value in headers.items()}

        #: The request body (:class:`bytes` or :class:`str`)
        self.body = body
        assert isinstance(body, (bytes, str))

        #: Automatically set by the :meth:`~jsonapi.api.API.handle_request`
        #: method from the responsible :class:`~jsonapi.api.API`.
        self.api = api

        #: Contains parameters, which are encoded into the URI.
        #: For example the resource uri ``http://localhost:5000/api/User/1``
        #: contains the id ``{'id': '1'}``.
        #:
        #: This dictionary will be populated in the
        #: :meth:`~jsonapi.api.API.handle_request` method.
        self.japi_uri_arguments = dict()

        #: You can use this dictionary to store store stuff associated
        #: with this request. For example: The database session or the
        #: the current user/client.
        self.settings = settings or dict()
        assert isinstance(self.settings, dict)
        return None

    @property
    def g(self):
        """Alias for :attr:`settings`."""
        return self.settings

    @cached_property
    def parsed_uri(self):
        """
        A tuple with the uri components
        """
        return urllib.parse.urlparse(self.uri)

    @cached_property
    def query(self):
        """
        A dictionary, which maps the query keys to their values.
        """
        query = urllib.parse.parse_qs(self.parsed_uri.query)
        return query

    def get_query_argument(self, name, fallback=None):
        """
        :arg str name:
            The name of the query parameter
        :arg fallback:
            Returned, if the *name* does not exist.

        :rtype: str
        :returns:
            The value of the query argument with the name *name*. If there is
            no query parameter with that name, *fallback* will be returned
            instead.
        """
        value = self.query.get(name)
        return value[0] if value else fallback

    @cached_property
    def content_type(self):
        """
        A tuple, with the media type and the parameters.

        .. code-block:: python3

            media_type, media_parameters = request.content_type

        :seealso: https://tools.ietf.org/html/rfc7231#section-3.1.1.1

        :todo: Parse the content-type header correct.
        """
        content_type = self.headers.get("content-type", "")
        type_, *parameters = content_type.split(";")
        return (type_, dict())

    def assert_jsonapi_content(self):
        """
        Raises a :exc:`~jsonapi.error.UnsupportedMediaType` exception,
        if the content type is not ``application/vnd.api+json``.
        """
        if self.headers.get("content-type", "") != "application/vnd.api+json":
            raise UnsupportedMediaType(
                details="The content-type must be 'application/vnd.api+json'."
            )
        return None

    @cached_property
    def japi_filters(self):
        """
        .. hint::

            Please note, that the *filter* strategy is not defined by the
            jsonapi specification and depends on the implementation. If you want
            to use another filter strategy, feel free to **override** this
            property.

        Returns a list, which contains 3-tuples::

            (fieldname, filtername, rule)

        This tuples describes on which field a filter is applied. For example::

            ("name", "startswith", "Homer")
            ("age", "gt", 25)
            ("name", "in", ["Homer", "Marge"])

        Filters can be applied using the query string::

            >>> # /api/User/?filter[name]=endswith:'Simpson'
            >>> request.japi_filters
            [("name", "endswith", "Simpson")]

            >>> # /api/User/?filter[name]=in:['Homer Simpson', 'Darth Vader']
            >>> request.japi_filters
            [("name", "in", ["Homer Simpson", "Darth Vader"])]

            >>> # /api/User/?filter[email]=startswith:'lisa'&filter[age]=lt:20
            >>> request.japi_filters
            [("email", "startswith", "lisa"), ("age", "lt", 20)]

        The general syntax is::

            "?filter[fieldname]=filtername:rule"

        where *rule* is a JSON value.

        :raises BadRequest:
            If the rule of a filter is not a JSON object.
        :raises BadRequest:
            If a filtername contains other characters than *[a-z]*.
        """
        KEY_RE = re.compile(r"filter\[(?P<field>[A-z0-9_]+)\]")
        VALUE_RE = re.compile(r"(?P<filtername>[a-z]+):(?P<rule>.*)")

        filters = list()
        for key, values in self.query.items():
            key_match = re.fullmatch(KEY_RE, key)
            value_match = re.fullmatch(VALUE_RE, values[0])

            # If the key indicates a filter, but the value is not correct
            # formatted.
            if key_match and not value_match:
                field = key_match.group("field")
                raise BadRequest(
                    detail="The filter '{}' is not correct applied.".format(field),
                    source_parameter=key
                )

            # The key indicates a filter and the filternames exists.
            elif key_match and value_match:
                field = key_match.group(1)
                filtername = value_match.group("filtername")
                rule = value_match.group("rule")
                try:
                    rule = self.api.load_json(rule)
                except Exception as err:
                    LOG.debug(err, exc_info=False)
                    raise BadRequest(
                        detail="The rule '{}' is not JSON serializable".format(rule),
                        source_parameter=key
                    )

                filters.append((field, filtername, rule))
        return filters

    def has_filter(self, field, filtername):
        """
        Returns true, if the filter *filtername* has been applied at least once
        on the *field*.

        :arg str field:
        :arg str filtername:
        """
        return any(
            field == item[0] and filtername == item[1]\
            for item in self.japi_filters
        )

    def get_filter(self, field, filtername, default=None):
        """
        If the filter *filtername* has been applied on the *field*, the
        *filterrule* is returned and *default* otherwise.

        :arg str field:
        :arg str filtername:
        :arg default:
            A fallback value for the filter.
        """
        for item in self.japi_filters:
            if item[0] == field and item[1] == filtername:
                return item[2]
        return default

    @cached_property
    def japi_fields(self):
        """
        The fields, which should be included in the response (sparse fieldset).

        .. code-block:: python3

            >>> # /api/User?fields[User]=email,name&fields[Post]=comments
            >>> request.japi_fields
            {"User": ["email", "name"], "Post": ["comments"]}

        :seealso: http://jsonapi.org/format/#fetching-sparse-fieldsets
        """
        FIELDS_RE = re.compile(r"fields\[([A-z0-9_]+)\]")

        fields = dict()
        for key, value in self.query.items():
            match = re.fullmatch(FIELDS_RE, key)
            if match:
                typename = match.group(1)
                type_fields = value[0].split(",")
                type_fields = [
                    item.strip() for item in type_fields if item.strip()
                ]

                fields[typename] = type_fields
        return fields

    @cached_property
    def japi_include(self):
        """
        Returns the names of the relationships, which should be included into
        the response.

        .. code-block:: python3

            >>> # /api/Post?include=author,comments.author
            >>> req.japi_include
            [["author"], ["comments", "author"]

        :seealso: http://jsonapi.org/format/#fetching-includes
        """
        include = self.get_query_argument("include", "")
        include = [path.split(".") for path in include.split(",") if path]
        return include

    @cached_property
    def japi_sort(self):
        """
        Returns a list with two tuples, describing how the output should be
        sorted:

        .. code-block:: python3

            >>> # /api/Post?sort=name,-age,+comments.count
            [("+", ["name"]), ("-", ["age"]), ("+", ["comments", "count"])]]

        :seealso: http://jsonapi.org/format/#fetching-sorting
        """
        tmp = self.get_query_argument("sort")
        tmp = tmp.split(",") if tmp else list()

        sort = list()
        for field in tmp:
            if field[0] == "+" or field[0] == "-":
                direction = field[0]
                field = field[1:]
            else:
                direction = "+"

            field = field.split(".")
            field = [e.strip() for e in field]

            sort.append((direction, field))
        return sort

    def get_order(self, field, default="+"):
        """
        Checks if a sort criterion (``+`` or ``-``) for the *field* exists
        and returns it.

        :arg str field:
        :arg default:
            Returned, if no criterion is set by the request.
        """
        if isinstance(field, str):
            field = field.split(".")

        for direction, field_ in self.japi_sort:
            print(field_, field)
            if field_ == field:
                return direction
        return default

    @cached_property
    def json(self):
        """
        Decodes the body assuming, that it is a JSON document. This method
        uses the API's :meth:`~jsonapi.api.API.load_json` method.

        :raises BadRequest:
            If the API is **not** in debug mode and the body is not a valid
            JSON document.
        :raises Exception:
            The original exception, if the API is in debug mode and the body
            is not a valid JSON document.
        """
        body = self.body

        # Decode the body
        if isinstance(body, bytes):
            try:
                body = body.decode()
            except UnicodeDecodeError:
                if self.api.debug:
                    raise
                raise BadRequest(
                    detail="The body of the request could not be decoded."
                )

        # Parse it.
        try:
            obj = self.api.load_json(body)
        except Exception as err:
            if self.api.debug:
                raise
            raise BadRequest(
                detail = "The body of the request does not contain a valid "\
                    "JSON document."
                )
        return obj
