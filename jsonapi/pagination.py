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
jsonapi.pagination
==================

This module contains helper for the pagination feature:
http://jsonapi.org/format/#fetching-pagination

We have built-in support for:

*   *limit*, *offset* based pagination (:class:`LimitOffset`),
*   *number*, *size* based pagination (:class:`NumberSize`),
*   and *cursor* based pagination (:class:`Cursor`).

All helpers have a similar interface. Here is an example for the
:class:`NumberSize` pagination:

.. code-block:: python3

    >>> p = NumberSize(
    ...     uri="http://example.org/api/Article/?sort=date_added&page[size]=5&page[number]=10)",
    ...     number=2,
    ...     size=25,
    ...     total_resources=106
    )
    >>> p.json_links()
    {
    'first': 'http://example.org/api/Article/?page%5Bsize%5D=25&sort=date_added&page%5Bnumber%5D=0',
    'last': 'http://example.org/api/Article/?page%5Bsize%5D=25&sort=date_added&page%5Bnumber%5D=4',
    'next': 'http://example.org/api/Article/?page%5Bsize%5D=25&sort=date_added&page%5Bnumber%5D=3',
    'prev': 'http://example.org/api/Article/?page%5Bsize%5D=25&sort=date_added&page%5Bnumber%5D=1',
    'self': 'http://example.org/api/Article/?page%5Bsize%5D=25&sort=date_added&page%5Bnumber%5D=2'
    }
    >>> p.meta()
    {
    'page-number': 2,
    'page-size': 25,
    'total-pages': 4,
    'total-resources': 106
    }
"""

# std
import logging
import urllib.parse
import re

# local
from .utilities import Symbol
from .errors import BadRequest


__all__ = [
    "DEFAULT_LIMIT",
    "BasePagination",
    "LimitOffset",
    "NumberSize",
    "Cursor"
]

LOG = logging.getLogger(__file__)

#: The default number of resources on a page.
DEFAULT_LIMIT = 25


class BasePagination(object):
    """
    The base class for all pagination helpers.
    """

    def __init__(self, uri):
        self._uri = uri
        self._parsed_uri = urllib.parse.urlparse(uri)
        self._query_uri = urllib.parse.parse_qs(self._parsed_uri.query)
        return None

    @classmethod
    def from_request(self, request, **kargs):
        """
        Checks if the needed pagination parameters are present in the request
        and if so, a new pagination instance with these parameters is returned
        and *None* otherwise.

        :seealso: :meth:`jsonapi.request.Request.get_query_argument`
        """
        raise NotImplementedError()

    @property
    def uri(self):
        return self._uri

    def page_link(self, pagination):
        """
        Uses the :attr:`uri` and replaces the *page* query parameters with the
        values in *pagination*.

        .. code-block:: python3

            pager.page_link({"offset": 10, "limit": 5})
            pager.page_link({"number": 10, "size": 5})
            pager.page_link({"cursor": 1, "limit": 5})
            # ...

        :arg dict pagination:
            Query parameters for the pagination.
        :rtype: str
        :returns:
            The url to the page
        """
        query = self._query_uri.copy()
        query.update({
            "page[{}]".format(key): str(value) for key, value in pagination.items()
        })
        query = urllib.parse.urlencode(query, doseq=True)

        uri = "{scheme}://{netloc}{path}?{query}".format(
            scheme=self._parsed_uri.scheme,
            netloc=self._parsed_uri.netloc,
            path=self._parsed_uri.path,
            query=query
        )
        return uri

    def json_meta(self):
        """
        **Must be overridden.**

        A dictionary, which must be included in the top-level *meta object*.
        """
        return dict()

    def json_links(self):
        """
        **Must be overridden.**

        A dictionary, which must be included in the top-level *links object*. It
        contains these keys:

        *   *self*
            The link to the current page

        *   *first*
            The link to the first page

        *   *last*
            The link to the last page

        *   *prev*
            The link to the previous page (only set, if a previous page exists)

        *   *next*
            The link to the next page (only set, if a next page exists)
        """
        raise NotImplementedError()


class LimitOffset(BasePagination):
    """
    Implements a pagination based on *limit* and *offset* values.

    .. code-block:: text

        /api/Article/?sort=date_added&page[limit]=5&page[offset]=10

    :arg str uri:
    :arg int limit:
        The number of resources on a page.
    :arg int offset:
        The offset, which leads to the current page.
    :arg int total_resources:
        The total number of resources in the collection.
    """

    def __init__(self, uri, limit, offset, total_resources):
        super().__init__(uri=uri)

        assert offset >= 0
        assert total_resources >= 0
        assert limit > 0

        #: The number of resources on a page.
        self.limit = limit

        #: The offset, which leads to the current page
        self.offset = offset

        #: The total number of resources in the collection
        self.total_resources = total_resources
        return None

    @classmethod
    def from_request(
            cls, request, total_resources, default_limit=DEFAULT_LIMIT
        ):
        """
        Extracts the current pagination values (*limit* and *offset*) from the
        request's query parameters.

        :arg ~jsonapi.request.Request request:
        :arg int total_resources:
            The total number of resources in the collection.
        :arg int default_limit:
            If the request's query string does not contain a limit,
            we will use this one as fallback value.
        """
        limit = request.get_query_argument("page[limit]")
        if limit is not None and ((not limit.isdigit()) or int(limit) <= 0):
            raise BadRequest(
                detail="The limit must be an integer > 0.",
                source_parameter="page[limit]"
            )
        if limit is None:
            limit = default_limit

        offset = request.get_query_argument("page[offset]")
        if offset is not None and ((not offset.isdigit()) or int(offset) < 0):
            raise BadRequest(
                detail="The offset must be an integer >= 0.",
                source_parameter="page[offset]"
            )
        if offset is None:
            offset = 0

        if offset%limit != 0:
            LOG.warning("The offset is not dividable by the limit.")
        return cls(request.uri, limit, offset, total_resources)

    def json_links(self):
        """
        """
        d = dict()
        d["self"] = self.page_link({
            "limit": self.limit,
            "offset": self.offset
        })
        d["first"] = self.page_link({
            "limit": self.limit,
            "offset": 0
        })
        d["last"] = self.page_link({
            "limit": self.limit,
            "offset": int((self.total_resources - 1)/self.limit)*self.limit
        })
        if self.offset > 0:
            d["prev"] = self.page_link({
                "limit": self.limit,
                "offset": max(self.offset - self.limit, 0)
            })
        if self.offset + self.limit < self.total_resources:
            d["next"] = self.page_link({
                "limit": self.limit,
                "offset": self.offset + self.limit
            })
        return d

    def json_meta(self):
        """
        Returns a dictionary with

        *   *total-resources*
            The total number of resources in the collection
        *   *page-limit*
            The number of resources on a page
        *   *page-offset*
            The offset of the current page
        """
        d = dict()
        d["total-resources"] = self.total_resources
        d["page-limit"] = self.limit
        d["page-offset"] = self.offset
        return d


class NumberSize(BasePagination):
    """
    Implements a pagination based on *number* and *size* values.

    .. code-block:: text

        /api/Article/?sort=date_added&page[size]=5&page[number]=10

    :arg str uri:
    :arg int number:
        The number of the current page.
    :arg int size:
        The number of resources on a page.
    :arg int total_resources:
        The total number of resources in the collection.
    """

    def __init__(self, uri, number, size, total_resources):
        super().__init__(uri=uri)

        assert number >= 0
        assert size > 0
        assert total_resources >= 0

        #: The current page number
        self.number = number

        #: The number of resources on a page
        self.size = size

        #: The total number of resources in the collection
        self.total_resources = total_resources
        return None

    @classmethod
    def from_request(
        cls, request, total_resources, default_size=DEFAULT_LIMIT
        ):
        """
        Extracts the current pagination values (*size* and *number*) from the
        request's query parameters.

        :arg ~jsonapi.request.Request request:
        :arg int total_resources:
            The total number of resources in the collection.
        :arg int default_size:
            If the request's query string does not contain the page size
            parameter, we will use this one as fallback.
        """
        number = request.get_query_argument("page[number]")
        if number is not None and ((not number.isdigit()) or int(number) < 0):
            raise BadRequest(
                detail="The number must an integer >= 0.",
                source_parameter="page[number]"
            )
        number = int(number) if number else 0

        size = request.get_query_argument("page[size]")
        if size is not None and ((not size.isdigit()) or int(size) <= 0):
            raise BadRequest(
                detail="The size must be an integer > 0.",
                source_parameter="page[size]"
            )
        if size is None:
            size = default_size
        size = int(size) if size else 0
        return cls(request.uri, number, size, total_resources)

    @property
    def limit(self):
        """
        The limit, based on the page :attr:`size`.
        """
        return self.size

    @property
    def offset(self):
        """
        The offset, based on the page :attr:`size` and :attr:`number`.
        """
        return self.size*self.number

    @property
    def last_page(self):
        """
        The number of the last page.
        """
        return int((self.total_resources - 1)/self.size)

    def json_links(self):
        """
        """
        d = dict()
        d["self"] = self.page_link({
            "number": self.number,
            "size": self.size
        })
        d["first"] = self.page_link({
            "number": 0,
            "size": self.size
        })
        d["last"] = self.page_link({
            "number": self.last_page,
            "size": self.size
        })
        if self.number > 0:
            d["prev"] = self.page_link({
                "number": self.number - 1,
                "size": self.size
            })
        if self.number < self.last_page:
            d["next"] = self.page_link({
                "number": self.number + 1,
                "size": self.size
            })
        return d

    def json_meta(self):
        """
        Returns a dictionary with

        *   *total-resources*
            The total number of resources in the collection
        *   *last-page*
            The index of the last page
        *   *page-number*
            The number of the current page
        *   *page-size*
            The (maximum) number of resources on a page
        """
        d = dict()
        d["total-resources"] = self.total_resources
        d["last-page"] = self.last_page
        d["page-number"] = self.number
        d["page-size"] = self.size
        return d


class Cursor(BasePagination):
    """
    Implements a (generic) approach for a cursor based pagination.

    .. code-block:: text

        /api/Article/?sort=date_added&page[limit]=5&page[cursor]=19395939020

    :arg str uri:
    :arg int limit:
        The number of resources on a page
    :arg cursor:
        The cursor to the current page
    :arg prev_cursor:
        The cursor to the previous page
    :arg next_cursor:
        The cursor to the next page
    """

    #: The cursor to the first page
    FIRST = Symbol("jsonapi:first")

    #: The cursor to the last page
    LAST = Symbol("jsonapi:last")

    def __init__(self, uri, limit, cursor, prev_cursor=None, next_cursor=None):
        super().__init__(uri=uri)
        assert limit > 0

        #: The page size
        self.limit = limit

        #: The cursor to the current page.
        self.cursor = cursor

        #: The cursor to the previous page.
        self.prev_cursor = prev_cursor

        #: The cursor to the next page.
        self.next_cursor = next_cursor
        return None

    @classmethod
    def from_request(cls, request, default_limit=DEFAULT_LIMIT, cursor_re=None):
        """
        Extracts the current pagination values (*limit* and *cursor*) from the
        request's query parameters.

        :arg ~jsonapi.request.Request request:
        :arg int default_limit:
             If the request’s query string does not contain a limit,
             we will use this one as fallback value.
        :arg str cursor_re:
            The cursor in the query string must match this regular expression.
            If it doesn't, an exception is raised.
        """
        cursor = request.get_query_argument("page[cursor]", cls.FIRST)
        if cursor is not None and cursor_re \
            and (not re.fullmatch(cursor_re, cursor)):
            raise BadRequest(
                detail="The cursor is invalid.",
                source_parameter="page[cursor]"
            )

        limit = request.get_query_argument("page[limit]")
        if limit is not None and ((not limit.isdigit()) or int(limit) <= 0):
            raise BadRequest(
                detail="The limit must be an integer > 0.",
                source_parameter="page[limit]"
            )
        if limit is None:
            limit = default_limit
        return cls(request.uri, limit, cursor)

    def json_links(self, prev_cursor=None, next_cursor=None):
        """
        :arg str prev_cursor:
            The cursor to the previous page.
        :arg str next_cursor:
            The cursor to the next page.
        """
        if prev_cursor is None:
            prev_cursor = self.prev_cursor
        if next_cursor is None:
            next_cursor = self.next_cursor

        d = dict()
        d["self"] = self.page_link({
            "cursor": str(self.cursor),
            "limit": self.limit
        })
        d["first"] = self.page_link({
            "cursor": str(self.FIRST),
            "limit": self.limit
        })
        d["last"] = self.page_link({
            "cursor": str(self.LAST),
            "limit": self.limit
        })
        if next_cursor is not None:
            d["next"] = self.page_link({
                "cursor": str(next_cursor),
                "limit": self.limit
            })
        if prev_cursor is not None:
            d["prev"] = self.page_link({
                "cursor": str(prev_cursor),
                "limit": self.limit
            })
        return d

    def json_meta(self):
        """
        Returns a dictionary with

        *   *page-limit*
            The number of resources per page
        """
        d = dict()
        d["page-limit"] = self.limit
        return d
