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
jsonapi.response_builder
========================

The response builders make it easier to create common response types (
collection, resource, new resource, relationship, ...).
"""

# std
import logging

# local
from .response import Response


__all__ = [
    "ResponseBuilder",
    "Collection",
    "Resource",
    "NewResource",
    "Relationship",
    "MetaOnly"
]


LOG = logging.getLogger(__file__)


class ResponseBuilder(object):
    """
    This class helps building a JSON API response.

    :arg ~jsonapi.request.Request request:
        The request, to which this object responds
    """

    def __init__(self, request):
        self.__request = request
        self.__api = request.api
        return None

    @property
    def api(self):
        """The :class:`~jsonapi.api.API`, which handles the :attr:`request`."""
        return self.__api

    @property
    def request(self):
        """The current request."""
        return self.__request

    def render(self):
        """
        :rtype: dict
        :returns:
            The JSON API response document
        """
        d = {}
        d["jsonapi"] = self.__api.jsonapi_object
        return d

    def to_response(self, status=200, headers=None):
        """
        Builds the :class:`~jsonapi.response.Response` and sets
        the ``application/vnd.api+json`` content type header.

        :rtype: ~jsonapi.response.Response
        """
        headers = headers or dict()
        headers["content-type"] = "application/vnd.api+json"

        body = self.render()
        body = self.__api.dump_json(body)

        resp = Response(status=status, headers=headers, body=body)
        return resp


class IncludeMixin(object):
    """
    """

    def __init__(self, included=None):
        """ """
        self.included = dict()
        self.included_relationships = dict()
        return None

    def _fetch_include_path(self, resource, path):
        """ """
        if not path:
            return None

        relname, *path = path

        schema = self.api.get_schema(resource)
        relatives = schema.fetch_include(resource, relname)
        return None
        
    def fetch_include(self):
        """ """
        return None


class Collection(ResponseBuilder):
    """
    Builds a collection response. The primary :attr:`data` contains a list
    of resources.

    :arg ~jsonapi.request.Request request:
        The current request
    :arg list data:
        A list of resources from the same type
    :arg list included:
        A list of all related resources, which should be included into the
        response.
    :arg dict links:
        The JSON API links object
    :arg dict meta:
        The JSON API meta object
    :arg ~jsonapi.pagination.BasePagination pagination:
        A pagination instance, which describes the pagination of the collection.
    """

    def __init__(
        self, request, *, data=None, included=None, links=None, meta=None,
        pagination=None
        ):
        """
        """
        super().__init__(request=request)

        #: A list of resources from the same type.
        self.data = data or dict()

        #: A list of all related resources, which should be included into the
        #: response.
        #: :seealso: :attr:`~jsonapi.request.Request.japi_include`
        self.included = included or dict()

        #: The JSON API links object.
        self.links = links or dict()

        #: The JSON API meta object.
        self.meta = meta or dict()

        #: The pagination, which is used for the collection.
        self.pagination = pagination
        return None

    def _render_data(self):
        """ """
        japi_fields = self.__request.japi_fields
        data = []

        for japi_id, resource in self.data.items():
            schema = self.__api.get_schema(japi_id.type)
            encoded = schema.encode_resource(
                resource,
                is_data=True,
                fieldset=japi_fields.get(japi_id.type),
                included=self.include_memo[japi_id]
            )
        return None

    def _render_included(self):
        """ """
        japi_fields = self.__request.japi_fields
        data = []

        for japi_id, resource in self.included.items():
            schema = self.__api.get_schema(japi_id.type)
            encoded = schema.encode_resource(
                resource,
                is_included=True,
                fieldset=japi_fields.get(japi_id.type),
                included=self.include_memo[japi_id]
            )
        return data

    def render(self):
        """
        """
        d = super().render()
        d["data"] = self.api.encode_many(self.data, context="data")
        if self.included:
            d["included"] = self.api.encode_many(self.included, context="include")
        if self.links:
            d["links"] = self.links
        if self.meta:
            d["meta"] = self.meta

        if self.pagination is not None:
            d.setdefault("links", dict()).update(self.pagination.json_links())
            d.setdefault("meta", dict()).update(self.pagination.json_meta())
        return d


class Resource(ResponseBuilder):
    """
    Contains a resource or ``None`` as primary :attr:`data`.

    :arg ~jsonapi.request.Request request:
        The current request
    :arg data:
        A single resource or ``None``.
    :arg list included:
        A list of all related resources, which should be included into the
        response.
    :arg dict links:
        The JSON API links object
    :arg dict meta:
        The JSON API meta object
    """

    def __init__(
        self, request, *, data=None, included=None, links=None, meta=None
        ):
        """
        """
        ResponseBuilder.__init__(self, request=request)

        self.data = data
        self.included = included or list()
        self.links = links or dict()
        self.meta = meta or dict()
        return None

    def render(self):
        """
        """
        d = super().render()

        if self.data is None:
            d["data"] = None
        else:
            d["data"] = self.api.serialize(self.data, self.request)

        if self.included:
            d["included"] = self.api.serialize_many(self.included, self.request)
        if self.links:
            d["links"] = self.links
        if self.meta:
            d["meta"] = self.meta
        return d


class NewResource(Resource):
    """
    The same as :class:`~jsonapi.response_builder.Resource` but also sets
    the ``LOCATION`` header and should be used for a new resource, which has
    been created during the request handling.
    """

    def to_response(self, status=200, headers=None):
        """
        """
        headers = headers or dict()
        headers["location"] = self.api.resource_uri(self.data)
        return super().to_response(status=status, headers=headers)


class Relationship(ResponseBuilder):
    """
    Builds a JSON API response, which contains a relationship.

    :arg ~jsonapi.request.Request request:
        The current request
    :arg resource:
        A resource object
    :arg str relname:
        The name of the relationship, which is returned in the response.
        If not given, we will extract the name from the request.
    :arg ~jsonapi.pagination.BasePagination pagination:
        A pagination instance, which describes the pagination of the collection.
        (Only *to-many* relationships should support pagination.)
    """

    def __init__(
        self, request, *, resource=None, relname=None, pagination=None
        ):
        """
        """
        super().__init__(request=request)

        #: The name of the relationship
        self.relname = relname or request.japi_uri_arguments["relname"]

        #: A resource object, on which the relationship is defined.
        self.resource = resource

        #: A pagination instance, which describes the pagination in case
        #: of a to-many relationship.
        self.pagination = pagination
        return None

    def render(self):
        """
        """
        encoder = self.api.get_encoder(self.resource)
        relationship_object = encoder.serialize_relationship(
            relname=self.relname, resource=self.resource, request=self.request,
            require_data=True, pagination=self.pagination
        )

        d = super().render()
        d.update(relationship_object)

        if self.pagination is not None:
            d.setdefault("links", dict()).update(self.pagination.json_links())
            d.setdefault("meta", dict()).update(self.pagination.json_meta())
        return d


class MetaOnly(ResponseBuilder):
    """
    Only responds with top-level :attr:`meta` data.

    :arg ~jsonapi.request.Request request:
        The current request
    :arg dict meta:
        The JSON API meta object
    """

    def __init__(self, request, *, meta=None):
        """
        """
        super().__init__(request=request)
        self.meta = meta or dict()
        return None

    def render(self):
        """
        """
        d = super().render()
        d["meta"] = self.meta
        return d
