import base64
import pathlib
import flask
import magic


def base32_to_str(base32code: str):
    return base64.b32decode(base32code.encode("utf-8")).decode("utf-8")


def str_to_base32(string: str):
    return base64.b32encode(string.encode("utf-8")).decode("utf-8")


def file_url_template(body, pathstr, **kwargs):
    path = pathlib.Path(base32_to_str(pathstr))
    if path.is_file():
        return body(path, **kwargs)
    else:
        flask.abort(404)


def static_file(path, mimetype=None):
    abspath = path.absolute()
    if mimetype is None:
        mimetype = magic.from_file(str(abspath), mime=True)
        if path.suffix == ".mpd" and mimetype == "text/xml":
            mimetype = "application/dash+xml"
    f = flask.send_from_directory(
        str(abspath.parent),
        str(abspath.name),
        etag=False,
        mimetype=mimetype,
        conditional=True,
    )
    return f
