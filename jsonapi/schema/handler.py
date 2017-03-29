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
jsonapi.schema.handler
======================

This module contains the handlers which are based on a
:class:`~jsonapi.schema.schema.Schema`.
"""


__all__ = [
    "Collection",
    "Resource",
    "ToOneRelationship",
    "ToManyRelationship",
    "ToOneRelated",
    "ToManyRelated"
]


# std
import logging
import collections

# third party
from jsonpointer import ensure_pointer

# local
from jsonapi.errors import InvalidType
from jsonapi.handler import Handler as BaseHandler
from jsonapi.response import Response
from jsonapi import response_builder


class Handler(BaseHandler):
    """
    The base for all handlers based on a :class:`~jsonapi.schema.schema.Schema`.
    """

    def __init__(self, schema, **kargs):
        super().__init__(**kargs)
        self.schema = schema
        return None


class Collection(Handler):
    """
    Implements the handler for the collection endpoint based on a schema.
    """

    def get(self):
        """
        Uses the :meth:`~jsonapi.schema.schema.Schema.query_collection`
        method of the schema to query the resources in the collection.

        :seealso: http://jsonapi.org/format/#fetching
        """
        kargs = dict()
        kargs["include"] = self.request.japi_include
        kargs["filters"] = self.request.japi_filters
        kargs["sort"] = self.request.japi_sort

        pagination_type = self.schema.opts.get("pagination")
        if pagination_type:
            kargs["pagination"] = pagination_type.from_request(self.request)

        resources = self.schema.query_collection(**kargs)

        resp = response_builder.Collection(
            request=self.request, data=resources,
            pagination=kargs.get("pagination")
        )
        return resp

    def post(self):
        """
        Uses the :meth:`~jsonapi.schema.schema.Schema.create_resource`
        method of the schema to create a new resource.

        :seealso: http://jsonapi.org/format/#crud-creating
        """
        self.request.assert_jsonapi_content()

        if not isinstance(self.request.json, collections.Mapping):
            detail = "Must be an object."
            raise InvalidType(detail=detail, source_pointer="")

        resource = self.schema.create_resource(
            data=self.request.json.get("data", {}),
            sp=ensure_pointer("/data")
        )

        resp = response_builder.NewResource(request=self.request, data=resource)
        return resp


class Resource(Handler):
    """
    Implements the handler for the resource endpoint based on a schema.
    """

    def get(self):
        """
        Uses the :meth:`~jsonapi.schema.schema.Schema.query_resource` method
        of the schema to query the requested resource.

        :seealso: http://jsonapi.org/format/#fetching-resources
        """
        resource = self.schema.query_resource(
            id_=self.request.japi_uri_arguments["id"],
            include=self.request.japi_include
        )

        resp = response_builder.Resource(request=self.request, data=resource)
        return resp

    def patch(self):
        """
        Uses the :meth:`~jsonapi.schema.schema.Schema.update_resource` method
        of the schema to update a resource.

        :seealso: http://jsonapi.org/format/#crud-updating
        """
        self.request.assert_jsonapi_content()

        if not isinstance(self.request.json, collections.Mapping):
            detail = "Must be an object."
            raise InvalidType(detail=detail, source_pointer="")

        resource = self.schema.update_resource(
            resource=self.request.japi_uri_arguments["id"],
            data=self.request.json.get("data", {}),
            sp=ensure_pointer("/data")
        )

        resp = response_builder.Resource(request=self.request, data=resource)
        return resp

    def delete(self):
        """
        Uses the :meth:`~jsonapi.schema.schema.Schema.delete_resource` method
        of the schema to delete a resource.

        :seealso: http://jsonapi.org/format/#crud-deleting
        """
        self.schema.delete_resource(
            resource=self.request.japi_uri_arguments["id"]
        )
        return Response(status=204)


class Relationship(Handler):
    """
    The base class for the relationship endpoints.
    """

    def __init__(self, relname, **kargs):
        super().__init__(**kargs)
        self.relname = relname
        return None


class ToOneRelationship(Relationship):
    """
    Implements the handler for a to-one relationship endpoint based on a
    schema.
    """

    def get(self):
        """
        Uses the :meth:`~jsonapi.schema.schema.Schema.encode_relationship`
        method of the schema to return the JSON API relationships object
        for the requested relationship.

        :seealso: http://jsonapi.org/format/#fetching-relationships
        """
        resource = self.schema.query_resource(
            id_=self.request.japi_uri_arguments["id"]
        )
        resp = response_builder.Relationship(
            request=self.request, relname=self.relname, resource=resource
        )
        return resp

    def patch(self):
        """
        Uses the :meth:`~jsonapi.schema.schema.Schema.update_relationship`
        method of the schema to update the relationship.

        :seealso: http://jsonapi.org/format/#crud-updating-relationships
        """
        resource = self.schema.update_relationship(
            relname=self.relname,
            resource=self.request.japi_uri_arguments["id"],
            data=self.request.json,
            sp=ensure_pointer("")
        )
        resp = response_builder.Relationship(
            request=self.request, relname=self.relname, resource=resource
        )
        return resp


class ToManyRelationship(Relationship):
    """
    Implements the handler for a to-many relationship endpoint based on a
    schema.
    """

    def get(self):
        """
        Uses the :meth:`~jsonapi.schema.schema.Schema.encode_relationship`
        method of the schema to return the JSON API relationships object
        for the requested relationship.

        :seealso: http://jsonapi.org/format/#fetching-relationships
        """
        field = self.schema.japi_relationships[self.relname]

        pagination_type = field.pagination
        if pagination_type:
            pagination = pagination_type.from_request(self.request)
        else:
            pagination = None

        resource = self.schema.query_resource(
            id_=self.request.japi_uri_arguments["id"]
        )
        resp = response_builder.Relationship(
            request=self.request, relname=self.relname, resource=resource,
            pagination=pagination
        )
        return resp

    def patch(self):
        """
        Uses the :meth:`~jsonapi.schema.schema.Schema.update_relationship`
        method of the schema to update the relationship.

        :seealso: http://jsonapi.org/format/#crud-updating-relationships
        """
        self.request.assert_jsonapi_content()

        field = self.schema.japi_relationships[self.relname]

        pagination_type = field.pagination
        if pagination_type:
            pagination = pagination_type.from_request(self.request)
        else:
            pagination = None

        resource = self.schema.update_relationship(
            relname=self.relname,
            resource=self.request.japi_uri_arguments["id"],
            data=self.request.json,
            sp=ensure_pointer("")
        )

        resp = response_builder.Relationship(
            request=self.request, relname=self.relname, resource=resource,
            pagination=pagination
        )
        return resp

    def post(self):
        """
        Uses the :meth:`~jsonapi.schema.schema.Schema.add_relationship`
        method of the schemato add new relationships.

        :seealso: http://jsonapi.org/format/#crud-updating-relationships
        """
        self.request.assert_jsonapi_content()

        field = self.schema.japi_relationships[self.relname]

        pagination_type = field.pagination
        if pagination_type:
            pagination = pagination_type.from_request(self.request)
        else:
            pagination = None

        resource = self.schema.add_relationship(
            relname=self.relname,
            resource=self.request.japi_uri_arguments["id"],
            data=self.request.json,
            sp=ensure_pointer("")
        )

        resp = response_builder.Relationship(
            request=self.request, relname=self.relname, resource=resource,
            pagination=pagination
        )
        return resp


class Related(Handler):
    """
    Base class for the *related* endpoints.
    """

    def __init__(self, relname, **kargs):
        super().__init__(**kargs)
        self.relname = relname
        return None


class ToOneRelated(Related):
    """
    Implements the handler for fetching the relative in a to-one relationship.
    """

    def get(self):
        """
        Uses the :meth:`~jsonapi.schema.schema.Schema.query_relative` method
        of the schema to query the related resource.

        :seealso: http://jsonapi.org/format/#fetching
        """
        resource = self.schema.query_relative(
            self.relname, include=self.request.japi_include
        )

        resp = response_builder.Resource(request=self.request, data=resource)
        return resp


class ToManyRelated(Related):
    """
    Implements the handler for fetching the relatives in a to-many relationship.
    """

    def get(self):
        """
        Uses the :meth:`~jsonapi.schema.schema.Schema.query_relatives` method
        of the schema to query the related resources.

        :seealso: http://jsonapi.org/format/#fetching
        """
        field = self.schema.japi_relationships[self.relname]

        kargs = dict()
        kargs["include"] = self.request.japi_include
        kargs["filters"] = self.request.japi_filters
        kargs["sort"] = self.request.japi_sort

        pagination_type = field.pagination
        if pagination_type:
            kargs["pagination"] = pagination_type.from_request(self.request)

        relatives = self.schema.get_relatives(
            self.request.japi_uri_arguments["id"], **kargs
        )

        resp = response_builder.Collection(
            request=self.request, data=relatives,
            pagination=kargs.get("pagination")
        )
        return resp
