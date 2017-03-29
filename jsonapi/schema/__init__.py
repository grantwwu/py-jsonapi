#!/usr/bin/env python3

"""
jsonapi.schema
==============

This package contains the toolkit for creating a
:class:`~jsonapi.schema.schema.Schema`, which not only allows to serialize and
deserialize a resource (like many other libraries out there), but also to
perform CRUD operations on it. Therefore a *py-jsonapi* shares some similarities
with a controller.

.. toctree::
    :maxdepth: 1

    base_fields
    decorators
    fields
    handler
    schema
"""

# local
from . import base_fields
from . import decorators
from . import fields
from . import handler
from . import schema
