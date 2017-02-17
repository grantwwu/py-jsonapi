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

The :class:`~jsonapi.api.API` class is the glue, which holds all components
together. In the simplest case, it works as container for all  encoders. In a
more advanced setup, the API is also responsible for the request handling
(routing, dispatching, ...).

By overriding the :meth:`API.handle_request` method, it can be easily integrated
in other web frameworks.
"""

# std
from collections import defaultdict
import enum
import json
import logging
import re
import urllib.parse

# thid party
try:
    import bson
    import bson.json_util
except ImportError:
    bson = None

# local
from . import version
from . import errors
from . import handler
from . import response_builder
from . utilities import jsonapi_id_tuple


__all__ = [
    "API"
]


LOG = logging.getLogger(__file__)


# We only need the id of this list.
ARG_DEFAULT = []


class API(object):
    """
    This class is responsible for the request dispatching. It knows all
    resource classes, encoders, includers and api endpoints.

    :arg str uri:
        The root uri of the whole API.
    :arg bool debug:
        If true, exceptions are not catched and the API is more verbose.
    :arg dict settings:
        A dictionary, which can be used by extensions for configuration stuff.
    """

    def __init__(self, uri, debug=True, settings=None):
        """
        """
        # True, if in debug mode.
        # Please note, that we never access the *_debug* attribute direct,
        # only the *debug* property.
        self._debug = debug

        self._uri = uri.rstrip("/")
        self._parsed_uri = urllib.parse.urlparse(self._uri)

        #: A dictionary, which can be used to store configuration values
        #: or data for extensions.
        self.settings = settings or dict()
        assert isinstance(self.settings, dict)

        # typename to encoder, includer, ... and vice versa
        self._encoder = dict()
        self._resource_class_to_encoder = dict()

        self._includer = dict()
        self._resource_class_to_includer = dict()

        # Maps an endpoint name to the handler.
        #
        # ("User", "collection")
        # ("User", "resource")
        # ("User", "related", "posts")
        # ("User", "relationship", "posts")
        #
        # NOTE: The routing and request handling is still open for discussion.
        self._handler = dict()

        # This route dictionary maps a url rule (regex) to a handler.
        # NOTE: The routing and request handling is still open for discussion.
        self._routes = dict()

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
        return None


    @property
    def debug(self):
        """
        When *debug* is *True*, the api is more verbose and exceptions are
        not catched.

        This property *can be overridden* in subclasses to mimic the behaviour
        of the parent framework.
        """
        return self._debug

    @debug.setter
    def debug(self, debug):
        self.debug = bool(debug)
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


    def get_encoder(self, o, default=ARG_DEFAULT):
        """
        Returns the :class:`~jsonapi.encoder.Encoder` associated with *o*.
        *o* must be either a typename, a resource class or resource object.

        :arg o:
            A typename, resource object or a resource class
        :arg default:
            Returned if no encoder for *o* is found.
        :raises KeyError:
            If no encoder for *o* is found and no *default* value is given.
        :rtype: jsonapi.encoder.Encoder:
        """
        encoder = self._encoder.get(o)\
            or self._resource_class_to_encoder.get(o)\
            or self._resource_class_to_encoder.get(type(o))
        if encoder is not None:
            return encoder
        if default is not ARG_DEFAULT:
            return default
        raise KeyError()

    def get_includer(self, o, default=ARG_DEFAULT):
        """
        Returns the :class:`~jsonapi.includer.Includer` associated with *o*.
        *o* must be either a typename, a resource class or resource object.

        :arg o:
            A typename, resource object or a resource class
        :arg default:
            Returned if no includer for *o* is found.
        :raises KeyError:
            If no includer for *o* is found and no *default* value is given.
        :rtype: jsonapi.includer.Includer:
        """
        includer = self._includer.get(o)\
            or self._resource_class_to_includer.get(o)\
            or self._resource_class_to_includer.get(type(o))
        if includer is not None:
            return includer
        if default is not ARG_DEFAULT:
            return default
        raise KeyError()

    def get_typenames(self):
        """
        :rtype: list
        :returns: A list with all typenames known to the API.
        """
        return list(self._encoder.keys())

    def add_type(self, encoder, includer=None):
        """
        Adds an encoder to the API. This method will call
        :meth:`~jsonapi.encoder.Encoder.init_api`, which binds the encoder
        instance to the API.

        :arg ~jsonapi.encoder.Encoder encoder:
        :arg ~jsonapi.includer.Includer includer:
        """
        resource_class = encoder.resource_class
        typename = encoder.typename

        if resource_class is None:
            LOG.warning(
                "The encoder '%s' is not assigned to a resource class.",
                self.typename or type(self).__name__
            )
        if typename is None:
            LOG.warning(
                "The encoder '%s' has no typename.",
                self.typename or type(self).__name__
            )

        # Add the encoder to the API.
        encoder.init_api(self)
        self._encoder[typename] = encoder
        if resource_class is not None:
            self._resource_class_to_encoder[resource_class] = encoder

        # Add the includer to the API.
        if includer is not None:
            includer.init_api(self)
            self._includer[typename] = includer
            if resource_class:
                self._resource_class_to_includer[resource_class] = includer
        return None

    def add_handler(self, handler, typename, endpoint_type, relname=None):
        """
        .. warning::

            The final routing mechanisms and URL patterns are still up for
            discussion.

        Adds a new :class:`~jsonapi.handler.Handler` to the API.

        :arg ~jsonapi.handler.Handler handler:
            A request handler
        :arg str typename:
            The name of the JSON API type, which can be manipulated/accessed
            by this handler.
        :arg str endpoint_type:
            ``"collection"``, ``"resource"``, ``"relationship"``
            or ``"related"``
        :arg str relname:
            The name of the relationship, if the *endpoint_type*
            is ``"related"`` or ``"relationship"``.
        """
        if endpoint_type == "collection":
            self._handler[(typename, endpoint_type)] = handler
            handler.init_api(self)
        elif endpoint_type == "resource":
            self._handler[(typename, endpoint_type)] = handler
            handler.init_api(self)
        elif endpoint_type == "relationship":
            assert relname
            self._handler[(typename, endpoint_type, relname)] = handler
            handler.init_api(self)
        elif endpoint_type == "related":
            assert relname
            self._handler[(typename, endpoint_type, relname)] = handler
            handler.init_api(self)
        return None

    def add_url_rule(self, url_rule, handler):
        """
        Adds a url rule to the known routes.

        :arg str url_rule:
            A regular expression
        :arg ~jsonapi.handler.Handler handler:
            A request handler
        """
        assert url_rule.startswith("/")
        url_rule = self._uri + url_rule
        self._routes[url_rule] = handler
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
            encoder = self.get_encoder(obj)
            return {"type": encoder.typename, "id": encoder.id(obj)}

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
        if isinstance(obj, tuple):
            assert len(obj) == 2
            return jsonapi_id_tuple(str(obj[0]), str(obj[1]))
        elif isinstance(obj, dict):
            return jsonapi_id_tuple(str(obj["type"]), str(obj["id"]))
        else:
            encoder = self.get_encoder(obj)
            return jsonapi_id_tuple(encoder.typename, encoder.id(obj))

    # Handler

    def _get_handler(self, request):
        """
        Returns the handler, which is responsible for the requested endpoint.
        """
        # Check the custom routes first.
        for url_rule, handler in self._routes.items():
            match = re.fullmatch(url_rule, request.parsed_uri.path)
            if match:
                request.japi_uri_arguments.update(match.groupdict())
                return handler

        # The regular expressions, which will match the uri path or not.
        escaped_uri = re.escape(self._uri)
        collection_re = escaped_uri\
            + "/(?P<type>[^/]+?)/?$"
        resource_re = escaped_uri\
            + "/(?P<type>[^/]+?)/(?P<id>[^/]+?)/?$"
        relationship_re = escaped_uri\
            + "/(?P<type>[^/]+?)/(?P<id>[^/]+?)/relationships/(?P<relname>[^/]+?)/?$"
        related_re = escaped_uri\
            + "/(?P<type>[^/]+?)/(?P<id>[^/]+?)/(?P<relname>[^/]+?)/?$"

        # Collection
        match = re.fullmatch(collection_re, request.parsed_uri.path)
        if match:
            request.japi_uri_arguments.update(match.groupdict())
            spec = (match.group("type"), "collection")
            return self._handler.get(spec)

        # Resource
        match = re.fullmatch(resource_re, request.parsed_uri.path)
        if match:
            request.japi_uri_arguments.update(match.groupdict())
            spec = (match.group("type"), "resource")
            return self._handler.get(spec)

        # Relationship
        match = re.fullmatch(relationship_re, request.parsed_uri.path)
        if match:
            request.japi_uri_arguments.update(match.groupdict())
            spec = (match.group("type"), "relationship", match.group("relname"))
            return self._handler.get(spec)

        # Related
        match = re.fullmatch(related_re, request.parsed_uri.path)
        if match:
            request.japi_uri_arguments.update(match.groupdict())
            spec = (match.group("type"), "related", match.group("relname"))
            return self._handler.get(spec)
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
            The request, which should be handled.

        :rtype: ~jsonapi.request.Response
        """
        assert request.api is None or request.api is self
        request.api = self

        try:
            self.prepare_request(request)

            # Find a handler (routing).
            handler = self._get_handler(request)
            if handler is None:
                LOG.debug("Could not find route.")
                raise errors.NotFound()

            # Handle the request.
            resp = handler.handle(request)

            # If the handler only returned a response builder, we need to
            # convert it to a propert response.
            if isinstance(resp, response_builder.ResponseBuilder):
                if isinstance(resp, response_builder.IncludeMixin):
                    resp.fetch_include()
                resp = resp.to_response()
        except errors.Error as err:
            if self.debug:
                raise
            resp = errors.error_to_response(err, dump_json=self.dump_json)
        return resp

    # URLs

    @property
    def uri(self):
        """
        The root uri of the api, which has been provided in the constructor.
        """
        return self._uri

    def collection_uri(self, resource):
        """
        :rtype: str
        :returns: The uri for the resource's collection
        """
        encoder = self.get_encoder(resource)
        return self._uri + "/" + encoder.typename

    def resource_uri(self, resource):
        """
        :rtype: str
        :returns: The uri for the resource
        """
        encoder = self.get_encoder(resource)
        return self._uri + "/" + encoder.typename + "/" + encoder.id(resource)

    def relationship_uri(self, resource, relname):
        """
        :rtype: str
        :returns: The uri for the relationship *relname* of the resource
        """
        encoder = self.get_encoder(resource)

        uri = "{base_uri}/{typename}/{resource_id}/relationships/{relname}"
        uri = uri.format(
            base_uri=self._uri, typename=encoder.typename,
            resource_id=encoder.id(resource), relname=relname
        )
        return uri

    def related_uri(self, resource, relname):
        """
        :rtype: str
        :returns:
            The uri for fetching all related resources in the relationship
            *relname* with the resource.
        """
        encoder = self.get_encoder(resource)

        uri = "{base_uri}/{typename}/{resource_id}/{relname}"
        uri = uri.format(
            base_uri=self._uri, typename=encoder.typename,
            resource_id=encoder.id(resource), relname=relname
        )
        return uri

    # Resource serializer

    def serialize(self, resource, request):
        """
        Chooses the correct serializer for the *resource* and returns the
        serialized version of the resource.

        :arg resource:
            A resource instance, whichs type is known to the API.
        :arg ~jsonapi.request.Request request:
            The request context

        :rtype: dict
        :returns:
            The serialized version of the *resource*.
        """
        encoder = self.get_encoder(resource)
        return encoder.serialize_resource(resource, request)

    def serialize_many(self, resources, request):
        """
        The same as :meth:`serialize`, but for many resources.

        :rtype: list
        :returns:
            A list with the serialized versions of all *resources*.
        """
        return [self.serialize(resource, request) for resource in resources]
