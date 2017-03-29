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
jsonapi.handler
===============

.. seealso::

    :mod:`jsonapi.schema.handler` for the request handlers based on a
    schema. (You don't have to use them, but they make your life simpler.)

This module contains the base class for all *py-jsonapi* resource handlers.
The implementation is straight forward::

    class Article(Handler):

        def get(self, request):
            pagination = jsonapi.pagination.NumberSize.from_request(
                request, query(Article).count()
            )
            articles = query(Article)\\
                .limit(pagination.limit)\\
                .offset(pagination.offset)\\
                .all()
            return jsonapi.response_builder.Collection(request, data=articles)

The handler receives a :class:`~jsonapi.request.Request` instance as
parameter and returns either a :class:`~jsonapi.response.Response`
or a :class:`~jsonapi.response_builder.ResponseBuilder` object.

If a :class:`~jsonapi.response_builder.ResponseBuilder` is returned,
the :meth:`~jsonapi.response_builder.IncludeMixin.fetch_include` method
is called automatic.
"""

# std
import logging

# local
from . import errors


__all__ = [
    "Handler"
]


LOG = logging.getLogger(__file__)


class Handler(object):
    """
    The interface for a request handler.

    :arg ~jsonapi.api.API api:
        The API, which owns this handler.
    """

    def __init__(self, api=None):
        self.api = api
        return None

    @property
    def request(self):
        """
        The current request. This is a proxy for ``self.api.current_request``.
        """
        return self.api.current_request

    @property
    def g(self):
        """
        This is a proxy for ``self.api.current_request.settings.``
        """
        return self.api.current_request.settings

    def init_api(self, api):
        """
        Binds the handler to the *api*. This method can be called at most once.

        :arg ~jsonapi.api.API:
        """
        assert self.api is None or self.api is api
        self.api = api
        return None

    def handle(self, request):
        """
        Calls the correct handler method (*get*, *patch*, ...) depending on HTTP
        :attr:`~jsonapi.request.Request.method`.

        :arg ~jsonapi.request.Request request:

        :returns:
            A :class:`~jsonapi.response.Response` or
            :class:`~jsonapi.response_builder.ResponseBuilder`
        """
        if request.method == "delete":
            return self.delete()
        elif request.method == "get":
            return self.get()
        elif request.method == "head":
            return self.head()
        elif request.method == "post":
            return self.post()
        elif request.method == "patch":
            return self.patch()
        elif request.method == "options":
            return self.options()
        raise errors.MethodNotAllowed()

    def delete(self):
        raise errors.MethodNotAllowed()

    def get(self):
        raise errors.MethodNotAllowed()

    def head(self):
        raise errors.MethodNotAllowed()

    def post(self):
        raise errors.MethodNotAllowed()

    def patch(self):
        raise errors.MethodNotAllowed()

    def options(self):
        raise errors.MethodNotAllowed()
