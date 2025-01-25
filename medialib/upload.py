import flask
import shared_code
import pyimglib
import magic
import io
import PIL.Image
import PIL.ExifTags
import medialib_db
import datetime
import random
import string
import pathlib
import pyimglib
import pillow_heif
import re
import dataclasses

from shared_code import EXTENSIONS_BY_MIME

simple_id_pattern = re.compile("[a-z]{2}\d+")

CIVIT_AI_ORIGIN = "civit ai"
MAX_TITLE_LENGTH = 63
MAX_SAMPLE_LENGTH = 200 * 1024 * 1024 # 200 MiB
MOV_MIMETYPE = "video/quicktime"
MPEG4V_MIMETYPE = "video/mp4"
JPEG_MIMETYPE = "image/jpeg"
AVIF_MIMETYPE = "image/avif"

def generate_unsupported_type_response():
    supported_formats = []
    for mime in EXTENSIONS_BY_MIME:
        supported_formats.append(f"{EXTENSIONS_BY_MIME[mime]} ({mime})")
    return flask.Response(
        "Server accepts only this formats: " + \
            ", ".join(supported_formats),
        415
    )

def detect_file_type(file_buffer, request_header_mimetype):
    mime = magic.from_buffer(file_buffer.getvalue(), mime=True)
    if mime == MOV_MIMETYPE and request_header_mimetype == MPEG4V_MIMETYPE:
        mime = MPEG4V_MIMETYPE
    is_image = False
    if mime.startswith("image/"):
        is_image = True
        file_type = None
    if is_image:
        file_type = "image"
    elif mime.startswith("video/"):
        file_type = "video"
    elif mime.startswith("audio/"):
        file_type = "audio"
    else:
        raise Exception("undetected content type")
    return mime, file_type, is_image

def detect_source(filename: str, origin_name: str | None, origin_id: str | None):
    if origin_name is None and simple_id_pattern.match(filename) is not None and filename[:2] == "ca":
        origin_name = CIVIT_AI_ORIGIN
    if origin_name == CIVIT_AI_ORIGIN:
        if simple_id_pattern.match(filename) is not None:
            origin_id = filename[2:]
        elif re.match("\d+", filename) is not None:
            origin_id = filename
    return origin_name, origin_id


@dataclasses.dataclass
class PlainTextData:
    data: str


def extract_metadata_from_image(img: PIL.Image.Image, mime: str, origin_name: str | None):
    if mime == JPEG_MIMETYPE and origin_name == CIVIT_AI_ORIGIN:
        if "exif" in img.info:
            exif = img.getexif()
            exif_items = {k:v for k, v in exif.get_ifd(PIL.ExifTags.Base.ExifOffset).items()}
            user_comment_raw: bytes = exif_items[37510]
            return PlainTextData(user_comment_raw.decode("utf-16_be")[5:])
    return None

upload_blueprint = flask.Blueprint('upload', __name__, url_prefix='/upload')


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

    file = flask.request.files["image-file"]
    description, origin_name, origin_id = extract_fields()
    file_buffer = io.BytesIO(file.stream.read(MAX_SAMPLE_LENGTH))
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
    if is_image:
        if mime == AVIF_MIMETYPE:
            heif = pillow_heif.open_heif(file_buffer)
            img = heif.to_pillow()
        else:
            img = PIL.Image.open(file_buffer)
        image_metadata = extract_metadata_from_image(img, mime, origin_name)
        hash = pyimglib.calc_image_hash(img)
        duplicates = medialib_db.find_content_by_hash(hash[1].hex().lower(), hash[2], hash[3], connection)
        if len(duplicates) > 0:
            if "alternate_version" not in flask.request.form:
                link_elements = []
                for dup in duplicates:
                    link_elements.append(f"<a href=/content_metadata/mlid{dup[0]}>mlid{dup[0]}</a>")
                return "Duplicates detected " + ", ".join(link_elements)
            else:
                is_alternate_version = True
    
    if description is None and isinstance(image_metadata, PlainTextData):
        description = image_metadata.data
    
    outdir = shared_code.get_output_directory()
    outdir.mkdir(parents=True, exist_ok=True)

    filename = ''.join(random.choices(string.ascii_letters+string.digits, k=16)) + \
        EXTENSIONS_BY_MIME[mime]
    file_path = outdir.joinpath(filename)
    print("SAVE OUTPUT FILE", file_path)
    file.save(file_path)

    content_new_data = {
        'content_title': title,
        'file_path': file_path,
        'content_type': file_type,
        'addition_date': datetime.datetime.now(),
        'content_id': None,
        'origin_name': origin_name,
        'origin_id': origin_id,
        'hidden': False,
        'description': description,
    }
    try:
        content_id = medialib_db.content_register(**content_new_data, connection=connection)
        connection.commit()
        connection.close()
    except Exception as e:
        file_path.unlink()
        raise e

    return flask.redirect(f"/content_metadata/mlid{content_id}")