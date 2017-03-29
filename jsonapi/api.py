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
jsonapi.api
===========

The :class:`~jsonapi.api.API` class is the piece, which puts all components
together. It sets up the request context and allows you to encode resources
easily.

By overriding the :meth:`API.handle_request` method, it can be easily integrated
in other web frameworks.
"""

# std
from collections import defaultdict, Sequence
import json
import logging
import threading

# thid party
try:
    import bson
    import bson.json_util
except ImportError:
    bson = None

# local
from . import version
from .errors import NotFound, Error, ErrorList, error_to_response
from . import response_builder
from .router import Router
from .utilities import jsonapi_id_tuple, Symbol


__all__ = [
    "API"
]


LOG = logging.getLogger(__file__)

ARG_DEFAULT = Symbol("ARG_DEFAULT")


class API(object):
    """
    This class is responsible for the request dispatching. It knows all
    resource classes, encoders, includers and api endpoints.

    :arg str uri:
        The base URL for all API endpoints.
    :arg bool debug:
        If true, exceptions are not catched and the API is more verbose.
    :arg dict settings:
        A dictionary, which can be used by extensions for configuration stuff.
    """

    def __init__(self, uri="/api", debug=True, settings=None):
        """ """
        #: When *debug* is *True*, the api is more verbose and exceptions are
        #: not catched.
        #:
        #: This property *can be overridden* in subclasses to mimic the
        #: behaviour of the parent framework.
        self.debug = debug

        #: A dictionary, which can be used to store configuration values
        #: or data for extensions.
        self.settings = settings or {}
        assert isinstance(self.settings, dict)

        #: The :class:`~jsonapi.router.Router` used to determine the URLs
        #: for relationships, collections, ...
        #: Feel free to add your own handlers to the router.
        self.router = Router(base_url=uri, api=self)

        #: The global jsonapi object, which is added to each response.
        #:
        #: You can add meta information to the ``jsonapi_object["meta"]``
        #: dictionary if you want.
        #:
        #: :seealso: http://jsonapi.org/format/#document-jsonapi-object
        self.jsonapi_object = dict()
        self.jsonapi_object["version"] = version.jsonapi_version
        self.jsonapi_object["meta"] = dict()
        self.jsonapi_object["meta"]["py-jsonapi-version"] = version.version

        # typename to schema
        self._schema_by_type = {}

        # resource class to schema
        self._schema_by_resource_class = {}
        return None

    def dump_json(self, obj):
        """
        Serializes the Python object *obj* to a JSON string.

        The default implementation uses Python's :mod:`json` module with some
        features from :mod:`bson` (if it is available).

        You *can* override this method.
        """
        indent = 4 if self.debug else None
        default = bson.json_util.default if bson else None
        sort_keys = self.debug
        return json.dumps(obj, indent=indent, default=default, sort_keys=sort_keys)

    def load_json(self, obj):
        """
        Decodes the JSON string *obj* and returns a corresponding Python object.

        The default implementation uses Python's :mod:`json` module with some
        features from :mod:`bson` (if available).

        You *can* override this method.
        """
        default = bson.json_util.object_hook if bson else None
        return json.loads(obj, object_hook=default)


    def get_schema(self, o, default=ARG_DEFAULT):
        """
        Returns the :class:`~jsonapi.schema.schema.Schema` associated with *o*.
        *o* must be either a typename, a resource class or resource object.

        :arg o:
            A typename, resource object or a resource class
        :arg default:
            Returned if no schema for *o* is found.
        :raises KeyError:
            If no schema for *o* is found and no *default* value is given.
        :rtype: ~jsonapi.schema.schema.Schema
        """
        schema = self._schema_by_type.get(o)\
            or self._schema_by_resource_class.get(o)\
            or self._schema_by_resource_class.get(type(o))

        if schema is not None:
            return schema
        if default != ARG_DEFAULT:
            return default
        raise KeyError()

    def get_typenames(self):
        """
        :rtype: list
        :returns: A list with all typenames known to the API.
        """
        return list(self._schema_by_type.keys())

    def add_schema(self, schema, add_handlers=True):
        """
        Adds a schema to the API. This method will call
        :meth:`~jsonapi.schema.schema.Schema.init_api`, which binds the schema
        instance to the API.

        :arg ~jsonapi.schema.schema.Schema schema:
        :arg bool add_handlers:
            If *true*, the request handlers for this schema are created
            automatic.
        """
        if schema.resource_class is None:
            LOG.warning(
                "The schema '%s' is not bound to a resource class.",
                schema.typename
            )

        schema.init_api(self)
        self._schema_by_type[schema.type] = schema
        if schema.resource_class:
            self._schema_by_resource_class[schema.resource_class] = schema

        if add_handlers:
            handler = schema.handler.Collection(api=self, schema=schema)
            self.router.add_collection_url(handler, schema.type)

            handler = schema.handler.Resource(api=self, schema=schema)
            self.router.add_resource_url(handler, schema.type)

            for relname in schema.japi_relationships.values():
                handler = schema.handler.Relationship(
                    api=self, schema=schema, relname=relname
                )
                self.router.add_relationship_url(handler, schema.type, relname)

                handler = schema.handler.Related(
                    api=self, schema=schema, relname=relname
                )
                self.router.add_related_url(handler, schema.type, relname)
        return None

    # Utilities

    def ensure_identifier_object(self, obj):
        """
        Converts *obj* into an identifier object:

        .. code-block:: python3

            {
                "type": "people",
                "id": "42"
            }

        :arg obj:
            A two tuple ``(typename, id)``, a resource object or a resource
            document, which contains the *id* and *type* key
            ``{"type": ..., "id": ...}``.

        :seealso: http://jsonapi.org/format/#document-resource-identifier-objects
        """
        # None
        if obj is None:
            return None
        # Identifier tuple
        elif isinstance(obj, tuple):
            return {"type": str(obj[0]), "id": str(obj[1])}
        # JSONapi identifier object
        elif isinstance(obj, dict):
            # The dictionary may contain more keys than only *id* and *type*. So
            # we extract only these two keys.
            return {"type": str(obj["type"]), "id": str(obj["id"])}
        # obj is a resource
        else:
            schema = self.get_schema(obj)
            return {"type": schema.type, "id": schema.id(obj)}

    def ensure_identifier(self, obj):
        """
        Does the same as :meth:`ensure_identifier_object`, but returns the two
        tuple identifier object instead of the document:

        .. code-block:: python3

            # (typename, id)
            ("people", "42")

        :arg obj:
            A two tuple ``(typename, id)``, a resource object or a resource
            document, which contains the *id* and *type* key
            ``{"type": ..., "id": ...}``.
        """
        if isinstance(obj, collections.Sequence):
            assert len(obj) == 2
            return jsonapi_id_tuple(str(obj[0]), str(obj[1]))
        elif isinstance(obj, dict):
            return jsonapi_id_tuple(str(obj["type"]), str(obj["id"]))
        else:
            schema = self.get_schema(obj)
            return jsonapi_id_tuple(schema.type, schema.id(obj))

    def _include(self, parent, path, included_resources, included_relationships):
        """
        Fetches the relationship path *path* recursively.
        """
        if not path:
            return None

        relname, *path = path
        if relname in included_relationships[parent]:
            return None

        schema = self.get_schema(resource)
        relatives = schema.fetch_include(resource, relname)

        for relative in relatives:
            relative_id = self.ensure_identifier(relative)
            included_resources[relative_id] = relative
            included_relationships[relative_id].add(relname)

            self._include(
                relative, path, included_resources, included_relationships
            )
        return None

    def include(self, primary, paths):
        """
        .. seealso::

            http://jsonapi.org/format/#fetching-includes

        Fetches the relationship paths *paths*.

        :arg list primary:
            A list with the primary data (resources) of the compound
            response document.
        :arg list paths:
            A list of relationship paths. E.g.
            ``[["comments.author"], ["author"]]``

        :returns:
            A two tuple with a list of the included resources and a dictionary,
            which maps each resource (primary and included) to a set with the
            names of the included relationships.
        """
        # id -> resource
        included_resources = {}

        # id -> included relationship names
        included_relationships = defaultdict(set)

        for resource in resources:
            self._include(
                resource, path, included_resources, included_relationships
            )
        return (included_resources, included_relationships)

    # Request handling

    _REQUEST_LOCAL = threading.local()

    @property
    def current_request(self):
        """
        The currently handled :class:`~jsonapi.request.Request`.
        """
        return self._REQUEST_LOCAL.request

    @contextlib.contextmanager
    def request_context(self, request):
        """
        Contextmanager for changing the current request context::

            with api.request_context(request):
                pass
        """
        assert request.api is None or request.api is self
        request.api = self

        old = self._REQUEST_LOCAL.request
        self._REQUEST_LOCAL = request
        yield
        self._REQUEST_LOCAL = old
        return None

    def prepare_request(self, request):
        """
        Called, before the :meth:`~jsonapi.handler.Handler.handle`
        method of the request handler.

        You *can* overridde this method to modify the request. (Add some
        settings, headers, a database connection...).

        .. code-block:: python3

            def prepare_request(self, request):
                super().prepare_request(request)
                request.settings["db"] = DBSession()
                request.settings["user"] = current_user
                request.settings["oauth"] = current_oauth_client
                return None
        """
        return None

    def handle_request(self, request):
        """
        Handles a request and returns a response object.

        This method should be overridden for integration in other frameworks.
        It is the **entry point** for all requests handled by this API instance.

        :arg ~jsonapi.request.Request request:
            The request which should be handled.

        :rtype: ~jsonapi.request.Response
        """
        with self.request_context(request):
            try:
                self.prepare_request(request)

                handler = self.router.get_handler(request.parsed_uri.path)
                if handler is None:
                    raise NotFound()

                resp = handler.handle(request)

                # If the handler only returned a response builder, we need to
                # convert it to a propert response.
                if isinstance(resp, ResponseBuilder):
                    if isinstance(resp, IncludeMixin):
                        resp.included = self.include(resp.data, request.japi_include)
                    resp = resp.to_response()
            except (Error, ErrorList) as err:
                if self.debug:
                    raise
                resp = error_to_response(err, dump_json=self.dump_json)
            return resp
