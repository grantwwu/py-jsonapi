#!/usr/bin/env python3

from pprint import pprint
from jsonapi import schema
import timeit
import time


class Article(object):

    def __init__(self):
        self.id = "42"
        self.title = "Hallo"
        self.text = "Welt"
        self.author = None
        self.comments = []

        self.int_pair = {
            "first": 10,
            "second": 20
        }
        return None


class ArticleSchema(schema.schema.Schema):
    resource_class = Article

    title = schema.base_fields.Attribute()

    #comments = schema.base_fields.ToOneRelationship()
    #author = schema.base_fields.ToOneRelationship()


if __name__ == "__main__":
    schema = ArticleSchema()

    print("-"*10)
    pprint(schema.type)
    pprint(schema._fields_by_key)
    pprint(schema._fields_by_sp)
    pprint(schema._japi_attributes)
    pprint(schema._japi_relationships)
    pprint(schema._japi_meta)
    pprint(schema._japi_links)


from jsonapi.router import Router

r = Router()
r.add_route("article-resource", "/api/Article/{id:\d+}/{relname}/foo", 42)
print(r.url_for("article-resource", id=10, relname="author"))

print(r.get_handler("/api/Article/10/author/foo"))
