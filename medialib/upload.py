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

from shared_code import EXTENSIONS_BY_MIME

simple_id_pattern = re.compile("[a-z]{2}\d+")

CIVIT_AI_ORIGIN = "civit ai"


upload_blueprint = flask.Blueprint('upload', __name__, url_prefix='/upload')

MAX_TITLE_LENGTH = 63


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
    file = flask.request.files["image-file"]
    description = None
    if len(flask.request.form["description"]) > 0:
        description = flask.request.form["description"]
    origin_name = None
    if len(flask.request.form["origin_name"]) > 0:
        origin_name = flask.request.form["origin_name"]
    origin_id = None
    if len(flask.request.form["origin_id"]) > 0:
        origin_id = flask.request.form["origin_id"]
    is_image = False
    file_buffer = io.BytesIO(file.stream.read(200 * 1024 * 1024))
    file.stream.seek(0)
    mime = magic.from_buffer(file_buffer.getvalue(), mime=True)
    if mime == "video/quicktime" and file.mimetype == "video/mp4":
        mime = "video/mp4"
    file_buffer.seek(0)
    if mime not in EXTENSIONS_BY_MIME:
        supported_formats = []
        for mime in EXTENSIONS_BY_MIME:
            supported_formats.append(f"{EXTENSIONS_BY_MIME[mime]} ({mime})")
        return flask.Response(
            "Server accepts only this formats: " + \
                ", ".join(supported_formats),
            415
        )
    # trim too long filename
    title = str(pathlib.Path(file.filename).stem[:MAX_TITLE_LENGTH])
    if origin_name is None and simple_id_pattern.match(title) is not None and title[:2] == "ca":
        origin_name = CIVIT_AI_ORIGIN
    if origin_name == CIVIT_AI_ORIGIN:
        if simple_id_pattern.match(title) is not None:
            origin_id = title[2:]
        elif re.match("\d+", title) is not None:
            origin_id = title
    if mime.startswith("image/"):
        is_image = True
    hash = None
    connection = medialib_db.common.make_connection()
    is_alternate_version = False
    if is_image:
        if mime == "image/avif":
            heif = pillow_heif.open_heif(file_buffer)
            img = heif.to_pillow()
        else:
            img = PIL.Image.open(file_buffer)
        if mime == "image/jpeg" and origin_name == CIVIT_AI_ORIGIN and description is None:
            if "exif" in img.info:
                exif = img.getexif()
                exif_items = {k:v for k, v in exif.get_ifd(PIL.ExifTags.Base.ExifOffset).items()}
                user_comment_raw: bytes = exif_items[37510]
                description = user_comment_raw.decode("utf-16_be")[5:]

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
    
    file_type = None
    if is_image:
        file_type = "image"
    elif mime.startswith("video/"):
        file_type = "video"
    elif mime.startswith("audio/"):
        file_type = "audio"
    else:
        raise Exception("undetected content type")
    
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