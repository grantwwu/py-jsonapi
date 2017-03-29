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
jsonapi.router
==============

This module contains the implementation of a simple router based on regular
expressions.
"""

__all__ = [
    "Router"
]

# std
import re


class Router(object):
    """
    .. seealso::

        http://jsonapi.org/recommendations/#urls

    A symple router based on the different endpoint types specified by
    http://jsonapi.org.

    :arg str base_url:
        The base url for all (automic generated) api endpoints.
    :arg ~jsonapi.api.API:
        The API which owns this router.
    """

    #: Matchs a segement in the url:
    #:
    #:  /api/Article/{id}
    #:  /api/Article/{id:\d+}
    ROUTE_RE = re.compile("\{(?P<name>[A-z_][A-z0-9_]*)(:(?P<re>.*?))?\}")

    def __init__(self, base_url, api=None):
        """ """
        self._api = api
        self._base_url = base_url

        # name to url spec
        self._specs = {}

        # alternative name to real name
        self._name_alias = {}
        return None

    def init_api(self, api):
        """Binds this router to the API."""
        assert self._api is None or self._api is api
        self._api = api
        return None

    @property
    def base_url(self):
        return self._base_url

    @property
    def api(self):
        return self._api

    def add_url(self, name, pattern, handler, *, name_alias=None):
        """
        Adds a new route to the endpoint with the name *name*. Pattern describes
        the URL for the endpoint::

            "/api/Article/{id}"

        You can also specify regular expressions for the parameters::

            "/api/Article/{id:[0-9]+}"

        :arg str name:
            The name of the endpoint.
        :arg str pattern:
            The URL pattern
        :arg ~jsonapi.handler.Handler handler:
            The handler for this endpoint
        :arg list name_alias:
            A list with alternative *names*. E.g.: You prefer to name
            the route for the *Article* collection *articles*, but *py-jsonapi*
            assumes that route must also be registered under the
            *Article-collection*.
        """
        handler.init_api(self.api)

        # Collect all parameters and build the formatter string for the
        # URL.
        params = []
        builder = ""
        url = ""
        index = 0
        for param in self.ROUTE_RE.finditer(pattern):
            params.append(param.groupdict())

            builder += pattern[index:param.start()]
            builder += "{" + param.group("name") + "}"

            url += pattern[index:param.start()]
            url += "(?P<{0}>{1})".format(
                param.group("name"), param.group("re") or "[^/]*?"
            )

            index = param.end()

        builder += pattern[index:]
        url += pattern[index:]

        # Save the specification.
        self._specs[name] = {
            "pattern": pattern,
            "url": re.compile(url),
            "parameters": params,
            "builder": builder,
            "handler": handler
        }

        self._name_alias[name] = name
        if name_alias:
            for alias in name_alias:
                self._name_alias[alias] = name
        return None

    def url(self, name, **kargs):
        """
        Builds the URL for an endpoint::

            router.url_for("article-resource", id=10)

        :arg str name:
            The name of the endpoint.
        :arg \*\*kargs:
            The parameters in the URL.
        """
        name = self._name_alias[name]
        spec = self._specs[name]
        return spec["builder"].format(**kargs)

    def get_handler(self, path):
        """
        Returns the handler whichs URL path matches *path*. The parameters
        encoded in the URL are returned too::

            params, handler = router.get_handler("/api/Article/10")

        :arg str path:
            The path of the requested URL
        """
        for spec in self._specs.values():
            m = spec["url"].fullmatch(path)
            if m:
                return (m.groupdict(), spec["handler"])
        return None

    def add_collection_url(self, handler, type):
        """
        Creates the route for the *collection* endpoint of the JSON API type
        *type*::

            router.add_collection_url(handler, schema.type)

        :seealso: http://jsonapi.org/recommendations/#urls-resource-collections
        """
        name = type + "-collection"
        pattern = self._base_url + "/" + type
        return self.add_url(name, pattern, handler)

    def add_resource_url(self, handler, type):
        """
        Creates the route for the *resource* endpoint of the JSON API type
        *type*::

            router.add_resource_url(handler, schema.type)

        :seealso: http://jsonapi.org/recommendations/#urls-individual-resources
        """
        name = type + "-resource"
        pattern = self._base_url + "/" + type + "/{id}"
        return self.add_url(name, pattern, handler)

    def add_relationship_url(self, handler, type, relname):
        """
        Creates the route to a relationship endpoint::

            router.add_relationship_url(handler, schema.type, "author")

        :seealso: http://jsonapi.org/recommendations/#urls-relationships
        """
        name = type + "-relationship-" + relname
        pattern = self._base_url + "/" + type + "/{id}/relationship/" + relname
        return self.add_url(name, pattern, handler)

    def add_related_url(self, handler, type, relname):
        """
        Creates the route to a *related* endpoint::

            router.add_related_url(handler, schema.type, "author")

        :seealso: http://jsonapi.org/recommendations/#urls-relationships
        """
        name = type + "-related-" + relname
        pattern = self._base_url + "/" + type + "/{id}/" + relname
        return self.add_url(name, pattern, handler)

    def collection_url(self, type):
        """
        Returns the URL for the collection of the given *type*.
        """
        name = type + "-collection"
        return self.url(name)

    def resource_url(self, type, id):
        """
        Returns the URL for the resource of the type *type* and the id *id*.
        """
        name = type + "-resource"
        return self.url(name, id=id)

    def relationship_url(self, type, id, relname):
        """
        Returns the URL for the relationship *relname*.
        """
        name = type + "-relationship-" + relname
        return self.url(name, id=id)

    def related_url(self, type, id, relname):
        """
        Returns the URL for getting the resources in the relationship
        *relname*.
        """
        name = type + "-related-" + relname
        return self.url(name, id=id)
