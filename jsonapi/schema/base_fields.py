#!/usr/bin/env python3

"""
jsonapi.schema.base_fields
==========================

This module contains the definition for all basic fields. A field describes
how data should be encoded to JSON and decoded again and allows to define
special methods for the different CRUD operations defined by the
http://jsonapi.org specification.

You should only work with the following fields directly:

*   :class:`Link`

    For JSON API link objects (usually included in a JSON API links object).

    :seealso: http://jsonapi.org/format/#document-links

*   :class:`Attribute`

    Represent information about a resource object (but not a relationship or a
    link).

    :seealso: http://jsonapi.org/format/#document-resource-object-attributes

*   :class:`ToOneRelationship`, :class:`ToManyRelationship`

    Represent relationships on a resource object.

    :seealso: http://jsonapi.org/format/#document-resource-object-relationships

.. todo::

    Add support for nested fields (aka embedded documents).

.. todo::

    Fields are currently not bound to schema instances. It may be helpful
    to do something like this in the future::

        class BaseField(object):

            #....

            def __get__(self, obj, cls=None):
                if obj is None:
                    return self

                class BoundField(object):
                    def get(*args, **kargs): return self.get(obj, *args, **kargs)
                    def set(*args, **kargs): return self.set(obj, *args, **kargs)
                    def add(*args, **kargs): return self.add(obj, *args, **kargs)
                    #...
                    __call__ = get
                return BoundField
"""

__all__ = [
    "BaseField",
    "LinksObjectMixin",
    "Link",
    "Attribute",
    "Relationship",
    "ToOneRelationship",
    "ToManyRelationship"
]

# std
import collections
import logging

# local
from jsonapi.errors import InvalidType, InvalidValue


LOG = logging.getLogger(__file__)


class BaseField(object):
    """
    This class describes the base for all fields defined on a schema and
    knows how to encode, decode and update the field. A field is usually
    directly mapped to a property (*mapped_key*) on the resource object, but
    this mapping can be customized by implementing custom *getters* and
    *setters*.

    .. hint::

        The inheritance of fields is currently implemented using the
        :func:`~copy.deepcopy` function from the standard library. This means,
        that in some rare cases, it is necessairy that you implement a
        custom :meth:`__deepcopy__` method when you subclass :class:`BaseField`.

    :arg str name:
        The name of the field in the JSON API document. If not explicitly
        given, it's the same as :attr:`key`.
    :arg str mapped_key:
        The name of the associated property on the resource class. If not
        explicitly given, it's the same as :attr:`key`.
    :arg str writable:
        Can be either *never*, *always*, *creation* or *update* and
        describes in which CRUD context the field is writable.
    :arg str required:
        Can be either *never*, *always*, *creation* or *update* and
        describes in which CRUD context the field is required as input.
    :arg callable fget:
        A method on a :class:`~jsonapi.schema.schema.Schema` which returns the
        current value of the resource's attribute:
        ``fget(self, resource, **kargs)``.
    :arg fset:
        A method on a :class:`~jsonapi.schema.schema.Schema` which updates the
        current value of the resource's attribute:
        ``fget(self, resource, data, sp, **kargs)``.
    """

    def __init__(
            self, *,
            name="",
            mapped_key="",
            writable="always",
            required="never",
            fget=None,
            fset=None
        ):
        """ """
        #: The name of this field on the :class:`~jsonapi.schema.schema.Schema`
        #: it has been defined on.Please note, that not each field has a *key*
        #: (like some links or meta attributes).
        self.key = None

        #: A :class:`jsonpointer.JSONPointer` to this field in a JSON API
        #: resource object. The source pointer is set from the Schema class
        #: during initialisation.
        self.sp = None

        self.name = name
        self.mapped_key = mapped_key

        assert writable in ("always", "never", "creation", "update")
        if writable == "always":
            writable = ("never", "creation")

        self.writable = writable

        assert required in ("always", "never", "creation", "update")
        self.required = required

        self.fget = fget
        self.fset = fset
        self.fvalidators = list()
        return None

    def __call__(self, f):
        """The same as :meth:`getter`."""
        return self.getter(f)

    def getter(self, f):
        """
        Descriptor to change the getter.

        :seealso: :func:`jsonapi.schema.decorators.gets`
        """
        self.fget = f
        self.name = self.name or f.__name__
        return self

    def setter(self, f):
        """
        Descriptor to change the setter.

        :seealso: :func:`jsonapi.schema.decorators.sets`
        """
        self.fset = f
        return self

    def validator(self, f, when="post-decode", context="always"):
        """
        Descriptor to add a validator.

        :seealso: :func:`jsonapi.schema.decorators.validates`

        :arg str when:
            Must be either *pre-decode* or *post-decode*.
        :arg str context:
            The CRUD context in which the validator is invoked. Must
            be *never*, *always*, *creation* or *update*.
        """
        assert when in ("pre-decode", "post-decode")
        assert context in ("never", "always", "creation", "update")
        self.fvalidators.append({
            "validator": f, "when": when, "context": context
        })
        return self

    def default_get(self, schema, resource, **kargs):
        """Used if no *getter* has been defined. Can be overridden."""
        if self.mapped_key:
            return getattr(resource, self.mapped_key)
        return None

    def default_set(self, schema, resource, data, sp, **kargs):
        """Used if no *setter* has been defined. Can be overridden."""
        if self.mapped_key:
            setattr(resource, self.mapped_key, data)
        return None

    def get(self, schema, resource, **kargs):
        """
        Returns the value of the field on the resource.

        :arg ~jsonapi.schema.schema.Schema schema:
            The schema this field has been defined on.
        """
        # NOTE: Don't change this method without checking if the *asyncio*
        #       library still works.
        f = self.fget or self.default_get
        return f(schema, resource, **kargs)

    def set(self, schema, resource, data, sp, **kargs):
        """
        Changes the value of the field on the resource.

        :arg ~jsonapi.schema.schema.Schema schema:
            The schema this field has been defined on.
        :arg data:
            The (decoded and validated) new value of the field
        :arg ~jsonpointer.JSONPointer sp:
            A JSON pointer to the source of the original input data.
        """
        # NOTE: Don't change this method without checking if the *asyncio*
        #       library still works.
        assert self.writable != "never"
        f = self.fset or self.default_set
        return f(schema, resource, data, sp, **kargs)

    def encode(self, schema, data, **kargs):
        """Encodes the *data* returned from :meth:`get` so that it can be
        serialized with :func:`json.dumps`. Can be overridden.
        """
        return data

    def decode(self, schema, data, sp, **kargs):
        """Decodes the raw *data* from the JSON API input document and returns
        it. Can be overridden.
        """
        return data

    def validate_pre_decode(self, schema, data, sp, context):
        """Validates the raw JSON API input for this field. This method is
        called before :meth:`decode`.

        :arg ~jsonapi.schema.schema.Schema schema:
            The schema this field has been defined on.
        :arg data:
            The raw input data
        :arg ~jsonpointer.JSONPointer sp:
            A JSON pointer to the source of *data*.
        """
        for validator in self.fvalidators:
            if validator["when"] != "pre-decode":
                continue
            if validator["context"] not in ("always", context):
                continue

            f = validator["validator"]
            f(schema, data, sp)
        return None

    def validate_post_decode(self, schema, data, sp, context):
        """Validates the decoded input *data* for this field. This method is
        called after :meth:`decode`.

        :arg ~jsonapi.schema.schema.Schema schema:
            The schema this field has been defined on.
        :arg data:
            The decoded input data
        :arg ~jsonpointer.JSONPointer sp:
            A JSON pointer to the source of *data*.
        """
        for validator in self.fvalidators:
            if validator["when"] != "post-decode":
                continue
            if validator["context"] not in ("always", context):
                continue

            f = validator["validator"]
            f(schema, data, sp)
        return None


class LinksObjectMixin(object):
    """
    Mixin for JSON API documents that contain a JSON API links object, like
    relationships::

        class Article(Schema):

            author = ToOneRelationship()
            author.add_link(Link(
                name="related", href="/Article/{r.id}/author"
            ))

            # or

            author_self = Link(
                name="self", href="/Article/{r.id}/relationships/author",
                link_of="author"
            )

    The :meth:`BaseField.encode` receives an additional keyword argument *link*
    with the encoded links.

    :arg list links:
        A list of (transient) :class:`links <Link>`.
    """

    def __init__(self, links=None):
        self.links = {link.name: link for link in links}
        return None

    def add_link(self, link):
        """
        Adds a new link to the links object.
        """
        self.links[link.name] = link
        return self


class Link(BaseField):
    """
    .. seealso::

        http://jsonapi.org/format/#document-links

    .. code-block:: python3

        class Article(Schema):

            self = Link(href="/api/{s.type}/{r.id}")

            author = ToOneRelationship()
            author_related = Link(
                href="/api/{s.type}/{r.id}/author", link_of="author"
            )

    In the http://jsonapi.org specification, a link is always part of a
    JSON API links object and is either a simple string or an object with
    the members *href* and *meta*.

    A link is only readable and *not* mapped to a property on the resource
    object (You can however define a *getter*).

    :arg str href:
        A formatter string for the link. You can access *s* for the schema,
        *r* for the resource object and *a* for the current api in the string:
        ``href = "http://images.example.org/{s.typename}/{r.id}"``.
        If you need more control, you can define a *getter* as usual.
    :arg str link_of:
        If given, the link is part of the links object of the field with the
        key *link_of* and appears otherwise in the resource object's links
        objects. E.g.: ``link_of = "author"``.
    :arg bool normalize:
        If true, the *encode* method normalizes the link so that it is always
        an object.
    """

    def __init__(
            self, href="",
            *, link_of="<resource>", name="", fget=None, normalize=True
        ):
        """ """
        super().__init__(self, name=name, writable="never", fget=fget)

        self.normalize = bool(normalize)
        self.href = href
        self.link_of = link_of
        return None

    def default_get(self, schema, resource):
        """Returns the formatted :attr:`href`."""
        href = self.href.format(s=schema, r=resource, a=schema.api)
        return href

    def encode(self, schema, data):
        """Normalizes the links object if wished."""
        if not self.normalize:
            return data
        elif isinstance(data, str):
            return {"href": data}
        else:
            assert isinstance(data, collections.Mapping)
            return data


class Attribute(BaseField):
    r"""
    .. seealso::

        http://jsonapi.org/format/#document-resource-object-attributes

    An attribute is always part of the resource's JSON API attributes object,
    unless *meta* is set, in which case the attribute appears in the resource's
    meta object.

    Per default, an attribute is mapped to a property on the resource object.
    You can customize this behaviour by implementing your own *getter* and
    *setter*:

    .. code-block:: python3

        class Article(Schema):

            title = Attribute()

    Does the same as:

    .. code-block:: python3

        class Article(Schema):

            title = Attribute()

            @title.getter
            def title(self, article):
                return article.title

            @title.setter
            def title(self, article, new_title):
                article.title = new_title
                return None

    :arg bool meta:
        If true, the attribute is part of the resource's *meta* object.
    :arg bool primary_key:
        If true, the attribute returns the primary key (id) of the resource.
        Exactly one attribute must be used as primary key.
    :arg \*\* kargs:
        The init arguments for the :class:`BaseField`.
    """

    def __init__(self, *, meta=False, **kargs):
        super().__init__(**kargs)
        self.meta = bool(meta)
        return None


class Relationship(BaseField, LinksObjectMixin):
    """
    .. seealso::

        http://jsonapi.org/format/#document-resource-object-relationships

    Additionaly to attributes and basic fields, we must know how to *include*
    the related resources in the case of relationships. This class defines
    the common interface of *to-one* and *to-many* relationships (links object,
    meta object, *self* link, *related* link, validation, ...).

    Relationships are always part of the resource's JSON API relationships
    object.

    :seealso: :class:`ToOneRelationship`, :class:`ToManyRelationship`

    :arg str require_data:
        If true, the JSON API relationship object must contain the *data*
        member. Must be either *never*, *always*, *creation* or *update*.
    :arg bool dereference:
        If true, the relationship linkage is dereferenced automatic when
        decoded. (Implicitly sets *require_data* to *always*)
    :arg set foreign_types:
        A set with all foreign types. If given, this list is used to validate
        the input data. Leave it empty to allow all types.
    :arg callable finclude:
        A method on a :class:`~jsonapi.schema.schema.Schema` which returns the
        related resources: ``finclude(self, resource, **kargs)``.
    :arg callable fquery:
        A method on a :class:`~jsonapi.schema.schema.Schema` which returns the
        queries the related resources: ``fquery(self, resource, **kargs)``.
    """

    #: True, if this is to-one relationship::
    #:
    #:      field.to_one == isinstance(field, ToOneRelationship)
    to_one = None

    #: True, if this is a to-many relationship::
    #:
    #:      field.to_many == isinstance(field, ToManyRelationship)
    to_many = None

    def __init__(
            self, *,
            dereference=True,
            require_data="always",
            foreign_types=None,
            finclude=None,
            fquery=None,
            links=None,
            **kargs):
        """ """
        BaseField.__init__(self, **kargs)
        LinksObjectMixin.__init__(self, links=links)

        # NOTE: The related resources are loaded by the schema class for
        #       performance reasons (one big query vs many small ones).
        self.dereference = bool(dereference)

        self.foreign_types = frozenset(foreign_types or [])
        self.finclude = finclude
        self.fquery = fquery

        assert require_data in ("never", "always", "oncreation", "onupdate")
        self.require_data = require_data

        # Add the default links.
        self.add_link(Link(
            "self", fget=lambda schema, res: schema.api.relationship_uri(res)
        ))
        self.add_link(Link(
            "related", fget=lambda schema, res: schema.api.related_uri(res)
        ))
        return None

    def includer(self, f):
        """
        Descriptor to change the includer.

        :seealso: :func:`~jsonapi.schema.decorators.includes`
        """
        self.finclude = f
        return f

    def default_include(self, schema, resource, **kargs):
        """Used if no *includer* has been defined. Can be overridden."""
        if self.mapped_key:
            return getattr(resource, self.mapped_key)
        raise RuntimeError("No includer and mapped_key have been defined.")

    def include(self, schema, resource, **kargs):
        """
        Returns the related resources.

        :arg ~jsonapi.schema.schema.Schema schema:
            The schema this field has been defined on.
        """
        # NOTE: Don't change this method without checking if the *asyncio*
        #       library still works.
        f = self.finclude or self.default_include
        return f(schema, resource, **kargs)

    def query_(self, f):
        """
        Descriptor to change the query function.

        :seealso: :func:`~jsonapi.schema.decorators.queries`
        """
        self.fquery = f
        return self

    def default_query(self, schema, resource, **kargs):
        """Used of no *query* function has been defined. Can be overridden."""
        if self.mapped_key:
            return getattr(resource, self.mapped_key)
        raise RuntimeError("No query method and mapped_key have been defined.")

    def query(self, schema, resource, **kargs):
        """
        Queries the related resources.
        """
        f = self.fquery or self.default_query
        return f(schema, resource, **kargs)

    def validate_resource_identifier(self, schema, data, sp):
        """
        :seealso: http://jsonapi.org/format/#document-resource-identifier-objects

        Asserts that *data* is a JSON API resource identifier with the correct
        *type* value.
        """
        if not isinstance(data, collections.Mapping):
            detail = "Must be an object."
            raise InvalidType(detail=detail, source_pointer=sp)

        if not ("type" in data and "id" in data):
            detail = "Must contain a 'type' and an 'id' member."
            raise InvalidValue(detail=detail, source_pointer=sp)

        if self.foreign_types and not data["type"] in self.foreign_types:
            detail = "Unexpected type: '{}'.".format(data["type"])
            raise InvalidValue(detail=detail, source_pointer=sp/"type")
        return None

    def validate_relationship_object(self, schema, data, sp):
        """
        Asserts that *data* is a JSON API relationship object.

        *   *data* is a dictionary
        *   *data* must be not empty
        *   *data* may only have the members *data*, *links* or *meta*.
        *   *data* must contain a *data* member, if :attr:`dereference` or
            :attr:`require_data` is true.
        """
        if not isinstance(data, collections.Mapping):
            detail = "Must be an object."
            raise InvalidType(detail=detail, source_pointer=sp)

        if not data:
            detail = "Must contain at least a 'data', 'links' or 'meta' member."
            raise InvalidValue(detail=detail, source_pointer=sp)

        if not (data.keys() <= {"links", "data", "meta"}):
            unexpected = (data.keys() - {"links", "data", "meta"}).pop()
            detail = "Unexpected member: '{}'.".format(unexpected)
            raise InvalidValue(detail=detail, source_pointer=sp)

        if (self.dereference or self.require_data) and not "data" in data:
            detail = "The 'data' member is required."
            raise InvalidValue(detail=detail, source_pointer=sp)
        return None

    def validate_pre_decode(self, schema, data, sp, context):
        self.validate_relationship_object(schema, data, sp)
        super().validate_pre_decode(schema, data, sp, context)
        return None


class ToOneRelationship(Relationship):
    """
    .. seealso::

        *   http://jsonapi.org/format/#document-resource-object-relationships
        *   http://jsonapi.org/format/#document-resource-object-linkage

    Describes how to serialize, deserialize and update a *to-one* relationship.
    """

    to_one = True
    to_many = False

    def validate_relationship_object(self, schema, data, sp):
        """Checks additionaly to :meth:`Relationship.validate_relationship_object`
        that the *data* member is a valid resource linkage.
        """
        super().validate_relationship_object(schema, data, sp)
        if "data" in data and data["data"] is not None:
            self.validate_resource_identifier(schema, data, sp/"data")
        return None

    def encode(self, schema, data, *, links=None):
        """Composes the final relationships object."""
        # None
        if data is None:
            data = {"data": data}
        # JSON API resource linkage or JSON API relationships object
        elif isinstance(data, collections.Mapping):
            if "type" in data and "id" in data:
                data = {"data": data}
        # the related resource instance
        else:
            data = {"data": schema.api.ensure_identifier_object(data)}

        if links:
            links.update(data.get("links", {}))
            data["links"] = links
        return data


class ToManyRelationship(Relationship):
    """
    .. seealso::

        *   http://jsonapi.org/format/#document-resource-object-relationships
        *   http://jsonapi.org/format/#document-resource-object-linkage

    Describes how to serialize, deserialize and update a *to-many* relationship.
    Additionaly to *to-one* relationships, *to-many* relationships must also
    support adding and removing relatives.

    :arg callable fadd:
        A method on a :class:`~jsonapi.schema.schema.Schema` which adds
        new resources to the relationship:
        ``fadd(self, resource, data, sp, **kargs)``.
    :arg callable fremove:
        A method on a :class:`~jsonapi.schema.schema.Schema` which removes
        some resources from the relationship:
        ``fremove(self, resource, data, sp, **kargs)``.
    :arg :class:`~jsonapi.pagination.BasePagination` pagination:
        The pagination helper *class* used to paginate the *to-many*
        relationship.
    """

    to_one = False
    to_many = True

    def __init__(self, *, fadd=None, fremove=None, pagination=None, **kargs):
        """ """
        super().__init__(**kargs)
        self.fadd = fadd
        self.fremove = fremove
        self.pagination = pagination
        return None

    def adder(self, f):
        """
        Descriptor to change the adder.

        :seealso: :func:`~jsonapi.schema.decorators.adds`
        """
        self.fadd = f
        return self

    def remover(self, f):
        """
        Descriptor to change the remover.

        :seealso: :func:`~jsonapi.schema.decorators.removes`
        """
        self.fremove = f
        return self

    def default_add(self, schema, resource, data, sp):
        """Used if no *adder* has been defined. **Should** be overridden."""
        LOG.warning("You should overridde the adder.")

        if not self.mapped_key:
            raise RuntimeError("No adder and mapped_key have been defined.")

        relatives = getattr(resource, self.mapped_key)
        relatives.extend(data)
        return None

    def default_remove(self, schema, resource, data, sp):
        """Used if not *remover* has been defined. **Should** be overridden."""
        LOG.warning("You should overridde the remover.")

        if not self.mapped_key:
            raise RuntimeError("No remover and mapped_key have been defined.")

        relatives = getattr(resource, self.mapped_key)
        for relative in data:
            try:
                relatives.remove(relative)
            except ValueError:
                pass
        return None

    def add(self, schema, resource, data, sp, **kargs):
        """Adds new resources to the relationship."""
        # NOTE: Don't change this method without checking if the *asyncio*
        #       library still works.
        f = self.fadd or self.default_add
        return f(schema, resource, data, sp, **kargs)

    def remove(self, schema, resource, data, sp, **kargs):
        """Removes resources from the relationship."""
        # NOTE: Don't change this method without checking if the *asyncio*
        #       library still works.
        f = self.fremove or self.default_remove
        return f(schema, resource, data, sp, **kargs)

    def encode(self, schema, data, *, links=None, pagination=None):
        """Composes the final JSON API relationships object.

        :arg ~jsonapi.pagination.BasePagination pagination:
            If not *None*, the links and meta members of the pagination
            helper are added to the final JSON API relationship object.
        """
        if isinstance(data, collections.Sequence):
            data = [schema.api.ensure_identifier_object(item) for item in data]
            data = {"data": data}

        if links:
            links.update(data.get("links", {}))
            data["links"] = links

        if pagination:
            data.setdefault("links", {}).update(pagination.json_links)
            data.setdefault("meta", {}).update(pagination.json_meta)
        return data

    def validate_relationship_object(self, schema, data, sp):
        """Checks additionaly to :meth:`Relationship.validate_relationship_object`
        that the *data* member is a list of resource identifier objects.
        """
        if "data" in data:
            if not isinstance(data["data"], collections.Sequence):
                detail = "The 'data' must be an array of resource identifier "\
                    "objects."
                raise InvalidType(detail=detail, sp=sp/"data")

            for i, item in enumerate(data):
                self.validate_resource_identifier(schema, item, sp/"data"/i)
        return None
