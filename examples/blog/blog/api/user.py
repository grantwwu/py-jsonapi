#!/usr/bin/env python3

from flask import g
import jsonapi
from ..models import User, Post


__all__ = [
    "init_api"
]


class UserEncoder(jsonapi.encoder.Encoder):
    resource_class = User

    name = jsonapi.encoder.Attribute()
    posts = jsonapi.encoder.ToManyRelationship()


class UserIncluder(jsonapi.includer.Includer):
    resource_class = User
    posts = jsonapi.includer.ToManyRelationship()


class BaseUserValidator(jsonapi.validator.Validator):
    id = jsonapi.validator.ID(regex="\d+")
    type = jsonapi.validator.Type(types=["User"])


class NewUserValidator(BaseUserValidator):

    @jsonapi.validator.Attribute(type=str, required=True)
    def name(self, d, source_pointer="/"):
        return not d.isspace()


class UpdateUserValidator(BaseUserValidator):

    @jsonapi.validator.Attribute(type=str)
    def name(self, d, source_pointer="/"):
        return not d.isspace()


class UserCollection(jsonapi.handler.Handler):

    def get(self, request):
        pagination = jsonapi.pagination.NumberSize.from_request(
            request, g.sql_session.query(User).count()
        )
        users = g.sql_session.query(User)\
            .limit(pagination.limit)\
            .offset(pagination.offset)\
            .all()

        return jsonapi.response_builder.Collection(
            request, data=users, pagination=pagination
        )

    def post(self, request):
        NewUserValidator().assert_one_resource_object(request.json)

        user = User(name=request.json["data"]["attributes"]["name"])
        g.sql_session.add(user)
        g.sql_session.commit()
        return jsonapi.response_builder.NewResource(request, data=user)


class UserResource(jsonapi.handler.Handler):

    def get(self, request):
        user = g.sql_session.query(User).get(request.japi_uri_arguments["id"])
        if user is None:
            raise jsonapi.errors.NotFound()
        return jsonapi.response_builder.Resource(request, data=user)

    def patch(self, request):
        user = g.sql_session.query(User).get(request.japi_uri_arguments["id"])
        if user is None:
            raise jsonapi.errors.NotFound()

        UpdateUserValidator().assert_resource_object(request.json)

        if "name" in request.json["attributes"]:
            user.name = request.json["attributes"]["name"]

        g.sql_session.add(user)
        g.sql_session.commit()
        return jsonapi.response_builder.Resource(request, data=user)

    def delete(self, request):
        user = g.sql_session.query(User).get(request.japi_uri_arguments["id"])
        if user is None:
            raise jsonapi.errors.NotFound()

        g.sql_session.delete(user)
        g.commit()
        return jsonapi.response.Response(status=204)


class UserRelationshipPosts(jsonapi.handler.Handler):

    def get(self, request):
        user = g.sql_session.query(User).get(request.japi_uri_arguments["id"])
        if user is None:
            raise jsonapi.errors.NotFound()
        return jsonapi.response_builder.Relationship(request, data=user)


class UserRelatedPosts(jsonapi.handler.Handler):

    def get(self, request):
        user = g.sql_session.query(User).get(request.japi_uri_arguments["id"])
        if user is None:
            raise jsonapi.errors.NotFound()

        pagination = jsonapi.pagination.NumberSize.from_request(
            request,
            g.sql_session.query(Post).filter(Post.author == user).count()
        )
        posts = g.sql_session.query(Post)\
            .filter(Post.author == user)\
            .limit(pagination.limit)\
            .offset(pagination.offset)
        return jsonapi.response_builder.Collection(request, data=posts)


def init_api(api):
    encoder = UserEncoder()
    includer = UserIncluder()

    api.add_type(encoder, includer)
    api.add_handler(
        handler=UserCollection(), typename=encoder.typename,
        endpoint_type="collection"
    )
    api.add_handler(
        handler=UserResource(), typename=encoder.typename,
        endpoint_type="resource"
    )
    api.add_handler(
        handler=UserRelationshipPosts(), typename=encoder.typename,
        endpoint_type="relationship", relname="posts"
    )
    api.add_handler(
        handler=UserRelatedPosts(), typename=encoder.typename,
        endpoint_type="related", relname="posts"
    )
    return None
