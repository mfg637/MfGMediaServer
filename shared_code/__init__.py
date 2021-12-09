from . import enums
import base64
import flask
import hashlib
import re
import urllib
import medialib_db


anonymous_forbidden = True
access_tokens = dict()
# key - URL, value - token
enable_external_scripts = True


def base32_to_str(base32code: str):
    return base64.b32decode(base32code.encode("utf-8")).decode("utf-8")


def str_to_base32(string: str):
    return base64.b32encode(string.encode("utf-8")).decode("utf-8")


def get_medialib_sorting_constants_for_template():
    return [
        {"value": sort_order.value, "name": sort_order.name.lower().replace("_", " ")}
        for sort_order in medialib_db.files_by_tag_search.ORDERING_BY
    ]


def cache_check(path):
    hash = hashlib.sha3_256()
    with path.open('br') as f:
        buffer = f.read(1024)
        while len(buffer) > 0:
            hash.update(buffer)
            buffer = f.read(1024 * 1024)
    src_hash = hash.hexdigest()
    try:
        if flask.request.headers['If-None-Match'][1:-1] == src_hash:
            status_code = flask.Response(status=304)
            return src_hash, status_code
    except KeyError:
        pass
    return src_hash, None


def simplify_filename(name):
    return re.sub(r"[_-]", ' ', name)


def login_validation():
    access_token = flask.request.args.get("access_token", None)
    if access_token is not None:
        if access_token == access_tokens[urllib.parse.unquote(flask.request.base_url)]:
            return
    if anonymous_forbidden and not flask.session.get('logged_in'):
        flask.abort(401)


def gen_access_token():
    import random
    import string
    access_token = ""
    for i in random.choices(string.ascii_letters + string.digits, k=64):
        access_token += i
    return access_token


root_dir = None