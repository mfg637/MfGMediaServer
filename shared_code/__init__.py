import functools
import pathlib

from . import enums
import base64
import hashlib
import re
import urllib
import medialib_db
import flask
import PIL.Image
import logging
import io
import tempfile
import subprocess
import pyimglib

import config

logger = logging.getLogger(__name__)


anonymous_forbidden = not config.allow_anonymous
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


def login_validation(func):
    @functools.wraps(func)
    def decorated_function(*args, **kwargs):
        access_token = flask.request.args.get("access_token", None)
        if access_token is not None:
            if access_token == access_tokens[urllib.parse.unquote(flask.request.base_url)]:
                flask.abort(401)
        if anonymous_forbidden and not flask.session.get('logged_in'):
            flask.abort(401)
        return func(*args, **kwargs)

    return decorated_function



def gen_access_token():
    import random
    import string
    access_token = ""
    for i in random.choices(string.ascii_letters + string.digits, k=64):
        access_token += i
    return access_token


def get_thumbnail_size(scale=1):
    return {
        "width": int(flask.session['thumbnail_width'] * scale),
        "height": int(flask.session['thumbnail_height'] * scale)
    }


root_dir: pathlib.Path = None


MIME_TYPES_BY_FORMAT = {
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "avif": "image/avif"
}


def extract_frame_from_video(img: pyimglib.decoders.frames_stream.FramesStream):
    logger.info("video extraction")
    _img = img.next_frame()
    img.close()
    return _img


def generate_thumbnail_image(img, _format, width, height) -> tuple[io.BytesIO, str, str]:
    logger.info("generating thumbnail")
    img = img.convert(mode='RGBA')
    img.thumbnail((width, height), PIL.Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    thumbnail_file_path = None
    mime = ''
    if _format.lower() == 'webp':
        img.save(buffer, format="WEBP", quality=90, method=4, lossless=False)
        mime = "image/webp"
        _format = "webp"
    elif _format.lower() == 'avif':
        tmp_png_file = tempfile.NamedTemporaryFile(suffix=".png")
        tmp_avif_file = tempfile.NamedTemporaryFile(suffix="avif")
        img.save(tmp_png_file, format="PNG")
        commandline = [
            "avifenc",
            "-d", "10",
            "--min", "8",
            "--max", "16",
            "-j", "4",
            "-a", "end-usage=q",
            "-a", "cq-level=12",
            "-s", "8",
            tmp_png_file.name,
            tmp_avif_file.name
        ]
        subprocess.run(commandline)
        tmp_png_file.close()
        buffer.write(tmp_avif_file.read())
        tmp_avif_file.close()
        mime = "image/avif"
        _format = "avif"
    else:
        img = img.convert(mode='RGB')
        img.save(buffer, format="JPEG", quality=90)
        mime = "image/jpeg"
        _format = "jpeg"
    img.close()
    buffer.seek(0)
    return buffer, mime, _format
