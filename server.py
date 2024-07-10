#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import datetime
import json
import subprocess
import sys
import tempfile
import abc
import urllib.parse
import xml.dom.minidom

import flask
import os
import pathlib
import io
import PIL.Image
import filesystem
import magic
import logging
import logging.handlers

import pyimglib
import pyimglib.decoders.ffmpeg
import shared_code
import pyimglib.ACLMMP as ACLMMP
import medialib_db
import medialib

from filesystem.browse import browse


tmp_file = tempfile.NamedTemporaryFile()


app = flask.Flask(__name__)


app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True


FILE_SUFFIX_LIST = [
    ".png", ".jpg", ".gif", ".webm", ".mp4", ".svg"
]


def loginit():
    logging.getLogger().setLevel(logging.NOTSET)

    console_logger = logging.StreamHandler(sys.stdout)
    console_logger.setLevel(logging.INFO)
    console_formater = logging.Formatter(
        '%(asctime)s::%(levelname)s::%(name)s::%(message)s',
        datefmt="%M:%S"
    )
    console_logger.setFormatter(console_formater)
    logging.getLogger().addHandler(console_logger)

    file_rotating_handler = logging.handlers.RotatingFileHandler(
        filename='logs/server.log', maxBytes=1_000_000, backupCount=5
    )
    file_rotating_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s::%(process)dx%(thread)d::%(levelname)s::%(name)s::%(message)s')
    file_rotating_handler.setFormatter(formatter)
    logging.getLogger().addHandler(file_rotating_handler)

    logging.debug("Application server.py started")


loginit()
logger = logging.getLogger(__name__)


@app.route('/')
@shared_code.login_validation
def app_root():
    return flask.render_template("home_page.html")


@app.route('/browse/')
@shared_code.login_validation
def fs_root():
    return browse(shared_code.root_dir)


app.register_blueprint(medialib.medialib_blueprint)


def static_file(path, mimetype=None):
    abspath = path.absolute()
    if mimetype is None:
        mimetype = magic.from_file(str(abspath), mime=True)
        if path.suffix == '.mpd' and mimetype == "text/xml":
            mimetype = "application/dash+xml"
    f = flask.send_from_directory(
        str(abspath.parent),
        str(abspath.name),
        etag=False,
        mimetype=mimetype,
        conditional=True
    )
    return f


def file_url_template(body, pathstr, **kwargs):
    path = pathlib.Path(shared_code.base32_to_str(pathstr))
    if path.is_file():
        return body(path, **kwargs)
    else:
        flask.abort(404)


@app.route('/orig/<string:pathstr>')
@shared_code.login_validation
def get_original(pathstr):
    def body(path):
        if pyimglib.decoders.avif.is_avif(path):
            return static_file(path, "image/avif")
        elif pyimglib.decoders.jpeg.is_JPEG(path):
            jpeg = pyimglib.decoders.jpeg.JPEGDecoder(path)
            try:
                if jpeg.arithmetic_coding():
                    return flask.redirect(
                        "{}image/jpeg/{}".format(
                            flask.request.host_url,
                            pathstr
                        )
                    )
            except ValueError:
                return flask.redirect(
                    "{}image/jpeg/{}".format(
                        flask.request.host_url,
                        pathstr
                    )
                )
        return static_file(path)
    return file_url_template(body, pathstr)


def get_download_filename(content_title, origin_id, path, _format) -> str:
    if content_title is not None:
        for suffix in FILE_SUFFIX_LIST:
            if suffix in content_title:
                content_title = content_title.replace(suffix, "")
        content_title = content_title.replace(
            "-amp-", "&"
        ).replace(
            "-eq-", "="
        )
    filename = None
    if origin_id is not None and content_title is not None:
        filename = "{} {}.{}".format(
            origin_id, content_title, _format.lower
        )
    elif content_title is None and origin_id is not None:
        filename = "{}.{}".format(origin_id, _format.lower())
    elif content_title is not None:
        filename = "{}.{}".format(content_title, _format.lower())
    else:
        filename = "{}.{}".format(path.stem, _format.lower())
    return filename


def jxl_jpeg_decode(file_path, download, content_title, origin_id, path):
    logger.info("decoding JPEG XL to JPEG")
    jpeg_buffer = io.BytesIO(shared_code.jpeg_xl_fast_decode(file_path))
    f = flask.send_file(jpeg_buffer, mimetype="image/jpeg")
    response = flask.make_response(f)
    if download:
        filename = get_download_filename(content_title, origin_id, path, "jpeg")
        response.headers['content-disposition'] = \
            'attachment; filename="{}"'.format(
                urllib.parse.quote(filename)
            )
    return response


@app.route('/image/<string:_format>/<string:pathstr>')
@shared_code.login_validation
def transcode_image(_format: str, pathstr):
    def body(path: pathlib.Path, _format):
        logger.debug("TRANSCODE path = {}, format = {}".format(path.__repr__(), _format))
        origin_id = flask.request.args.get("origin_id", None, str)
        content_title = flask.request.args.get("title", None, str)
        download: bool = flask.request.args.get("download", False, bool)
        src_hash, status_code = shared_code.cache_check(path)
        if status_code is not None:
            return status_code
        if path.suffix == ".jxl" and _format == 'jpeg':
            return jxl_jpeg_decode(path, download, content_title, origin_id, path)
        img = pyimglib.decoders.open_image(path)
        possible_formats = (_format,)
        LEVEL = int(flask.session['clevel'])
        if _format.lower() == "autodetect":
            _format = "webp"
            if LEVEL <= 1:
                possible_formats = ("avif", "webp")
            if LEVEL == 4:
                possible_formats = ("jpeg", "png", "gif")
                _format = "jpeg"
        if isinstance(img, pyimglib.decoders.srs.ClImage):
            lods = img.get_image_file_list()
            logger.debug("lods: {}".format(lods.__repr__()))
            current_lod = lods.pop(0)
            current_lod_format = pyimglib.decoders.get_image_format(current_lod)
            logger.debug("current_lod {}: {}".format(current_lod.__repr__(), current_lod_format))
            if _format == "png":
                img = pyimglib.decoders.open_image(current_lod)
            else:
                while len(lods):
                    if current_lod_format not in possible_formats:
                        current_lod = lods.pop()
                        current_lod_format = pyimglib.decoders.get_image_format(current_lod)
                        logger.debug("current_lod {}: {}".format(current_lod.__repr__(), current_lod_format))
                    else:
                        break
                if current_lod_format in possible_formats and not download:
                    base32path = shared_code.str_to_base32(str(current_lod))
                    return flask.redirect(
                        "{}orig/{}".format(
                            flask.request.host_url,
                            base32path
                        )
                    )
                elif current_lod_format == _format and download:
                    absolute_path = shared_code.root_dir.joinpath(current_lod)
                    f = flask.send_file(absolute_path, mimetype=shared_code.MIME_TYPES_BY_FORMAT[_format])
                    filename = get_download_filename(content_title, origin_id, path)
                    response = flask.make_response(f)
                    response.headers['content-disposition'] = 'attachment; filename="{}"'.format(
                        urllib.parse.quote(filename)
                    )
                    return response
                else:
                    if current_lod_format == "jpeg xl" and _format == "jpeg":
                        return jxl_jpeg_decode(current_lod, download, content_title, origin_id, path)
                    else:
                        img = pyimglib.decoders.open_image(current_lod)
        if isinstance(img, pyimglib.decoders.frames_stream.FramesStream):
            _img = img.next_frame()
            img.close()
            img = _img
        img = img.convert(mode='RGBA')
        buffer = io.BytesIO()
        mime = ''
        if _format.lower() == 'webp':
            img.save(buffer, format="WEBP", quality=90, method=4, lossless=False)
            mime = "image/webp"
        elif _format.lower() == 'jpeg':
            if pyimglib.decoders.jpeg.is_JPEG(path):
                jpeg_data = path.read_bytes()
                transcoding_result = subprocess.run(
                    ["jpegtran", "-copy", "all"],
                    input=jpeg_data,
                    capture_output=True
                )
                buffer = io.BytesIO(transcoding_result.stdout)
            else:
                img = img.convert(mode='RGB')
                img.save(buffer, format="JPEG", quality=90)
            mime = "image/jpeg"
        else:
            img.save(buffer, format="PNG")
            mime = "image/png"
        buffer.seek(0)
        f = flask.send_file(
            buffer,
            mimetype=mime,
            max_age=24 * 60 * 60,
            last_modified=path.stat().st_mtime,
        )
        #response = flask.Response(buffer, mimetype=mime, )
        f.set_etag(src_hash)
        response = flask.make_response(f)
        if download:
            filename = get_download_filename(content_title, origin_id, path, _format)
            response.headers['content-disposition'] = 'attachment; filename="{}"'.format(
                urllib.parse.quote(filename)
            )
        return response
    return file_url_template(body, pathstr, _format=_format)


@app.route('/thumbnail/<string:_format>/<int:width>x<int:height>/<string:pathstr>')
@shared_code.login_validation
def gen_thumbnail(_format: str, width: int, height: int, pathstr: str | None):

    def srs_image_processing(img, allow_origin) -> PIL.Image.Image | pathlib.Path:
        logger.info("srs image processing")
        lods: list[pathlib.Path] = img.progressive_lods()
        compatibility_level = int(flask.request.cookies.get("clevel"))
        best_quality = compatibility_level <= 1
        if allow_origin and best_quality:
            return lods[-1]
        cl2_compatible = compatibility_level <= 2
        if allow_origin and cl2_compatible:
            cl2_content = img.get_content_by_level(2)
            if cl2_content is not None:
                return cl2_content
        current_lod = lods.pop(0)
        current_lod_img = pyimglib.decoders.open_image(current_lod)
        while len(lods):
            if isinstance(current_lod_img, pyimglib.decoders.frames_stream.FramesStream):
                current_lod_img = current_lod_img.next_frame()
            if current_lod_img.width < width and current_lod_img.height < height:
                current_lod = lods.pop()
                logger.debug("CURRENT_LOD: {}".format(current_lod))
                current_lod_img.close()
                current_lod_img = pyimglib.decoders.open_image(current_lod)
            else:
                break
        if current_lod_img.format == "WEBP" and allow_origin:
            return current_lod
        else:
            return current_lod_img

    def check_origin_allowed(img, allow_origin):
        return allow_origin and img.format == "WEBP" and\
               (img.is_animated or (img.width <= width and img.height <= height))

    def complex_formats_processing(img, file_path, allow_origin) -> PIL.Image.Image | flask.Response:
        logger.info("complex_formats_processing")
        if isinstance(img, pyimglib.decoders.srs.ClImage):
            selected_image = srs_image_processing(img, allow_origin)
            logger.debug("srs_image_processing: {}".format(selected_image.__repr__()))
            if isinstance(selected_image, pathlib.Path):
                base32path = shared_code.str_to_base32(str(selected_image))
                return flask.redirect(
                    "{}orig/{}".format(
                        flask.request.host_url,
                        base32path
                    )
                )
            else:
                img = selected_image
        if isinstance(img, pyimglib.decoders.frames_stream.FramesStream):
            img = shared_code.extract_frame_from_video(img)
            logger.debug("extracted frame: {}".format(img.__repr__()))
        if check_origin_allowed(img, allow_origin):
            logger.info("origin redirect allowed")
            base32path = shared_code.str_to_base32(str(file_path))
            return flask.redirect(
                "{}orig/{}".format(
                    flask.request.host_url,
                    base32path
                )
            )
        return img

    def file_path_processing(path, _format, width, height):
        logger.info("file_path_processing")
        allow_origin = bool(flask.request.args.get('allow_origin', False))
        src_hash, status_code = None, None
        if path.stat().st_size < (1024 * 1024 * 1024):
            src_hash, status_code = shared_code.cache_check(path)
        if status_code is not None:
            return status_code
        img = pyimglib.decoders.open_image(shared_code.root_dir.joinpath(path))
        extracted_img = complex_formats_processing(img, path, allow_origin)
        if isinstance(extracted_img, flask.Response):
            return extracted_img
        elif isinstance(extracted_img, PIL.Image.Image):
            img = extracted_img
        else:
            raise NotImplementedError(type(extracted_img))
        buffer, mime, _format = shared_code.generate_thumbnail_image(img, _format, width, height)
        f = flask.send_file(
            buffer,
            mimetype=mime,
            max_age=24 * 60 * 60,
            last_modified=path.stat().st_mtime,
        )
        if src_hash is not None:
            f.set_etag(src_hash)
        return f

    return file_url_template(file_path_processing, pathstr, _format=_format, width=width, height=height)


ORIGIN_PREFIX = {
    "derpibooru": "db",
    "ponybooru": "pb",
    "twibooru": "tb",
    "e621": "ef",
    "furbooru": "fb",
    "furaffinity": "fa"
}


@app.route('/content_metadata/mlid<int:content_id>', methods=['GET', 'POST'], defaults={'pathstr': None})
@app.route('/content_metadata/<string:pathstr>', methods=['GET', 'POST'], defaults={'content_id': None})
@shared_code.login_validation
def get_content_metadata(pathstr, content_id):
    def body(path: pathlib.Path | None, content_id=None):
        def detect_content_type(path: pathlib.Path):
            if path.suffix in filesystem.browse.image_file_extensions:
                return "image"
            elif path.suffix in filesystem.browse.video_file_extensions:
                data = pyimglib.decoders.ffmpeg.probe(path)
                if len(pyimglib.decoders.ffmpeg.parser.find_audio_streams(data)):
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

        ORIGIN_URL_TEMPLATE = {
            "derpibooru": "https://derpibooru.org/images/{}",
            "ponybooru": "https://ponybooru.org/images/{}",
            "twibooru": "https://twibooru.org/{}",
            "e621": "https://e621.net/posts/{}",
            "furbooru": "https://furbooru.org/images/{}",
            "furaffinity": "https://www.furaffinity.net/view/{}/"
        }
        connection = medialib_db.common.make_connection()
        db_query_results = None
        db_albums_registered = None
        is_file = True
        if content_id is not None:
            is_file = False
            db_query_results = medialib_db.get_content_metadata_by_content_id(
                content_id, connection
            )
            path = pathlib.Path(db_query_results[1])
            db_albums_registered = medialib_db.get_content_albums(content_id, connection)
            if db_albums_registered is not None and len(db_albums_registered) == 0:
                db_albums_registered = None
        else:
            db_query_results = medialib_db.get_content_metadata_by_file_path(
                path, connection
            )
        template_kwargs = {
            'content_title': "",
            'content_id': "",
            'origin_name': "",
            'origin_id': "",
            'origin_link': None,
            'hidden': False,
            'description': '',
            'prefix_id': None,
            'path_str': shared_code.str_to_base32(str(path))
        }
        if db_query_results is not None:
            template_kwargs['content_id'] = db_query_results[0]
            content_id = db_query_results[0]
            if db_query_results[2] is not None:
                template_kwargs['content_title'] = db_query_results[2]
            if db_query_results[-3] is not None:
                template_kwargs['origin_name'] = db_query_results[-3]
                if db_query_results[-2] is not None and template_kwargs['origin_name'] in ORIGIN_URL_TEMPLATE:
                    template_kwargs['origin_link'] = \
                        ORIGIN_URL_TEMPLATE[template_kwargs['origin_name']].format(db_query_results[-2])
                    template_kwargs['prefix_id'] = "{}{}".format(
                        ORIGIN_PREFIX[template_kwargs['origin_name']], db_query_results[-2]
                    )
            else:
                template_kwargs['prefix_id'] = "mlid{}".format(
                    db_query_results[0]
                )
            if db_query_results[-2] is not None:
                template_kwargs['origin_id'] = db_query_results[-2]
            if db_query_results[4] is not None:
                template_kwargs['description'] = db_query_results[4]
            template_kwargs['hidden'] = bool(db_query_results[-1])
        if len(flask.request.form):
            content_new_data = {
                'content_title': None,
                'content_id': None,
                'origin_name': None,
                'origin_id': None,
                'hidden': False,
                'description': None,
            }
            if db_query_results is not None:
                content_new_data['content_id'] = db_query_results[0]
            else:
                content_new_data['file_path'] = path
                content_new_data['content_type'] = detect_content_type(path)
                content_new_data['addition_date'] = \
                    datetime.datetime.fromtimestamp(path.stat().st_mtime)
            for key in flask.request.form:
                if key in content_new_data and len(flask.request.form[key].strip()):
                    content_new_data[key] = flask.request.form[key].strip()
                if key in template_kwargs:
                    template_kwargs[key] = flask.request.form[key].strip()
            if content_new_data['hidden'] == 'on':
                content_new_data['hidden'] = True
            logger.debug("content_new_data: {}".format(content_new_data))
            tag_names = flask.request.form.getlist('tag_name')
            tag_categories = flask.request.form.getlist('tag_category')
            tag_aliases = flask.request.form.getlist('tag_alias')
            for i, tag_category in enumerate(tag_categories):
                if len(tag_category) == 0:
                    tag_categories[i] = None
            for i, tag_alias in enumerate(tag_aliases):
                if len(tag_alias) == 0:
                    tag_aliases[i] = tag_names[i]
            tags = list(zip(tag_names, tag_categories, tag_aliases))
            logger.debug("tags: {}".format(tags))
            if db_query_results is not None:
                medialib_db.content_update(connection=connection, **content_new_data)
            else:
                content_id = medialib_db.content_register(**content_new_data, connection=connection)
            medialib_db.add_tags_for_content(content_id, tags, connection)
        tags = dict()
        representations = None
        if content_id is not None:
            tags = medialib_db.get_tags_by_content_id(content_id, auto_open_connection=False)
            representations = medialib_db.get_representation_by_content_id(content_id, connection)
        connection.close()
        if is_file:
            return flask.render_template(
                'content-metadata.html',
                item=filesystem.browse.get_file_info(path),
                file_name=path.name,
                tags=tags,
                derpibooru_dl_server=config.derpibooru_dl_server,
                albums=None,
                representations=None,
                **template_kwargs
            )
        else:
            file_item = None
            try:
                file_item = filesystem.browse.get_db_content_info(
                    content_id, db_query_results[1], db_query_results[3], db_query_results[2], icon_scale=2
                )[0]
            except FileNotFoundError:
                pass
            return flask.render_template(
                'content-metadata.html',
                item=file_item,
                file_name=path.name,
                tags=tags,
                derpibooru_dl_server=config.derpibooru_dl_server,
                albums=db_albums_registered,
                representations=representations,
                **template_kwargs
            )
    if content_id is not None:
        return body(None, content_id)
    elif pathstr is not None:
        return file_url_template(body, pathstr)


@app.route('/autodownload/mlid<int:content_id>', methods=['GET'], defaults={'pathstr': None})
@app.route('/autodownload/<string:pathstr>', methods=['GET'], defaults={'content_id': None})
@shared_code.login_validation
def autodownload(pathstr, content_id):
    def body(path: pathlib.Path | None, content_id=None):
        def detect_content_type(path: pathlib.Path):
            if path.suffix in filesystem.browse.image_file_extensions:
                return "image"
            elif path.suffix in filesystem.browse.video_file_extensions:
                data = pyimglib.decoders.ffmpeg.probe(path)
                if len(pyimglib.decoders.ffmpeg.parser.find_audio_streams(data)):
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

        connection = medialib_db.common.make_connection()
        db_query_results = None
        db_albums_registered = None
        is_file = True
        if content_id is not None:
            is_file = False
            db_query_results = medialib_db.get_content_metadata_by_content_id(
                content_id, connection
            )
            path = pathlib.Path(db_query_results[1])
            db_albums_registered = medialib_db.get_content_albums(content_id, connection)
            if db_albums_registered is not None and len(db_albums_registered) == 0:
                db_albums_registered = None
        else:
            db_query_results = medialib_db.get_content_metadata_by_file_path(
                path, connection
            )
        content_title: str | None = None
        prefix_id = None
        path_str = shared_code.str_to_base32(str(path))
        template_kwargs = {
            'content_id': "",
            'origin_name': "",
            'origin_id': ""
        }
        if db_query_results is not None:
            template_kwargs['content_id'] = db_query_results[0]
            content_id = db_query_results[0]
            if db_query_results[2] is not None:
                content_title = db_query_results[2]
            if db_query_results[-3] is not None:
                template_kwargs['origin_name'] = db_query_results[-3]
                if db_query_results[-2] is not None and \
                        template_kwargs['origin_name'] in ORIGIN_PREFIX:
                    prefix_id = "{}{}".format(
                        ORIGIN_PREFIX[template_kwargs['origin_name']], 
                        db_query_results[-2]
                    )
            else:
                prefix_id = "mlid{}".format(
                    db_query_results[0]
                )
            if db_query_results[-2] is not None:
                template_kwargs['origin_id'] = db_query_results[-2]
        representations: list[medialib_db.srs_indexer.ContentRepresentationUnit] | None = \
            None
        if content_id is not None:
            representations = medialib_db.get_representation_by_content_id(
                content_id, connection
            )
        connection.close()

        if path.suffix == ".srs" and representations:
            compatible_repr: medialib_db.srs_indexer.ContentRepresentationUnit = \
                representations[0]
            for _repr in representations:
                if _repr.compatibility_level > compatible_repr.compatibility_level:
                    compatible_repr = _repr
            if compatible_repr.format == "jxl" and \
                compatible_repr.compatibility_level == 2:

                return jxl_jpeg_decode(
                    compatible_repr.file_path, 
                    True, 
                    content_title, 
                    prefix_id, 
                    path
                )
            else:
                repr_path = compatible_repr.file_path
                f = flask.send_file(repr_path)
                response = flask.make_response(f)
                filename = get_download_filename(
                    content_title, prefix_id, path, repr_path.suffix[1:]
                )
                response.headers['content-disposition'] = \
                    'attachment; filename="{}"'.format(
                        urllib.parse.quote(filename)
                    )
                return response
        elif path.suffix == ".jxl":
            return jxl_jpeg_decode(path, True, content_title, prefix_id, path)
        elif path.suffix.lower() in {".jpg", ".jpeg"}:
            if content_title is not None and prefix_id is not None:
                safe_title = content_title.replace(
                    "?", "-qm-"
                ).replace(
                    "&", "-amp-"
                ).replace(
                    "=", "-eq-"
                ).replace(
                    "#", "-hash-"
                )
                return flask.redirect(
                    f"/image/jpeg/{path_str}?download=1&origin_id={prefix_id}&title={safe_title}"
                )
            elif prefix_id is not None:
                return flask.redirect(
                    f"/image/jpeg/{path_str}?download=1&origin_id={prefix_id}"
                )
            else:
                return flask.redirect(
                    f"/image/jpeg/{path_str}?download=1"
                )
        else:
            f = flask.send_file(path)
            response = flask.make_response(f)
            filename = get_download_filename(
                content_title, prefix_id, path, path.suffix[1:]
            )
            response.headers['content-disposition'] = \
                'attachment; filename="{}"'.format(
                    urllib.parse.quote(filename)
                )
            return response

    if content_id is not None:
        return body(None, content_id)
    elif pathstr is not None:
        return file_url_template(body, pathstr)


def mpd_processing(mpd_file: pathlib.Path):
    subs_file = mpd_file.with_suffix(".mpd.subs")
    logger.debug("subs file: {} ({})".format(subs_file, subs_file.exists()))
    if subs_file.exists():
        mpd_document: xml.dom.minidom.Document = xml.dom.minidom.parse(str(mpd_file))
        period: xml.dom.minidom.Element = mpd_document.getElementsByTagName("Period")[0]
        with subs_file.open() as f:
            subs = json.load(f)
            for subtitle in subs:
                last_repr_id = int(mpd_document.getElementsByTagName("Representation")[-1].getAttribute("id"))
                if "webvtt" in subtitle:
                    _as: xml.dom.minidom.Element = mpd_document.createElement("AdaptationSet")
                    _as.setAttribute("mimeType", "text/vtt")
                    _as.setAttribute("lang", subtitle["lang2"])

                    _repr: xml.dom.minidom.Element = mpd_document.createElement("Representation")
                    _repr.setAttribute("id", str(last_repr_id + 1))
                    _repr.setAttribute("bandwidth", "123")

                    url: xml.dom.minidom.Element = mpd_document.createElement("BaseURL")
                    url_text_node = mpd_document.createTextNode(subtitle["webvtt"])

                    url.appendChild(url_text_node)
                    _repr.appendChild(url)
                    _as.appendChild(_repr)

                    period.appendChild(_as)
        return flask.Response(mpd_document.toprettyxml(), mimetype="application/dash+xml")
    else:
        return static_file(mpd_file)


def file_processing(file: pathlib.Path):
    if file.suffix == ".mpd":
        return mpd_processing(file)
    else:
        return static_file(file)


@app.route('/browse/<path:pathstr>')
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


@app.route('/helloword')
def hello_world():
    return 'Hello, World!'


class VideoTranscoder(abc.ABC):
    def __init__(self):
        self._buffer = None
        self._io = None
        self.process = None

    @abc.abstractmethod
    def get_specific_commandline_part(self, path, fps):
        return None

    @abc.abstractmethod
    def get_output_buffer(self):
        return None

    @abc.abstractmethod
    def read_input_from_pipe(self, pipe_output):
        pass

    @abc.abstractmethod
    def get_mimetype(self):
        return None

    def do_convert(self, pathstr):
        def body(path):
            data = pyimglib.decoders.ffmpeg.probe(path)
            video = None
            for stream in data['streams']:
                if stream['codec_type'] == "video" and \
                        (video is None or stream['disposition']['default'] == 1):
                    video = stream
            fps = None
            if video['avg_frame_rate'] == "0/0":
                fps = eval(video['r_frame_rate'])
            else:
                fps = eval(video['avg_frame_rate'])
            seek_position = flask.request.args.get('seek', None)
            commandline = [
                'ffmpeg',
            ]
            if seek_position is not None:
                commandline += [
                    '-ss', seek_position
                ]
            commandline += self.get_specific_commandline_part(path, fps)
            self.process = subprocess.Popen(commandline, stdout=subprocess.PIPE)
            self.read_input_from_pipe(self.process.stdout)
            f = flask.send_file(self.get_output_buffer(), etag=False, mimetype=self.get_mimetype())
            return f

        return file_url_template(body, pathstr)


class VP8_VideoTranscoder(VideoTranscoder):
    def __init__(self):
        super().__init__()
        self._encoder = "libvpx"

    def get_mimetype(self):
        return "video/webm"

    def read_input_from_pipe(self, pipe_output):
        self._io = pipe_output

    def get_specific_commandline_part(self, path, fps):
        width = flask.request.args.get('width', 1440)
        height = flask.request.args.get('height', 720)
        return [
            '-i', str(path),
            '-vf',
            'scale=\'min({},iw)\':\'min({}, ih)\''.format(width, height) + \
            ':force_original_aspect_ratio=decrease' + \
            (",fps={}".format(fps / 2) if fps > 30 else ""),
            '-deadline', 'realtime',
            '-cpu-used', '5',
            '-vcodec', self._encoder,
            '-crf', '10',
            '-b:v', '8M',
            '-ac', '2',
            '-acodec', 'libopus',
            '-b:a', '144k',
            '-f', 'webm',
            '-'
        ]

    def get_output_buffer(self):
        return self._io


class VP9_VideoTranscoder(VP8_VideoTranscoder):
    def __init__(self):
        super().__init__()
        self._encoder = "libvpx-vp9"


@app.route('/vp8/<string:pathstr>')
@shared_code.login_validation
def ffmpeg_vp8_simplestream(pathstr):
    vp8_converter = VP8_VideoTranscoder()
    return vp8_converter.do_convert(pathstr)


@app.route('/vp9/<string:pathstr>')
@shared_code.login_validation
def ffmpeg_vp9_simplestream(pathstr):
    vp9_converter = VP9_VideoTranscoder()
    return vp9_converter.do_convert(pathstr)


class NVENC_VideoTranscoder(VideoTranscoder):
    def get_mimetype(self):
        return "video/mp4"

    def __init__(self):
        global tmp_file
        super().__init__()
        # self.tmpfile = tempfile.TemporaryFile()
        if not tmp_file.closed:
            tmp_file.close()
        tmp_file = tempfile.NamedTemporaryFile(delete=True)

    def get_specific_commandline_part(self, path, fps):
        width = flask.request.args.get('width', 1440)
        height = flask.request.args.get('height', 720)
        return [
            '-y',
            '-i', str(path),
            '-vf',
            'scale=\'min({},iw)\':\'min({}, ih)\''.format(width, height) + \
            ':force_original_aspect_ratio=decrease' + \
            (",fps={}".format(fps / 2) if fps > 30 else ""),
            '-vcodec', 'h264_nvenc',
            '-preset', 'fast',
            '-b:v', '8M',
            '-ac', '2',
            '-acodec', 'libfdk_aac',
            '-vbr', '4',
            '-f', 'mp4',
            tmp_file.name
        ]

    def get_output_buffer(self):
        return tmp_file.name

    def read_input_from_pipe(self, pipe_output):
        self.process.wait()


@app.route('/nvenc/<string:pathstr>')
@shared_code.login_validation
def ffmpeg_nvenc_filestream(pathstr):
    nvenc_converter = NVENC_VideoTranscoder()
    return nvenc_converter.do_convert(pathstr)


@app.route('/aclmmp_webm/<string:pathstr>')
@shared_code.login_validation
def aclmmp_webm_muxer(pathstr):
    def body(path):
        dir = path.parent
        SRS_file = path.open('r')
        content_metadata, streams_metadata, minimal_content_compatibility_level = ACLMMP.srs_parser.parseJSON(
            SRS_file,
            webp_compatible=True
        )
        SRS_file.close()
        LEVEL = int(flask.session['clevel'])
        CHANNELS = int(flask.session['audio_channels'])
        if minimal_content_compatibility_level < LEVEL:
            flask.abort(404)
        commandline = ['ffmpeg']
        video_file = False
        audio_file = False
        if streams_metadata[0] is not None:
            video_file= True
            commandline += ['-i', dir.joinpath(streams_metadata[0].get_compatible_files(LEVEL)[0])]
        if streams_metadata[1] is not None:
            audio_file = True
            file = streams_metadata[1][0].get_file(CHANNELS, LEVEL)
            if file is not None:
                commandline += ['-i', dir.joinpath(file)]
            else:
                files = streams_metadata[1][0].get_compatible_files(LEVEL)
                commandline += ['-i', dir.joinpath(files[0])]
        if video_file and audio_file:
            commandline += ['-map', '0', '-map', '1']
        commandline += ['-c', 'copy', '-f', 'webm', '-']
        process = subprocess.Popen(commandline, stdout=subprocess.PIPE)
        f = flask.send_file(process.stdout, add_etags=False, mimetype='video/webm')
        return f
    return file_url_template(body, pathstr)


@app.route('/folder_icon_paint/<path:pathstr>')
@shared_code.login_validation
def icon_paint(pathstr):
    import static.images.folder_icon_painter as folder_icon_painter
    scale = float(flask.request.args.get('scale', 1))
    dir = pathlib.Path(pathstr).absolute()
    data = None
    with dir.joinpath(".imgview-dir-config.json").open("r") as f:
        data = json.load(f)
    rendered_template = None
    if data['cover'] is not None:
        thumbnail_path = dir.joinpath(data['cover'])
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
        width, height, = 0, 0
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
            shared_code.str_to_base32(str(thumbnail_path.relative_to(shared_code.root_dir)))
        )
        if data['color'] is not None:
            stops = folder_icon_painter.paint_icon(data['color'])
            rendered_template = flask.render_template(
                'folder icon blank.svg',
                stops=stops,
                xoffset=xoffset,
                yoffset=yoffset,
                width=width,
                height=height,
                img_url=img_url
            )
        else:
            rendered_template = flask.render_template(
                'folder icon blank.svg',
                stops=folder_icon_painter.stops,
                xoffset=xoffset,
                yoffset=yoffset,
                width=width,
                height=height,
                img_url=img_url
            )
    else:
        stops = folder_icon_painter.paint_icon(data['color'])
        rendered_template = flask.render_template('folder icon.svg', stops=stops)
    return flask.Response(rendered_template, mimetype="image/svg+xml")


@app.route('/m3u8/<string:pathstr>.m3u8')
@shared_code.login_validation
def gen_m3u8(pathstr):
    path = pathlib.Path(shared_code.base32_to_str(pathstr))
    if path.is_file():
        buffer = io.StringIO()
        with path.open("r") as f:
            for line in f:
                if '#' in line:
                    buffer.write(line)
                elif line.strip() == "":
                    buffer.write(line)
                else:
                    base32path = shared_code.str_to_base32(str(path.parent.joinpath(line)).rstrip())
                    base_url = "https://{}:{}/orig/{}".format(
                        config.host_name,
                        config.port,
                        base32path
                    )
                    access_token = shared_code.gen_access_token()
                    shared_code.access_tokens[base_url] = access_token
                    buffer.write(base_url + "?access_token={}\n".format(access_token))
        return flask.Response(buffer.getvalue(), mimetype="audio/x-mpegurl", status=200)
    else:
        flask.abort(404)


@app.route('/<path:pathstr>')
@shared_code.login_validation
def root_open_file(pathstr):
    path = pathlib.Path(pathstr).absolute()
    if pathlib.Path(path).is_file():
        return static_file(path)
    else:
        flask.abort(404)


@app.route('/ffprobe_json/<string:pathstr>')
@shared_code.login_validation
def ffprobe_response(pathstr):
    path = pathlib.Path(shared_code.base32_to_str(pathstr))
    if path.is_file():
        return flask.Response(pyimglib.decoders.ffmpeg.probe(path), mimetype="application/json")
    else:
        flask.abort(404)


@app.route('/webvtt/<string:pathstr>')
@shared_code.login_validation
def get_vtt_subs(pathstr):
    path = pathlib.Path(shared_code.base32_to_str(pathstr) + ".vtt")
    if path.is_file():
        return static_file(path, mimetype="text/vtt")
    else:
        flask.abort(404)


@app.errorhandler(401)
def show_login_form(event):
    f = None
    if 'redirect_to' in flask.request.form:
        f = flask.render_template(
            'login.html',
            redirect_to=str(flask.request.form['redirect_to']),
            items_per_page=config.items_per_page
        )
    else:
        f = flask.render_template(
            'login.html',
            redirect_to=str(flask.request.url),
            items_per_page=config.items_per_page
        )
    return flask.Response(f, status=401)


@app.route('/login', methods=['POST'])
def login_handler():
    import hashlib
    import config
    if hashlib.sha3_512(flask.request.form['password'].encode("utf-8")).hexdigest() == \
            config.valid_password_hash_hex and \
            flask.request.form['login'] == config.valid_login:
        flask.session['logged_in'] = True
        flask.session['clevel'] = flask.request.form['clevel']
        config.ACLMMP_COMPATIBILITY_LEVEL = int(flask.request.form['clevel'])
        flask.session['audio_channels'] = flask.request.form['ac']
        flask.session['items_per_page'] = int(flask.request.form['items_per_page'])
        thumbnail_size = flask.request.form['thumbnail_size'].split("x", maxsplit=1)
        flask.session['thumbnail_width'] = int(thumbnail_size[0])
        flask.session['thumbnail_height'] = int(thumbnail_size[1])
        response = flask.make_response(flask.redirect(flask.request.form['redirect_to']))
        response.set_cookie("clevel", str(int(flask.request.form['clevel'])))
        return response
    else:
        flask.abort(401)


if __name__ == '__main__':
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
    parser.add_argument("--anon", help="enable access by anonymous", action="store_false")
    parser.add_argument(
        '--disable-external-content',
        help="Don't include external content links in template (web pages). Useful when you offline.",
        action="store_false"
    )
    args = parser.parse_args()
    os.chdir(args.root_dir)
    shared_code.root_dir = pathlib.Path('.').absolute()
    if args.port is not None:
        port = args.port
    shared_code.anonymous_forbidden = args.anon
    shared_code.enable_external_scripts = args.disable_external_content
    app.secret_key = os.urandom(12)
    app.run(host=config.host_name, port=port, ssl_context=ssl_context)
