#!/usr/bin/env python3

import json
import requests
from pprint import pprint


user_uri = "http://localhost:5000/api/User"
post_uri = "http://localhost:5000/api/Post"


jsonapi_headers = {
    "content-type": "application/vnd.api+json",
    "accept-type": "application/vnd.api+json"
}


def create_user(name):
    r = requests.post(user_uri, headers=jsonapi_headers, data=json.dumps({
        "data": {
            "type": "User",
            "attributes": {
                "name": name
            }
        }
    }))
    return r.json()


def update_user(user_id, name):
    r = requests.patch(
        user_uri + "/" + user_id, headers=jsonapi_headers, data=json.dumps({
            "data": {
                "id": user_id,
                "attributes": {
                    "name": name
                }
            }
        })
    )
    return r.json()


def delete_user(user_id):
    r = requests.delete(user_uri + "/" + user_id, headers=jsonapi_headers)
    r.raise_for_status()
    return None


def update_post_author(post_id, user_id):
    r = requests.patch(
        post_uri + "/" + post_id + "/relationships/author/",
        headers=jsonapi_headers,
        data=json.dumps({
            "data": {"type": "User", "id": user_id}
        })
    )
    return r.json()


def update_post(post_id, author_id, text):
    r = requests.patch(
        post_uri + "/" + post_id,
        headers=jsonapi_headers,
        data=json.dumps({
            "data": {
                "id": post_id,
                "type": "Post",
                "attributes": {
                    "text": text
                },
                "relationships": {
                    "author": {
                        "data": {"type": "User", "id": author_id}
                    }
                }
            }
        })
    )
    return r.json()


if __name__ == "__main__":
    pprint(create_user("Benedikt Schmitt"))
    #pprint(update_user("4", "FoobarBaagahz"))

    #pprint(update_post_author("1", "7"))
    #pprint(update_post("1", "5", "jpgodjdjdjjaogjaojgoajgojoag"))
