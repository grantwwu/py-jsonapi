#!/usr/bin/env python3

"""
jsonapi.schema.schema
=====================

This module contains the base schema which implements the encoding, decoding,
validation and update operations based on
:class:`fields <jsonapi.schema.base_fields.BaseField>`.
"""

__all__ = [
    "SchemaMeta",
    "Schema"
]

# std
import copy
import collections
import contextlib
import logging

# third party
from cached_property import cached_property
from jsonpointer import ensure_pointer

# local
from jsonapi.schema.base_fields import (
    BaseField, LinksObjectMixin, Link, Attribute, Relationship
)
from jsonapi.errors import (
    ValidationError, InvalidValue, InvalidType, Conflict
)


logger = logging.getLogger(__file__)


class SchemaMeta(type):

    @classmethod
    def _assign_sp(cls, fields, sp):
        """Sets the :attr:`BaseField.sp` (source pointer) property recursively
        for all child fields.
        """
        for field in fields:
            field.sp = sp/field.name
            if isinstance(field, LinksObjectMixin):
                cls._assign_source_pointer(field.links, field.sp/"links")
        return None

    @classmethod
    def _sp_to_field(cls, fields):
        """Returns an ordered dictionary, which maps the source pointer of a
        field to the field. Nested fields are listed before the parent.
        """
        d = collections.OrderedDict()
        for field in fields:
            if isinstance(field, LinksObjectMixin):
                d.update(cls._collect_fields(field.links))
            d[field.sp] = field
        return d

    def __new__(cls, name, bases, attrs):
        """
        Detects all fields and wires everything up. These class attributes are
        defined here:

        *   *type*

            The JSON API typename

        *   *_fields_by_sp*

            Maps the source pointer of a field to the associated
            :class:`BaseField`.

        *   *_fields_by_key*

            Maps the key (schema property name) to the associated
            :class:`BaseField`.

        *   *_japi_attributes*

            Maps the JSON API attribute name to the :class:`Attribute`
            instance.

        *   *_japi_relationships*

            Maps the JSON API relationship name to the :class:`Relationship`
            instance.

        *   *_japi_links*

            Maps the JSON API link name to the :class:`Link` instance.

        *   *_japi_meta*

            Maps the (top level) JSON API meta member to the associated
            :class:`Attribute` instance.

        *   *_japi_toplevel*

            A list with all JSON API top level fields (japi_attributes, ...,
            japi_meta).

        :arg str name:
            The name of the schema class
        :arg tuple bases:
            The direct bases of the schema class
        :arg dict attrs:
            A dictionary with all properties defined on the schema class
            (attributes, methods, ...)
        """
        fields_by_key = dict()
        attrs["_fields_by_key"] = fields_by_key

        # Create a copy of the inherited fields.
        for base in reversed(bases):
            if issubclass(base, Schema):
                fields_by_key.update(base._fields_by_key)
        fields_by_key = copy.deepcopy(fields_by_key)

        for key, prop in attrs.items():
            if isinstance(prop, BaseField):
                prop.key = key
                prop.name = prop.name or key
                prop.mapped_key = prop.mapped_key or key
                fields_by_key[prop.key] = prop

        # Apply the decorators.
        # TODO: Use a more generic approach.
        for key, prop in attrs.items():
            if hasattr(prop, "japi_getter"):
                field = fields_by_key[prop.japi_getter["field"]]
                field.getter(prop)
            elif hasattr(prop, "japi_setter"):
                field = fields_by_key[prop.japi_setter["field"]]
                field.setter(prop)
            elif hasattr(prop, "japi_validates"):
                field = fields_by_key[prop.japi_validates["field"]]
                field.validator(
                    prop, when=prop.japi_validator["when"],
                    context=prop.japi_validator["context"]
                )
            elif hasattr(prop, "japi_adder"):
                field = fields_by_key[prop.japi_adder["field"]]
                field.adder(prop)
            elif hasattr(prop, "japi_remover"):
                field = fields_by_key[prop.japi_remover["field"]]
                field.remover(prop)
            elif hasattr(prop, "japi_includer"):
                field = fields_by_key[prop.japi_includer["field"]]
                field.includer(prop)
            elif hasattr(prop, "japi_query"):
                field = fields_by_key[prop.japi_query["field"]]
                field.query_(prop)

        # Find nested fields (link_of, ...) and link them with
        # their parent.
        for key, field in fields_by_key.items():
            if getattr(field, "link_of", None):
                parent = fields_by_key[field.link_of]
                parent.add_link(field)

        # Find the *top-level* attributes, relationships, links and meta fields.
        japi_attributes = {
            key: field\
            for key, field in fields_by_key.items()\
            if isinstance(field, Attribute) and not field.meta
        }
        cls._assign_sp(japi_attributes.values(), ensure_pointer("/attributes"))
        attrs["_japi_attributes"] = japi_attributes

        japi_relationships = {
            key: field\
            for key, field in fields_by_key.items()\
            if isinstance(field, Relationship)
        }
        cls._assign_sp(
            japi_relationships.values(), ensure_pointer("/relationships")
        )
        attrs["_japi_relationships"] = japi_relationships

        japi_links = {
            key: field\
            for key, field in fields_by_key.items()\
            if isinstance(field, Link) and not field.link_of
        }
        cls._assign_sp(japi_links.values(), ensure_pointer("/links"))
        attrs["_japi_links"] = japi_links

        japi_meta = {
            key: field\
            for key, field in fields_by_key.items()\
            if isinstance(field, Attribute) and field.meta
        }
        cls._assign_sp(japi_links.values(), ensure_pointer("/meta"))
        attrs["_japi_meta"] = japi_meta

        # Collect all top level fields in a list.
        japi_toplevel = list()
        japi_toplevel.extend(japi_attributes.values())
        japi_toplevel.extend(japi_relationships.values())
        japi_toplevel.extend(japi_links.values())
        japi_toplevel.extend(japi_meta.values())
        attrs["_japi_toplevel"] = japi_toplevel

        # Create the source pointer map.
        fields_by_sp = cls._sp_to_field(japi_toplevel)
        attrs["_fields_by_sp"] = fields_by_sp

        # Determine 'type' name.
        if (not attrs.get("type")) and attrs.get("resource_class"):
            attrs["type"] = attrs["resource_class"].__name__
        if (not attrs.get("type")):
            attrs["type"] = name
        return super().__new__(cls, name, bases, attrs)

    def __init__(cls, name, bases, attrs):
        """
        Initialise a new schema class.
        """
        super().__init__(name, bases, attrs)
        return None

    def __call__(cls, *args):
        """
        Creates a new instance of a Schema class.
        """
        return super().__call__(*args)


class Schema(metaclass=SchemaMeta):
    """
    A schema defines how we can encode a resource and patch it. It also allows
    to patch a resource. All in all, it defines a **controller** for a *type*
    in the JSON API.

    If you want, you can implement your own request handlers and only use
    the schema for validation and serialization.
    """

    # TODO: The options dictionary.
    opts = dict()
    opts["pagination"] = None

    #: The resource class associated with this schema.
    resource_class = None

    #: The JSON API *type*. (Leave it empty to derive it automatic from the
    #: resource class name or the schema name).
    type = ""

    def __init__(self, api=None):
        """ """
        self.api = api

        # crud_context = "create", "read", "update", "delete"

        #: *l* is bound to the current request.
        self._l = object()
        self._l.context = {
            "encoding": None,
            "crud": None,
            "included_relationships": None
        }
        return None

    # Context
    # -------

    def init_api(self, api):
        """
        Binds the schema to the API instance. This method is called automatic
        from the :class:`~jsonapi.api.API` instance.
        """
        assert self.api is None or self.api is api
        self.api = api
        return None

    @property
    def context(self):
        """
        Returns the current context::

            >>> article_schema.context
            {
                "fieldset": ["title", "text", "author"],
                "encoding": "included",
                "crud": "update",
                "included_relationships": ["author", "comments"]
            }

        Use the :meth:`use_context` contextmanager to change the context.
        """
        return self._l.context

    @contextlib.contextmanager
    def use_context(self, **kargs):
        """
        Updates the current encoding context:

        .. code-block:: python3

            with article_schema.use_context(fieldset=["title", "author"]):
                data = article_schema.encode_resource(article)

            with article_schema.context(encoding="included"):
                pass
        """
        old_context = self._l.context.copy()
        self._l.context.update(kargs)
        yield
        self._l.context = old_context
        return None

    # ID
    # --

    def id(self, resource):
        """
        :rtype: str
        :returns: The id of the resource.
        """
        data = self._japi_id.get(self, resource)
        return self._japi_id.encode(self, data)

    # Encoding
    # --------

    def _encode_field(self, field, resource, kargs=None):
        """
        Encodes the *field* and if has nested fields (e.g. inherits from
        :class:`LinksObjectMixin`), the nested fields are encoded first and
        passed to the encode method of the *field*.
        """
        kargs = kargs if kargs is not None else dict()
        if isinstance(field, LinksObjectMixin):
            kargs["links"] = {
                link.name: link.encode(resource) for link in field.links
            }

        data = field.get(resource)
        return field.encode(self, data, **kargs)

    def encode_resource(
            self, resource, *, is_data=False, is_included=False, included=None,
            fieldset=None
        ):
        """
        .. seealso::

            http://jsonapi.org/format/#document-resource-objects

        :arg resource:
            A resource object
        :arg fieldset:
            *None* or a list with all fields that must be included. All other
            fields must not appear in the final document.
        :arg str context:
            Is either *data* or *included* and defines in which part of the
            JSON API document the resource object is placed.
        :arg list included:
            A list with all included relationships.
        :rtype: dict
        :returns:
            The JSON API resource object
        """
        fieldset = self.api.current_request.japi_fields.get(self.type)

        d = dict()
        d["type"] = self.type
        d["id"] = self.id(resource)

        # JSON API attributes object
        attributes = {
            field.name: self._encode_field(field, resource)\
            for field in self._japi_attributes.values()\
            if fieldset is None or field.name in fieldset
        }
        if attributes:
            d["attributes"] = attributes

        # JSON API relationships object
        relationships = {
            field.name: self._encode_field(field, resource)\
            for field in self._japi_relationships.values()\
            if fieldset is None or field.name in fieldset
        }
        if relationships:
            d["relationships"] = relationships

        # JSON API meta object
        meta = {
            field.name: self._encode_field(field, resource)\
            for field in self._japi_meta.values()
        }
        if meta:
            d["meta"] = meta

        # JSON API links object
        links = {
            field.name: self._encode_field(field, resource)\
            for field in self._japi_links.values()
        }
        if not "self" in links:
            d["self"] = self.api.resource_uri(resource)
        d["links"] = links
        return d

    def encode_relationship(self, relname, resource, *, pagination=None):
        """
        .. seealso::

            http://jsonapi.org/format/#document-resource-object-relationships

        Creates the JSON API relationship object of the relationship *relname*.

        :arg str relname:
            The name of the relationship
        :arg resource:
            A resource object
        :arg ~jsonapi.pagination.BasePagination pagination:
            Describes the pagination in case of a *to-many* relationship.

        :rtype: dict
        :returns:
            The JSON API relationship object for the relationship *relname*
            of the *resource*
        """
        field = self._relationships[relname]

        kargs = dict()
        if field.to_one and pagination:
            kargs["pagination"] = pagination
        return self._encode_field(field, resource, kargs)

    # Validation (pre decode)
    # -----------------------

    def _validate_field_pre_decode(self, field, data, sp, context=None):
        """
        Validates the input data for a field, **before** it is decoded. If the
        field has nested fields, the nested fields are validated first.

        :arg BaseField field:
        :arg data:
            The input data for the field.
        :arg JSONPointer sp:
            The pointer to *data* in the original document. If *None*, there
            was no input data for this field.
        :arg str context:
            The current crud context.
        """
        context = context or self.context.get("crud")

        writable = field.writable in ("always", context)
        if (not writable) and (sp is not None):
            detail = "The field '{}' is readonly."
            raise ValidationError(detail=detail, source_pointer=sp)

        required = field.required in ("always", context)
        if required and data is (sp is not None):
            detail = "The field '{}' is required."
            raise InvalidValue(detail=detail, source_pointer=sp)

        if sp is not None:
            field.validate_pre_decode(self, data, sp, context)
        return None

    def validate_resource_pre_decode(
        self, data, sp, context=None, *, expected_id=""
        ):
        """
        Validates a JSON API resource object received from an API client::

            schema.validate_resource_pre_decode(
                data=request.json["data"], sp="/data"
            )

        :arg data:
            The received JSON API resource object
        :arg ~jsonpointer.JSONPointer sp:
            The JSON pointer to the source of *data*.
        :arg str context:
            The current crud context.
        """
        context = context or self.context.get("crud")

        if not isinstance(data, collections.Mapping):
            detail = "Must be an object."
            raise InvalidType(detail=detail, source_pointer=sp)

        # JSON API id
        if (expected_id or context == "update") and not "id" in data:
            detail = "The 'id' member is missing."
            raise InvalidValue(detail=detail, source_pointer=sp/"id")
        if expected_id and data["id"] != expected_id:
            detail = "The id '{}' does not match the endpoint ('{}')."\
                .format(data["id"], expected_id)
            raise Conflict(detail=detail, source_pointer=sp/"id")
        self._validate_field_pre_decode(self._japi_id, data["id"], sp/"id")

        # JSON API attributes object
        attrs = data.get("attributes", {})
        attrs_sp = sp/"attributes"

        if not isinstance(attrs, dict):
            detail = "Must be an object."
            raise InvalidType(detail=detail, source_pointer=attrs_sp)

        for field in self._japi_attributes.values():
            field_sp = attrs_sp/field.name if field.name in attrs else None
            field_data = attrs.get(field.name)
            self._validate_field_pre_decode(field, field_data, field_sp)

        # JSON API relationships object
        rels = data.get("relationships", {})
        rels_sp = sp/"relationships"

        if not isinstance(rels, dict):
            detail = "Must be an object."
            raise InvalidType(detail=detail, source_pointer=rels_sp)

        for field in self._japi_relationships.values():
            field_sp = rels_sp/field.name if field.name in rels else None
            field_data = rels.get(field.name)
            self._validate_field_pre_decode(field, field_data, field_sp)

        # JSON API meta object
        meta = data.get("meta", {})
        meta_sp = sp/"meta"

        if not isinstance(meta, dict):
            detail = "Must be an object."
            raise InvalidType(detail=detail, source_pointer=meta_sp)

        for field in self._japi_meta.values():
            field_sp = meta_sp/field.name if field.name in meta else None
            field_data = meta.get(field.name)
            self._validate_field_pre_decode(field, field_data, field_sp)
        return None

    # Decoding
    # --------

    def _decode_field(self, field, data, sp, *, memo=None, kargs=None):
        """
        Decodes the input data for the *field*. If the *field* has nested
        fields, the nested fields are decoded first and passed to the
        decode method of the field.

        :arg ~jsonapi.schema.BaseField field:
            The field whichs input data is decoded.
        :arg data:
            The input data for the field
        :arg ~jsonpointer.JSONPointer:
            The JSON pointer to the source of *data*
        :arg dict memo:
            The decoded data will be stored additionaly in this dictionary
            with the key *field.key*.
        :arg dict kargs:
            A dictionary with additional keyword arguments passed to
            :meth:`BaseField.decode`.
        """
        kargs = kargs or {}

        d = field.decode(self, data, sp, **kargs)
        if memo is not None and field.key:
            memo[field.key] = (d, sp)
        return d

    def decode_resource(self, data, sp):
        """
        Decodes the JSON API resource object *data* and returns a dictionary
        which maps the key of a field to its decoded input data.

        :rtype: ~collections.OrderedDict
        :returns:
            An ordered dictionary which maps a fields key to a two tuple
            ``(data, sp)`` which contains the input data and the source pointer
            to it.
        """
        memo = OrderedDict()

        # JSON API attributes object
        attrs = data.get("attributes", {})
        attrs_sp = sp/"attributes"
        for field in self._japi_attributes.values():
            field_sp = attrs_sp/field.name if field.name in attrs else None
            field_data = attrs.get(field.name)
            self._decode_field(field, field_data, field_sp, memo)

        #  JSON API relationships object
        rels = data.get("relationships", {})
        rels_sp = sp/"relationships"
        for field in self._japi_relationships.values():
            field_sp = rels_sp/field.name if field.name in rels else None
            field_data = rels.get(field.name)
            self._decode_field(field, field_data, field_sp, memo)

        # JSON API meta object
        meta = data.get("meta", dict())
        meta_sp = sp/"meta"
        for field in self._japi_meta.values():
            field_sp = meta_sp/field.name if field.name in meta else None
            field_data = meta.get(field.name)
            self._decode_field(field, field_data, field_sp, memo)
        return memo

    # Validate (post decode)
    # ----------------------

    def validate_resource_post_decode(self, memo, context=None):
        """
        Validates the decoded *data* of JSON API resource object.

        :arg ~collections.OrderedDict memo:
            The *memo* object returned from :meth:`decode_resource`.
        :arg str context:
            The current crud context.
        """
        # NOTE: The fields in *memo* are ordered, such that children are
        #       listed before their parent.
        context = context or self.context.get("crud")
        for key, (data, sp) in memo.items():
            field = self._field_by_key[key]
            field.validate_post_decode(self, data, sp, context)
        return None

    # CRUD (resource)
    # ---------------

    def create_resource(self, data, sp):
        """
        .. seealso::

            http://jsonapi.org/format/#crud-creating

        Creates a new resource instance and returns it. **You should overridde
        this method.**

        The default implementation passes the attributes, (dereferenced)
        relationships and meta data from the JSON API resource object
        *data* to the constructor of the resource class. If the primary
        key is *writable* on creation and a member of *data*, it is also
        passed to the constructor.

        :arg dict data:
            The JSON API resource object with the initial data.
        :arg ~jsonpointer.JSONPointer sp:
            The JSON pointer to the source of *data*.
        """
        self.validate_resource_pre_decode(data, sp, context="create")
        memo = self.decode_resource(data, sp)
        self.validate_resource_post_decode(memo, context="create")

        # Map the property names on the resource instance to its initial data.
        init = {
             self._fields_by_key[key].mapped_key: data\
             for key, (data, sp) in memo.items()
        }
        if "id" in data:
            init["id"] = data["id"]

        # Create a new object by calling the constructor.
        resource = self.resource_class(**init)
        return resource

    def update_resource(self, resource, data, sp):
        """
        .. seealso::

            http://jsonapi.org/format/#crud-updating

        Updates an existing *resource*. **You should overridde this method** in
        order to save the changes in the database.

        The default implementation uses the
        :class:`~jsonapi.schema.base_fields.BaseField` descriptors to update the
        resource.

        :arg resource:
            The id of the resource or the resource instance
        :arg dict data:
            The JSON API resource object with the update information
        :arg ~jsonpointer.JSONPointer sp:
            The JSON pointer to the source of *data*.
        """
        if isinstance(resource, self.resource_class):
            resource_id = self.id(resource)
        else:
            resource_id = resource

        self.validate_resource_pre_decode(
            data, sp, context="update", expected_id=resource_id
        )
        memo = self.decode_resource(data, sp)
        self.validate_resource_post_decode(memo, context="update")

        if not isinstance(resource, self.resource_class):
            resource = self.query_resource(resource)

        for key, (data, sp) in memo.items():
            field = self._fields_by_key[key]
            field.set(self, resource, data, sp)
        return None

    def delete_resource(self, resource):
        """
        .. seealso::

            http://jsonapi.org/format/#crud-deleting

        Deletes the *resource*. **You must overridde this method.**

        :arg resource:
            The id of the resource or the resource instance
        """
        raise NotImplementedError()

    # CRUD (relationships)
    # --------------------

    def update_relationship(self, relname, resource, data, sp):
        """
        .. seealso::

            http://jsonapi.org/format/#crud-updating-relationships

        Updates the relationship with the JSON API name *relname*.

        :arg str relname:
            The name of the relationship.
        :arg resource:
            The id of the resource or the resource instance.
        :arg str data:
            The JSON API relationship object with the update information.
        :arg ~jsonpointer.JSONPointer sp:
            The JSON pointer to the source of *data*.
        """
        field = self._japi_relationships[relname]

        self._validate_field_pre_decode(field, data, sp, context="update")
        decoded = self._decode_field(field, data, sp)
        self._validate_field_post_decode(field, data, sp, context="update")

        if not isinstance(resource, self.resource_class):
            resource = self.query_resource(resource)

        field.set(self, resource, decoded, sp)
        return None

    def add_relationship(self, relname, resource, data, sp):
        """
        .. seealso::

            http://jsonapi.org/format/#crud-updating-to-many-relationships

        Adds the members specified in the JSON API relationship object *data*
        to the relationship, unless the relationships already exist.

        :arg str relname:
            The name of the relationship.
        :arg resource:
            The id of the resource or the resource instance.
        :arg str data:
            The JSON API relationship object with the update information.
        :arg ~jsonpointer.JSONPointer sp:
            The JSON pointer to the source of *data*.
        """
        field = self._japi_relationships[relname]
        assert field.to_many

        self._validate_field_pre_decode(field, data, sp, context="update")
        decoded = self._decode_field(field, data, sp)
        self._validate_field_post_decode(field, data, sp, context="update")

        if not isinstance(resource, self.resource_class):
            resource = self.query_resource(resource)

        field.add(self, resource, decoded, sp)
        return None

    def remove_relationship(self, relname, resource, data, sp):
        """
        .. seealso::

            http://jsonapi.org/format/#crud-updating-to-many-relationships

        Deletes the members specified in the JSON API relationship object *data*
        from the relationship.

        :arg str relname:
            The name of the relationship.
        :arg resource:
            The id of the resource or the resource instance.
        :arg str data:
            The JSON API relationship object with the update information.
        :arg ~jsonpointer.JSONPointer sp:
            The JSON pointer to the source of *data*.
        """
        field = self._japi_relationships[relname]
        assert field.to_many

        self._validate_field_pre_decode(field, data, sp, context="update")
        decoded = self._decode_field(field, data, sp)
        self._validate_field_post_decode(field, data, sp, context="update")

        if not isinstance(resource, self.resource_class):
            resource = self.query_resource(resource)

        field.remove(self, resource, decoded, sp)
        return None

    # Querying
    # --------

    def query_collection(
        self, include=None, pagination=None, filters=None, sort=None
        ):
        """
        .. seealso::

            http://jsonapi.org/format/#fetching

        Fetches a subset of the collection represented by this schema.
        **Must be overridden.**

        :arg list include:
            The list of relationships which will be included into the
            response. See also: :attr:`jsonapi.request.Request.japi_include`.
        :arg ~jsonapi.pagination.BasePagination pagination:
            Describes the requested pagination of the collection. You
            will probably need to set some attribute of the pagination helper,
            like the *total_number* or *next_cursor*.
        :arg dict filters:
            A dictionary with filters for the query. See also:
            :attr:`jsonapi.request.Request.japi_filters`
        :arg list sort:
            A list with order criterions. See also:
            :attr:`jsonapi.request.Request.japi_sort`
        """
        raise NotImplementedError()

    def query_resource(self, id_, include=None):
        """
        .. seealso::

            http://jsonapi.org/format/#fetching

        Fetches the resource with the id *id_*. **Must be overridden.**

        :arg str id_:
            The id of the requested resource.
        :arg list include:
            The list of relationships which will be included into the
            response. See also: :attr:`jsonapi.request.Request.japi_include`.
        :raises ~jsonapi.errors.ResourceNotFound:
            If there is no resource with the given *id_*.
        """
        raise NotImplementedError()

    def query_relative(self, relname, resource_id, *, include=None):
        """
        Controller for the *related* endpoint of the to-one relationship with
        then name *relname*.

        Returns the related resource or ``None``.

        :arg str relname:
            The name of a to-one relationship.
        :arg str resource_id:
            The id of the resource or the resource instance.
        :arg list include:
            The list of relationships which will be included into the
            response. See also: :attr:`jsonapi.request.Request.japi_include`
        """
        field = self._japi_relationships[relname]
        assert field.to_one

        relative = field.query(self, resource, include=include)
        return relative

    def query_relatives(
            self, relname, resource, *,
            include=None, pagination=None, filters=None, sort=None
        ):
        """
        Controller for the *related* endpoint of the to-many relationship with
        then name *relname*.

        Because a to-many relationship represents a collection, this method
        accepts the same parameters as :meth:`query_collection`.

        Returns the related resource or ``None``.

        :arg str relname:
            The name of a to-one relationship.
        :arg str resource_id:
            The id of the resource or the resource instance.
        """
        field = self._japi_relationships[relname]
        assert field.to_many

        relatives = field.query(
            self, resource,
            filters=filters, include=include, sort=sort, pagination=pagination
        )
        return relatives

    def fetch_include(self, resource, relname, *, rest_path=None):
        """
        .. seealso::

            http://jsonapi.org/format/#fetching-includes

        Fetches the related resources. The default method uses the
        :meth:`~jsonapi.schema.base_fields.Relationship.include` method of
        the *Relationship* fields. **Can be overridden.**

        :arg resource:
            A resource object.
        :arg str relname:
            The name of the relationship.
        :arg list rest_path:
            The name of the relationships of the returned relatives, which
            will also be included.
        :rtype: list
        :returns:
            A list with the related resources. The list is empty or has
            exactly one element in the case of *to-one* relationships.
            If *to-many* relationships are paginated, the relatives from the
            first page should be returned.
        """
        field = self._japi_relationships[relname]
        return field.include(self, resource, rest_path=rest_path)
