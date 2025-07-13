import json
import logging
import lzma
import tempfile
import typing
import flask
import medialib_db.config
import shared_code
from shared_code.file_uploading import (
    PNG_MIMETYPE,
    WEBP_MIMETYPE,
    JPEG_MIMETYPE,
    AVIF_MIMETYPE,
    MAX_TITLE_LENGTH,
    MAX_SAMPLE_LENGTH,
    detect_file_type,
    generate_filename,
)
import pyimglib
import io
import PIL.Image
import PIL.ExifTags
import medialib_db
import datetime
import pathlib
import pillow_heif
import re
import dataclasses
from pyimglib.transcoding.encoders.srs_image_encoder import (
    test_alpha_channel,
    SrsLossyJpegXlEncoder,
)
from pyimglib.decoders.srs import decode as decode_srs
from werkzeug.datastructures import FileStorage

from shared_code import EXTENSIONS_BY_MIME
from . import stealth_png

logger = logging.getLogger(__name__)

simple_id_pattern = re.compile("[a-z]{2}\d+")

CIVIT_AI_ORIGIN = "civit ai"


def generate_unsupported_type_response():
    supported_formats = []
    for mime in EXTENSIONS_BY_MIME:
        supported_formats.append(f"{EXTENSIONS_BY_MIME[mime]} ({mime})")
    return flask.Response(
        "Server accepts only this formats: " + ", ".join(supported_formats),
        415,
    )


def detect_source(
    filename: str, origin_name: str | None, origin_id: str | None
):
    if (
        origin_name is None
        and simple_id_pattern.match(filename) is not None
        and filename[:2] == "ca"
    ):
        origin_name = CIVIT_AI_ORIGIN
    if origin_name == CIVIT_AI_ORIGIN:
        if simple_id_pattern.match(filename) is not None:
            origin_id = filename[2:]
        elif re.match("\d+", filename) is not None:
            origin_id = filename
    return origin_name, origin_id


def save_image(
    source_file: FileStorage,
    file_size: int,
    mime: str,
    outdir: pathlib.Path,
    img: PIL.Image.Image,
    rgba_to_rgb: bool,
):
    is_srs = False
    if mime == PNG_MIMETYPE:
        if (
            img.has_transparency_data
            and test_alpha_channel(img)
            and not rgba_to_rgb
        ):
            filename, file_title = generate_filename(WEBP_MIMETYPE)
            file_path = outdir.joinpath(filename)
            img.save(file_path, quality=95)
        else:
            if img.has_transparency_data and rgba_to_rgb:
                if img.mode == "LA":
                    new_img = img.convert("L")
                else:
                    new_img = img.convert("RGB")
                img.close()
                img = new_img
            is_srs = True
            filename, file_title = generate_filename(JPEG_MIMETYPE)
            file_path = outdir.joinpath(filename)

            src_tmp_file = tempfile.NamedTemporaryFile(
                mode="wb", suffix=".png", delete=True
            )
            img.save(src_tmp_file, format="PNG", compress_level=0)

            srs_encoder = SrsLossyJpegXlEncoder(90, file_size, 40)
            file_path = srs_encoder.encode(
                pathlib.Path(src_tmp_file.name), file_path
            )
            src_tmp_file.close()
    else:
        filename, file_title = generate_filename(mime)
        file_path = outdir.joinpath(filename)
        print("SAVE OUTPUT FILE", file_path)
        source_file.save(file_path)
    return file_path, file_title, is_srs


@dataclasses.dataclass
class PlainTextData:
    data: str


@dataclasses.dataclass
class JSONData:
    data: typing.Any


@dataclasses.dataclass
class ComfyUIWorkflow:
    prompt: dict
    workflow: dict


def extract_metadata_from_image(
    img: PIL.Image.Image, mime: str, origin_name: str | None
):
    if mime == JPEG_MIMETYPE and origin_name == CIVIT_AI_ORIGIN:
        if "exif" in img.info:
            exif = img.getexif()
            exif_items = {
                k: v
                for k, v in exif.get_ifd(PIL.ExifTags.Base.ExifOffset).items()
            }
            user_comment_raw: bytes = exif_items[37510]
            return (
                PlainTextData(user_comment_raw.decode("utf-16_be")[5:]),
                False,
            )
    elif mime == PNG_MIMETYPE:
        if "parameters" in img.info:
            return PlainTextData(
                img.info["parameters"]
            ), stealth_png.stealth_png_check(img)
        elif "prompt" in img.info and "workflow" in img.info:
            return (
                ComfyUIWorkflow(
                    json.loads(img.info["prompt"]),
                    json.loads(img.info["workflow"]),
                ),
                stealth_png.stealth_png_check(img),
            )
        else:
            plain_text = stealth_png.read_info_from_image_stealth(img)
            if type(plain_text) is str:
                try:
                    json_data = json.loads(plain_text)
                    if "prompt" in json_data and "workflow" in json_data:
                        return (
                            ComfyUIWorkflow(
                                json.loads(img.info["prompt"]),
                                json.loads(img.info["workflow"]),
                            ),
                            True,
                        )
                    else:
                        return JSONData(json_data), True
                except json.decoder.JSONDecodeError:
                    return PlainTextData(plain_text), True
    return None, False


upload_blueprint = flask.Blueprint("upload", __name__, url_prefix="/upload")


@upload_blueprint.route("/")
@shared_code.login_validation
def show_upload_page():
    thumnbail_size = shared_code.get_thumbnail_size()
    return flask.render_template(
        "upload.html",
        preview_width=thumnbail_size["width"] * 2,
        preview_height=thumnbail_size["height"] * 2,
    )


@upload_blueprint.route("/uploading", methods=["POST"])
@shared_code.login_validation
def upload_file():
    def extract_fields() -> tuple[str | None, str | None, str | None]:
        description = None
        if len(flask.request.form["description"]) > 0:
            description = flask.request.form["description"]
        origin_name = None
        if len(flask.request.form["origin_name"]) > 0:
            origin_name = flask.request.form["origin_name"]
        origin_id = None
        if len(flask.request.form["origin_id"]) > 0:
            origin_id = flask.request.form["origin_id"]
        return description, origin_name, origin_id

    file: FileStorage = flask.request.files["image-file"]
    description, origin_name, origin_id = extract_fields()
    file_buffer = io.BytesIO(file.stream.read(MAX_SAMPLE_LENGTH))
    file_size = len(file_buffer.getvalue())
    file_buffer.seek(0)
    file.stream.seek(0)
    mime, file_type, is_image = detect_file_type(file_buffer, file.mimetype)
    file_buffer.seek(0)
    if mime not in EXTENSIONS_BY_MIME:
        return generate_unsupported_type_response()
    # trim too long filename
    title = str(pathlib.Path(file.filename).stem[:MAX_TITLE_LENGTH])
    origin_name, origin_id = detect_source(title, origin_name, origin_id)
    hash = None
    connection = medialib_db.common.make_connection()
    is_alternate_version = False
    image_metadata = None
    img = None
    rgba_to_rgb = False
    if is_image:
        if mime == AVIF_MIMETYPE:
            heif = pillow_heif.open_heif(file_buffer)
            img = heif.to_pillow()
        else:
            img = PIL.Image.open(file_buffer)
        image_metadata, rgba_to_rgb = extract_metadata_from_image(
            img, mime, origin_name
        )
        hash = pyimglib.calc_image_hash(img)
        duplicates = medialib_db.find_content_by_hash(
            hash[1].hex().lower(), hash[2], hash[3], connection
        )
        if len(duplicates) > 0:
            if "alternate_version" not in flask.request.form:
                link_elements = []
                for dup in duplicates:
                    link_elements.append(
                        f"<a href=/content_metadata/mlid{dup[0]}>mlid{dup[0]}</a>"
                    )
                return "Duplicates detected " + ", ".join(link_elements)
            else:
                is_alternate_version = True

    if description is None and isinstance(image_metadata, PlainTextData):
        description = image_metadata.data

    outdir = shared_code.get_output_directory()
    outdir.mkdir(parents=True, exist_ok=True)

    file_path, saved_name, is_srs = save_image(
        file, file_size, mime, outdir, img, rgba_to_rgb
    )
    if img is not None:
        img.close()

    content_new_data = {
        "content_title": title,
        "file_path": file_path,
        "content_type": file_type,
        "addition_date": datetime.datetime.now(),
        "content_id": None,
        "origin_name": origin_name,
        "origin_id": origin_id,
        "hidden": False,
        "description": description,
    }
    try:
        content_id = medialib_db.content_register(
            **content_new_data, connection=connection
        )
        if isinstance(image_metadata, ComfyUIWorkflow):
            binary_encoded_json = json.dumps(image_metadata.workflow).encode(
                "utf-8"
            )
            comfy_workflow_filepath = outdir.joinpath(saved_name + ".json.xz")
            with lzma.open(comfy_workflow_filepath, "wb") as f:
                f.write(binary_encoded_json)
            medialib_db.attachment.add_attachment(
                connection,
                content_id,
                "json+xz",
                comfy_workflow_filepath,
                "ComfyUI Workflow",
            )
        elif isinstance(image_metadata, JSONData):
            binary_encoded_json = json.dumps(image_metadata.data).encode(
                "utf-8"
            )
            json_filepath = outdir.joinpath(saved_name + ".json.xz")
            with lzma.open(json_filepath, "wb") as f:
                f.write(binary_encoded_json)
            medialib_db.attachment.add_attachment(
                connection,
                content_id,
                "json+xz",
                json_filepath,
                "JSON file",
            )
        if is_srs:
            srs_image = decode_srs(file_path)
            levels = srs_image.get_levels()
            for level in levels:
                representation_file = outdir.joinpath(levels[level])
                relative_repr_path = str(
                    representation_file.relative_to(
                        medialib_db.config.relative_to
                    )
                )
                medialib_db.register_representation(
                    content_id,
                    representation_file.suffix[1:],
                    level,
                    relative_repr_path,
                    connection,
                )
        connection.commit()
        connection.close()
    except Exception as e:
        file_path.unlink()
        raise e

    return flask.redirect(f"/content_metadata/mlid{content_id}")
