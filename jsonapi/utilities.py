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
jsonapi.utilities
=================

This module contains some helpers, which are frequently needed in different
modules and situations.
"""

# std
import collections
import warnings


__all__ = [
    "Symbol",
    "jsonapi_id_tuple",
    "collect_identifiers",
    "rebase_include",
    "class_property"
]


class Symbol(object):
    """
    A simple symbol implementation.

    .. code-block:: python3

        foo = Symbol()
        assert foo == foo

        bar = Symbol()
        assert bar != foo

        assert Symbol("foo") != Symbol("foo")
    """

    def __init__(self, name=""):
        self.name = name
        return None

    def __str__(self):
        return self.name if self.name else self.__repr__(self)

    def __repr__(self):
        return "Symbol(name={})".format(self.name)

    def __eq__(self, other):
        return other is self

    def __ne__(self, other):
        return other is not self


#: A named tuple for JSON API identifiers:
#:
#: .. code-block:: python3
#:
#:      jsonapi_id_tuple(type="Article", id="42")
jsonapi_id_tuple = collections.namedtuple("jsonapi_id_tuple", ["type", "id"])


def collect_identifiers(d, with_data=True, with_meta=False):
    """
    Returns all identifers found in the document *d*:

    .. code-block:: python3

        >>> d = {
        ...     "author": {
        ...         "data": {"type": "User", "id": "42"}
        ...     }
        ...     "comments": {
        ...         "data": [
        ...             {"type": "Comment", "id": "2"},
        ...             {"type": "Comment", "id": "3"}
        ...         ]
        ...     }
        ... }
        >>> collect_identifiers(d)
        {("User", "42"), ("Comment", "2"), ("Comment", "3")}

    :arg dict d:
    :arg bool with_data:
        If true, we check recursive in all *data* objects for identifiers.
    :arg bool with_meta:
        If true, we check recursive in all *meta* objects for identifiers.

    :rtype: set
    :returns:
        A set with all found identifier tuples.
    """
    ids = set()
    docs = [d]
    while docs:
        d = docs.pop()

        if isinstance(d, list):
            for value in d:
                if isinstance(value, (dict, list)):
                    docs.append(value)

        elif isinstance(d, dict):
            if "id" in d and "type" in d:
                ids.add(jsonapi_id_tuple(d["type"], d["id"]))

            for key, value in d.items():
                if key == "meta" and not with_meta:
                    continue
                if key == "data" and not with_data:
                    continue
                if isinstance(value, (dict, list)):
                    docs.append(value)
    return ids


def rebase_include(new_root, include):
    """
    Adds *new_root* to each include path in *include*.

    .. code-block:: python3

        >>> rebase_include("articles", [["comments"], ["posts"]])
        [["articles", "comments"], ["articles", "posts"]]
        >>> rebase_include("articles", [])
        [["articles"]]

    :arg str new_root:
        The new root of all include paths
    :arg list include:
        A list of include paths

    :rtype: list
    :returns:
        The new list of include paths.
    """
    if not include:
        rebased = [[new_root]]
    else:
        rebased = [[new_root] + path for path in include]
    return rebased
