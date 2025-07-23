#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import datetime
import json
import sys
import tempfile

import flask
import os
import pathlib
import filesystem
import logging
import logging.handlers

import pyimglib
import pyimglib.common
import shared_code
from shared_code.route_template import file_url_template
import medialib_db
import medialib
import image
import video

from filesystem.browse import browse


tmp_file = tempfile.NamedTemporaryFile()


app = flask.Flask(__name__)


app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True


def loginit():
    logging.getLogger().setLevel(logging.NOTSET)

    console_logger = logging.StreamHandler(sys.stdout)
    console_logger.setLevel(logging.INFO)
    console_formater = logging.Formatter(
        "%(asctime)s::%(levelname)s::%(name)s::%(message)s", datefmt="%M:%S"
    )
    console_logger.setFormatter(console_formater)
    logging.getLogger().addHandler(console_logger)

    file_rotating_handler = logging.handlers.RotatingFileHandler(
        filename="logs/server.log", maxBytes=1_000_000, backupCount=5
    )
    file_rotating_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s::%(process)dx%(thread)d::%(levelname)s::%(name)s::%(message)s"
    )
    file_rotating_handler.setFormatter(formatter)
    logging.getLogger().addHandler(file_rotating_handler)

    logging.debug("Application server.py started")


loginit()
logger = logging.getLogger(__name__)


@app.route("/")
@shared_code.login_validation
def app_root():
    return flask.render_template("home_page.html")


@app.route("/browse/")
@shared_code.login_validation
def fs_root():
    return browse(shared_code.root_dir)


app.register_blueprint(medialib.medialib_blueprint)
app.register_blueprint(image.image_blueprint)
app.register_blueprint(video.video_blueprint)


@app.route("/orig/<string:pathstr>")
@shared_code.login_validation
def get_original(pathstr):
    def body(path):
        if pyimglib.decoders.avif.is_avif(path):
            return shared_code.route_template.static_file(path, "image/avif")
        elif pyimglib.decoders.jpeg.is_JPEG(path):
            jpeg = pyimglib.decoders.jpeg.JPEGDecoder(path)
            try:
                if jpeg.arithmetic_coding():
                    return flask.redirect(
                        "{}image/transcode/jpeg/{}".format(
                            flask.request.host_url, pathstr
                        )
                    )
            except ValueError:
                return flask.redirect(
                    "{}image/transcode/jpeg/{}".format(
                        flask.request.host_url, pathstr
                    )
                )
        return shared_code.route_template.static_file(path)

    return file_url_template(body, pathstr)


def detect_content_type(path: pathlib.Path):
    if path.suffix in filesystem.browse.image_file_extensions:
        return "image"
    elif path.suffix in filesystem.browse.video_file_extensions:
        data = pyimglib.common.ffmpeg.probe(path)
        if len(pyimglib.common.ffmpeg.parser.find_audio_streams(data)):
            return "video"
        else:
            return "video-loop"
    elif path.suffix in filesystem.browse.audio_file_extensions:
        return "audio"
    elif path.suffix == ".srs":
        f = path.open("r")
        data = json.load(f)
        f.close()
        return medialib_db.srs_indexer.get_content_type(data)
    else:
        raise Exception("undetected content type", path.suffix, path)


@app.route(
    "/content_metadata/mlid<int:content_id>",
    methods=["GET", "POST"],
    defaults={"pathstr": None},
)
@app.route(
    "/content_metadata/<string:pathstr>",
    methods=["GET", "POST"],
    defaults={"content_id": None},
)
@shared_code.login_validation
def get_content_metadata(pathstr: str | None, content_id: int | None) -> str:
    """
    Retrieve and process metadata for a media content item,
    identified by either a path string or a content ID.

    This function handles both GET and POST requests:
    - On GET, it fetches metadata and related information
        for the specified content.
    - On POST, it processes form data
        to update or register new content metadata and associated tags.

    Args:
        pathstr (str | None):
            Base32-encoded string representing the file path of the content,
            or None.
        content_id (int | None):
            Unique identifier of the content in the database, or None.

    Returns:
        str: Rendered HTML template for the content metadata page.

    Raises:
        werkzeug.exceptions.HTTPException:
            If the content is not found, both identifiers are None,
            or unexpected errors occur.
    """

    def get_db_content_and_path(connection, content_id, path):
        if content_id is not None:
            db_content = medialib_db.content.get_content_metadata_by_id(
                content_id, connection
            )
            if db_content is None:
                return flask.abort(
                    404, f"Content by ID {content_id} not found"
                )
            return db_content, db_content.file_path, False
        elif path is not None:
            db_content = medialib_db.content.get_content_metadata_by_path(
                path, connection
            )
            return db_content, path, True
        else:
            return flask.abort(400, "content_id and path are both None")

    def build_template_kwargs(path, db_content):
        kwargs = {
            "content_title": (
                db_content.title if db_content and db_content.title else ""
            ),
            "content_id": db_content.content_id if db_content else "",
            "hidden": db_content.hidden if db_content else False,
            "description": (
                db_content.description
                if db_content and db_content.description
                else ""
            ),
            "prefix_id": (
                f"mlid{db_content.content_id}" if db_content else None
            ),
            "path_str": shared_code.route_template.str_to_base32(str(path)),
        }
        return kwargs

    def process_form(db_content, path):
        content_new_data = {
            "content_title": None,
            "content_id": db_content.content_id if db_content else None,
            "hidden": False,
            "description": None,
        }
        if db_content is None:
            content_new_data["file_path"] = path
            content_new_data["content_type"] = detect_content_type(path)
            content_new_data["addition_date"] = (
                datetime.datetime.fromtimestamp(path.stat().st_mtime)
            )
        for key in flask.request.form:
            value = flask.request.form[key].strip()
            if key in content_new_data and value:
                content_new_data[key] = value
        if content_new_data["hidden"] == "on":
            content_new_data["hidden"] = True
        tag_names = flask.request.form.getlist("tag_name")
        tag_categories = flask.request.form.getlist("tag_category")
        tag_aliases = flask.request.form.getlist("tag_alias")
        for i, tag_category in enumerate(tag_categories):
            if not tag_category:
                tag_categories[i] = None
        for i, tag_alias in enumerate(tag_aliases):
            if not tag_alias:
                tag_aliases[i] = tag_names[i]
        tags = list(zip(tag_names, tag_categories, tag_aliases))
        return content_new_data, tags

    # --- code body ---
    connection = medialib_db.common.make_connection()
    path = None
    if pathstr is not None:
        path = pathlib.Path(shared_code.route_template.base32_to_str(pathstr))
    db_content, path, is_file = get_db_content_and_path(
        connection, content_id, path
    )
    template_kwargs = build_template_kwargs(path, db_content)

    # (POST) form processing
    if flask.request.method == "POST" and len(flask.request.form):
        content_new_data, tags = process_form(db_content, path)
        if db_content:
            medialib_db.content.content_update(
                connection=connection, **content_new_data
            )
        else:
            content_id = medialib_db.content_register(
                **content_new_data, connection=connection
            )
        if content_id is None:
            connection.close()
            flask.abort(500, "Unexpected behaviour: content_id is still None")
        medialib_db.add_tags_for_content(content_id, tags, connection)

    # fetching additional data
    tags = {}
    representations = None
    attachments: list[medialib_db.attachment.Attachment] | None = None
    origins: list[medialib_db.origin.Origin] = []
    if content_id is not None:
        tags = medialib_db.get_tags_by_content_id(
            content_id, auto_open_connection=False
        )
        representations = medialib_db.get_representation_by_content_id(
            content_id, connection
        )
        origins = medialib_db.origin.get_origins_of_content(
            connection, content_id
        )
        albums = medialib_db.album.get_content_albums(content_id, connection)
        attachments = medialib_db.attachment.get_attachments_for_content(
            connection, content_id
        )
        if len(attachments) == 0:
            attachments = None
    connection.close()

    # render template
    if is_file:
        return flask.render_template(
            "content-metadata.html",
            item=filesystem.browse.get_file_info(path),
            file_name=path.name,
            tags=tags,
            derpibooru_dl_server=config.derpibooru_dl_server,
            albums=None,
            representations=None,
            origins=origins,
            attachments=None,
            **template_kwargs,
        )
    elif db_content is not None:
        try:
            file_item = filesystem.browse.get_db_content_info(
                db_content.content_id,
                str(db_content.file_path),
                db_content.content_type,
                db_content.title,
                icon_scale=2,
            )[0]
        except FileNotFoundError:
            file_item = None
        return flask.render_template(
            "content-metadata.html",
            item=file_item,
            file_name=path.name,
            tags=tags,
            derpibooru_dl_server=config.derpibooru_dl_server,
            albums=albums,
            representations=representations,
            origins=origins,
            attachments=attachments,
            **template_kwargs,
        )
    else:
        return flask.abort(500, "db_content is None and not file")


def file_processing(file: pathlib.Path):
    if file.suffix == ".mpd":
        return video.mpd_processing(file)
    else:
        return shared_code.route_template.static_file(file)


@app.route("/browse/<path:pathstr>")
@shared_code.login_validation
def browse_dir(pathstr):
    path = pathlib.Path(pathstr).absolute()
    logger.info(f"path = {path}")
    if pathlib.Path(path).is_dir():
        in_root_dir = False
        for parent in path.parents:
            if parent == shared_code.root_dir:
                in_root_dir = True
                break
        if in_root_dir:
            return browse(path)
        else:
            flask.abort(403)
    elif pathlib.Path(path).is_file():
        return file_processing(path)
    else:
        flask.abort(404)


@app.route("/helloword")
def hello_world():
    return "Hello, World!"


@app.route("/folder_icon_paint/<path:pathstr>")
@shared_code.login_validation
def icon_paint(pathstr):
    import static.images.folder_icon_painter as folder_icon_painter

    scale = float(flask.request.args.get("scale", 1))
    dir = pathlib.Path(pathstr).absolute()
    data = None
    with dir.joinpath(".imgview-dir-config.json").open("r") as f:
        data = json.load(f)
    rendered_template = None
    if data["cover"] is not None:
        thumbnail_path = dir.joinpath(data["cover"])
        base_size = (174, 108)
        scaled_base_size = (round(174 * scale), round(108 * scale))
        img = pyimglib.decoders.open_image(thumbnail_path, scaled_base_size)
        if isinstance(img, pyimglib.decoders.srs.ClImage):
            img = img.load_thumbnail(scaled_base_size)
        if isinstance(img, pyimglib.decoders.frames_stream.FramesStream):
            _img = img.next_frame()
            img.close()
            img = _img
        thumb_ratio = base_size[0] / base_size[1]
        src_ratio = img.size[0] / img.size[1]
        (
            width,
            height,
        ) = (
            0,
            0,
        )
        if src_ratio > thumb_ratio:
            width = base_size[0]
            height = base_size[0] / src_ratio
        else:
            width = base_size[1] * src_ratio
            height = base_size[1]
        base_offset = (10, 30)
        xoffset = (base_size[0] - width) // 2 + base_offset[0]
        yoffset = (base_size[1] - height) // 2 + base_offset[1]
        img_url = "/thumbnail/webp/{}x{}/{}".format(
            scaled_base_size[0],
            scaled_base_size[1],
            shared_code.route_template.str_to_base32(
                str(thumbnail_path.relative_to(shared_code.root_dir))
            ),
        )
        if data["color"] is not None:
            stops = folder_icon_painter.paint_icon(data["color"])
            rendered_template = flask.render_template(
                "folder icon blank.svg",
                stops=stops,
                xoffset=xoffset,
                yoffset=yoffset,
                width=width,
                height=height,
                img_url=img_url,
            )
        else:
            rendered_template = flask.render_template(
                "folder icon blank.svg",
                stops=folder_icon_painter.stops,
                xoffset=xoffset,
                yoffset=yoffset,
                width=width,
                height=height,
                img_url=img_url,
            )
    else:
        stops = folder_icon_painter.paint_icon(data["color"])
        rendered_template = flask.render_template(
            "folder icon.svg", stops=stops
        )
    return flask.Response(rendered_template, mimetype="image/svg+xml")


@app.route("/<path:pathstr>")
@shared_code.login_validation
def root_open_file(pathstr):
    path = pathlib.Path(pathstr).absolute()
    if pathlib.Path(path).is_file():
        return shared_code.route_template.static_file(path)
    else:
        flask.abort(404)


@app.errorhandler(401)
def show_login_form(event):
    f = None
    if "redirect_to" in flask.request.form:
        f = flask.render_template(
            "login.html",
            redirect_to=str(flask.request.form["redirect_to"]),
            items_per_page=config.items_per_page,
        )
    else:
        f = flask.render_template(
            "login.html",
            redirect_to=str(flask.request.url),
            items_per_page=config.items_per_page,
        )
    return flask.Response(f, status=401)


@app.route("/login", methods=["POST"])
def login_handler():
    import hashlib
    import config

    if (
        hashlib.sha3_512(
            flask.request.form["password"].encode("utf-8")
        ).hexdigest()
        == config.valid_password_hash_hex
        and flask.request.form["login"] == config.valid_login
    ):
        flask.session["logged_in"] = True
        flask.session["clevel"] = flask.request.form["clevel"]
        config.ACLMMP_COMPATIBILITY_LEVEL = int(flask.request.form["clevel"])
        flask.session["audio_channels"] = flask.request.form["ac"]
        flask.session["items_per_page"] = int(
            flask.request.form["items_per_page"]
        )
        thumbnail_size = flask.request.form["thumbnail_size"].split(
            "x", maxsplit=1
        )
        flask.session["thumbnail_width"] = int(thumbnail_size[0])
        flask.session["thumbnail_height"] = int(thumbnail_size[1])
        response = flask.make_response(
            flask.redirect(flask.request.form["redirect_to"])
        )
        response.set_cookie("clevel", str(int(flask.request.form["clevel"])))
        return response
    else:
        flask.abort(401)


if __name__ == "__main__":
    import argparse
    import config

    ssl_context = None
    if len(config.certificate_file) and len(config.private_key_file):
        cert_path = os.path.join(app.root_path, config.certificate_file)
        key_path = os.path.join(app.root_path, config.private_key_file)
        if os.path.exists(cert_path) and os.path.exists(key_path):
            ssl_context = (cert_path, key_path)
    port = config.port
    filesystem.browse.items_per_page = config.items_per_page
    parser = argparse.ArgumentParser()
    parser.add_argument("root_dir", default="")
    parser.add_argument("--port")
    parser.add_argument(
        "--anon", help="enable access by anonymous", action="store_false"
    )
    parser.add_argument(
        "--disable-external-content",
        help="Don't include external content links in template (web pages). Useful when you offline.",
        action="store_false",
    )
    args = parser.parse_args()
    os.chdir(args.root_dir)
    shared_code.root_dir = pathlib.Path(".").absolute()
    if args.port is not None:
        port = args.port
    shared_code.anonymous_forbidden = args.anon
    shared_code.enable_external_scripts = args.disable_external_content
    app.secret_key = os.urandom(12)
    app.run(host=config.host_name, port=port, ssl_context=ssl_context)
