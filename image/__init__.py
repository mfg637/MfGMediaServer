import logging
import flask
import io
import urllib.parse
import pathlib
import subprocess

import magic
import medialib_db
import shared_code
import pyimglib
import filesystem
import PIL.Image
from shared_code import route_template


logger = logging.getLogger(__name__)


image_blueprint = flask.Blueprint("image", __name__, url_prefix="/image")


def jxl_jpeg_decode(file_path, download, content_title, origin_id, path):
    logger.info("decoding JPEG XL to JPEG")
    jpeg_buffer = io.BytesIO(shared_code.jpeg_xl_fast_decode(file_path))
    f = flask.send_file(jpeg_buffer, mimetype="image/jpeg")
    response = flask.make_response(f)
    if download:
        filename = shared_code.get_download_filename(
            content_title, origin_id, path, "jpeg"
        )
        response.headers["content-disposition"] = (
            'attachment; filename="{}"'.format(urllib.parse.quote(filename))
        )
    return response


@image_blueprint.route("/transcode/<string:_format>/<string:pathstr>")
@shared_code.login_validation
def transcode_image(_format: str, pathstr):
    def body(path: pathlib.Path, _format):
        logger.debug(
            "TRANSCODE path = {}, format = {}".format(path.__repr__(), _format)
        )
        origin_id = flask.request.args.get("origin_id", None, str)
        content_title = flask.request.args.get("title", None, str)
        download: bool = flask.request.args.get("download", False, bool)
        src_hash, status_code = shared_code.cache_check(path)
        if status_code is not None:
            return status_code
        if path.suffix == ".jxl" and _format == "jpeg":
            return jxl_jpeg_decode(
                path, download, content_title, origin_id, path
            )
        img = pyimglib.decoders.open_image(path)
        possible_formats = (_format,)
        LEVEL = int(flask.session["clevel"])
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
            current_lod_format = pyimglib.decoders.get_image_format(
                current_lod
            )
            logger.debug(
                "current_lod {}: {}".format(
                    current_lod.__repr__(), current_lod_format
                )
            )
            if _format == "png":
                img = pyimglib.decoders.open_image(current_lod)
            else:
                while len(lods):
                    if current_lod_format not in possible_formats:
                        current_lod = lods.pop()
                        current_lod_format = (
                            pyimglib.decoders.get_image_format(current_lod)
                        )
                        logger.debug(
                            "current_lod {}: {}".format(
                                current_lod.__repr__(), current_lod_format
                            )
                        )
                    else:
                        break
                if current_lod_format in possible_formats and not download:
                    base32path = route_template.str_to_base32(str(current_lod))
                    return flask.redirect(
                        "{}orig/{}".format(flask.request.host_url, base32path)
                    )
                elif current_lod_format == _format and download:
                    absolute_path = shared_code.root_dir.joinpath(current_lod)
                    f = flask.send_file(
                        absolute_path,
                        mimetype=shared_code.MIME_TYPES_BY_FORMAT[_format],
                    )
                    filename = shared_code.get_download_filename(
                        content_title, origin_id, path, _format
                    )
                    response = flask.make_response(f)
                    response.headers["content-disposition"] = (
                        'attachment; filename="{}"'.format(
                            urllib.parse.quote(filename)
                        )
                    )
                    return response
                else:
                    if current_lod_format == "jpeg xl" and _format == "jpeg":
                        return jxl_jpeg_decode(
                            current_lod,
                            download,
                            content_title,
                            origin_id,
                            path,
                        )
                    else:
                        img = pyimglib.decoders.open_image(current_lod)
        if isinstance(img, pyimglib.decoders.frames_stream.FramesStream):
            _img = img.next_frame()
            img.close()
            img = _img
        img = img.convert(mode="RGBA")
        buffer = io.BytesIO()
        mime = ""
        if _format.lower() == "webp":
            img.save(
                buffer, format="WEBP", quality=90, method=4, lossless=False
            )
            mime = "image/webp"
        elif _format.lower() == "jpeg":
            if pyimglib.decoders.jpeg.is_JPEG(path):
                jpeg_data = path.read_bytes()
                transcoding_result = subprocess.run(
                    ["jpegtran", "-copy", "all"],
                    input=jpeg_data,
                    capture_output=True,
                )
                buffer = io.BytesIO(transcoding_result.stdout)
            else:
                img = img.convert(mode="RGB")
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
        # response = flask.Response(buffer, mimetype=mime, )
        f.set_etag(src_hash)
        response = flask.make_response(f)
        if download:
            filename = shared_code.get_download_filename(
                content_title, origin_id, path, _format
            )
            response.headers["content-disposition"] = (
                'attachment; filename="{}"'.format(
                    urllib.parse.quote(filename)
                )
            )
        return response

    return route_template.file_url_template(body, pathstr, _format=_format)


@image_blueprint.route(
    "/thumbnail/<string:_format>/<int:width>x<int:height>/<string:pathstr>"
)
@shared_code.login_validation
def gen_thumbnail(_format: str, width: int, height: int, pathstr: str | None):

    def srs_image_processing(
        img, allow_origin
    ) -> PIL.Image.Image | pathlib.Path:
        logger.info("srs image processing")
        lods: list[pathlib.Path] = img.progressive_lods()
        compatibility_level = int(flask.request.cookies.get("clevel", 3))
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
            if isinstance(
                current_lod_img, pyimglib.decoders.frames_stream.FramesStream
            ):
                current_lod_img = current_lod_img.next_frame()
            if (
                current_lod_img.width < width
                and current_lod_img.height < height
            ):
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
        return (
            allow_origin
            and img.format == "WEBP"
            and (
                img.is_animated
                or (img.width <= width and img.height <= height)
            )
        )

    def complex_formats_processing(
        img, file_path, allow_origin
    ) -> PIL.Image.Image | flask.Response:
        logger.info("complex_formats_processing")
        if isinstance(img, pyimglib.decoders.srs.ClImage):
            selected_image = srs_image_processing(img, allow_origin)
            logger.debug(
                "srs_image_processing: {}".format(selected_image.__repr__())
            )
            if isinstance(selected_image, pathlib.Path):
                base32path = route_template.str_to_base32(str(selected_image))
                return flask.make_response(
                    flask.redirect(
                        "{}orig/{}".format(flask.request.host_url, base32path)
                    )
                )
            else:
                img = selected_image
        if isinstance(img, pyimglib.decoders.frames_stream.FramesStream):
            img = shared_code.extract_frame_from_video(img)
            logger.debug("extracted frame: {}".format(img.__repr__()))
        if check_origin_allowed(img, allow_origin):
            logger.info("origin redirect allowed")
            base32path = route_template.str_to_base32(str(file_path))
            return flask.make_response(
                flask.redirect(
                    "{}orig/{}".format(flask.request.host_url, base32path)
                )
            )
        return img

    def file_path_processing(path, _format, width, height):
        logger.info("file_path_processing")
        allow_origin = bool(flask.request.args.get("allow_origin", False))
        src_hash, status_code = None, None
        if path.stat().st_size < (1024 * 1024 * 1024):
            src_hash, status_code = shared_code.cache_check(path)
        if status_code is not None:
            return status_code
        img = pyimglib.decoders.open_image(
            shared_code.root_dir.joinpath(path), (width, height)
        )
        extracted_img = complex_formats_processing(img, path, allow_origin)
        if isinstance(extracted_img, flask.Response):
            return extracted_img
        elif isinstance(extracted_img, PIL.Image.Image):
            img = extracted_img
        else:
            raise NotImplementedError(type(extracted_img))
        buffer, mime, _format = shared_code.generate_thumbnail_image(
            img, _format, width, height
        )
        f = flask.send_file(
            buffer,
            mimetype=mime,
            max_age=24 * 60 * 60,
            last_modified=path.stat().st_mtime,
        )
        if src_hash is not None:
            f.set_etag(src_hash)
        return f

    return route_template.file_url_template(
        file_path_processing,
        pathstr,
        _format=_format,
        width=width,
        height=height,
    )


@image_blueprint.route(
    "/autodownload/mlid<int:content_id>",
    methods=["GET"],
    defaults={"pathstr": None},
)
@image_blueprint.route(
    "/autodownload/<string:pathstr>",
    methods=["GET"],
    defaults={"content_id": None},
)
@shared_code.login_validation
def autodownload(pathstr, content_id):
    def body(path: pathlib.Path | None, content_id=None):
        connection = medialib_db.common.make_connection()
        db_content = None
        if content_id is not None:
            db_content = medialib_db.content.get_content_metadata_by_id(
                content_id, connection
            )
            if db_content is None:
                return flask.abort(404)
            path = db_content.file_path
        elif path is not None:
            db_content = medialib_db.content.get_content_metadata_by_path(
                path, connection
            )
        if path is None:
            raise ValueError("Unexpected behaviour: path is still None")
        content_title: str | None = None
        prefix_id = None
        path_str = shared_code.route_template.str_to_base32(str(path))
        template_kwargs = {
            "content_id": "",
            "origin_name": "",
            "origin_id": "",
        }
        if db_content is not None:
            template_kwargs["content_id"] = str(db_content.content_id)
            content_id = db_content.content_id
            if db_content.title is not None:
                content_title = db_content.title
            origins = medialib_db.origin.get_origins_of_content(
                connection, content_id
            )
            if len(origins):
                for origin in origins:
                    if origin.origin_id is not None:
                        prefix = origin.get_prefix()
                        if prefix is not None:
                            prefix_id = "{}{}".format(prefix, origin.origin_id)
            if prefix_id is None:
                prefix_id = "mlid{}".format(db_content.content_id)
        representations: (
            list[medialib_db.srs_indexer.ContentRepresentationUnit] | None
        ) = None
        if content_id is not None:
            representations = medialib_db.get_representation_by_content_id(
                content_id, connection
            )
        connection.close()

        if path.suffix == ".srs" and representations:
            compatible_repr: (
                medialib_db.srs_indexer.ContentRepresentationUnit
            ) = representations[0]
            for _repr in representations:
                if (
                    _repr.compatibility_level
                    > compatible_repr.compatibility_level
                ):
                    compatible_repr = _repr
            if (
                compatible_repr.format == "jxl"
                and compatible_repr.compatibility_level == 2
            ):

                return jxl_jpeg_decode(
                    compatible_repr.file_path,
                    True,
                    content_title,
                    prefix_id,
                    path,
                )
            else:
                repr_path = compatible_repr.file_path
                f = flask.send_file(repr_path)
                response = flask.make_response(f)
                filename = shared_code.get_download_filename(
                    content_title, prefix_id, path, repr_path.suffix[1:]
                )
                response.headers["content-disposition"] = (
                    'attachment; filename="{}"'.format(
                        urllib.parse.quote(filename)
                    )
                )
                return response
        elif path.suffix == ".jxl":
            return jxl_jpeg_decode(path, True, content_title, prefix_id, path)
        elif path.suffix.lower() in {".jpg", ".jpeg"}:
            if content_title is not None and prefix_id is not None:
                safe_title = (
                    content_title.replace("?", "-qm-")
                    .replace("&", "-amp-")
                    .replace("=", "-eq-")
                    .replace("#", "-hash-")
                )
                return flask.redirect(
                    (
                        (
                            f"/image/jpeg/{path_str}?download=1&"
                            f"origin_id={prefix_id}&title={safe_title}"
                        )
                    )
                )
            elif prefix_id is not None:
                return flask.redirect(
                    f"/image/jpeg/{path_str}?download=1&origin_id={prefix_id}"
                )
            else:
                return flask.redirect(f"/image/jpeg/{path_str}?download=1")
        else:
            f = flask.send_file(path)
            response = flask.make_response(f)
            filename = shared_code.get_download_filename(
                content_title, prefix_id, path, path.suffix[1:]
            )
            response.headers["content-disposition"] = (
                'attachment; filename="{}"'.format(
                    urllib.parse.quote(filename)
                )
            )
            return response

    if content_id is not None:
        return body(None, content_id)
    elif pathstr is not None:
        return route_template.file_url_template(body, pathstr)


@image_blueprint.route(
    "/autotag/mlid<int:content_id>",
    methods=["GET", "POST"],
    defaults={"pathstr": None},
)
@image_blueprint.route(
    "/autotag/<string:pathstr>",
    methods=["GET", "POST"],
    defaults={"content_id": None},
)
@shared_code.login_validation
def get_tags_from_external_service(pathstr, content_id):
    def body(path: pathlib.Path | None, content_id=None):
        connection = medialib_db.common.make_connection()
        db_content: medialib_db.content.Content | None = None
        is_file = True
        if content_id is not None:
            is_file = False
            db_content = medialib_db.content.get_content_metadata_by_id(
                content_id, connection
            )
            if db_content is None:
                return flask.abort(
                    404, f"Content with ID {content_id} not found"
                )
            path = db_content.file_path
        elif path is not None:
            db_content = medialib_db.content.get_content_metadata_by_path(
                path, connection
            )
        else:
            return flask.abort(
                400,
                "expected content ID or path str but no arguments provided",
            )

        representations: (
            list[medialib_db.srs_indexer.ContentRepresentationUnit] | None
        ) = None
        if content_id is not None:
            representations = medialib_db.get_representation_by_content_id(
                content_id, connection
            )
        connection.close()

        img = None
        img_file = None
        img_file_path = None
        mime = None

        if path.suffix == ".srs" and representations:
            compatible_repr: (
                medialib_db.srs_indexer.ContentRepresentationUnit
            ) = representations[0]
            for _repr in representations:
                if (
                    _repr.compatibility_level
                    > compatible_repr.compatibility_level
                ):
                    compatible_repr = _repr
            if (
                compatible_repr.format == "jxl"
                and compatible_repr.compatibility_level == 2
            ):
                img_file = shared_code.jpeg_xl_fast_decode(
                    compatible_repr.file_path
                )
                mime = "image/jpeg"
            else:
                img_file_path = compatible_repr.file_path
        elif path.suffix == ".jxl":
            img_file = shared_code.jpeg_xl_fast_decode(path)
            mime = "image/x-portable-anymap"
        elif path.suffix.lower() in {".jpg", ".jpeg"}:
            jpeg_object = pyimglib.decoders.jpeg.JPEGDecoder(path)
            try:
                if jpeg_object.arithmetic_coding():
                    img_file = jpeg_object.decode().stdout
                else:
                    img_file_path = path
            except ValueError:
                img_file = jpeg_object.decode().stdout
        elif path.suffix.lower() in {".png", ".webp"}:
            img_file_path = path
        else:
            img = pyimglib.decoders.open_image(path)

        URL = "http://127.0.0.1:10877/tagging"

        import requests

        if img_file is not None:
            r = requests.post(
                URL, data={"threshold": "0.1"}, files={"image-file": img_file}
            )
        elif img_file_path is not None:
            mime = magic.from_file(str(img_file_path), mime=True)
            r = requests.post(
                URL,
                data={"threshold": "0.1"},
                files={
                    "image-file": (
                        img_file_path.name,
                        img_file_path.open("br"),
                        mime,
                    )
                },
            )
        elif img is not None:
            png_file = io.BytesIO()
            img.save(png_file, "PNG")
            r = requests.post(
                URL,
                data={"threshold": "0.1"},
                files={
                    "image-file": (path.name, png_file.getvalue(), "image/png")
                },
            )
        else:
            print(img, img_file, img_file_path)
            raise Exception("Undefined state")

        tags = r.json()

        if is_file:
            return flask.render_template(
                "tag_select_form.html",
                item=filesystem.browse.get_file_info(path),
                file_name=path.name,
                tags=tags,
                resource_id_type="file",
                resource_id=pathstr,
            )
        elif db_content is not None:
            file_item = None
            try:
                file_item = filesystem.browse.get_db_content_info(
                    db_content.content_id,
                    str(db_content.file_path),
                    db_content.content_type,
                    db_content.title,
                    icon_scale=2,
                )[0]
            except FileNotFoundError:
                pass
            return flask.render_template(
                "tag_select_form.html",
                item=file_item,
                file_name=path.name,
                tags=tags,
                resource_id_type="content_id",
                resource_id=content_id,
            )
        else:
            return flask.abort(500, "db_content is None and not file")

    if content_id is not None:
        return body(None, content_id)
    elif pathstr is not None:
        return route_template.file_url_template(body, pathstr)
