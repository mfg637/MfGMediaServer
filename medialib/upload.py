import flask
import shared_code
import pyimglib
import magic
import io
import PIL.Image
import medialib_db
import datetime
import random
import string


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


EXTENSIONS_BY_MIME = {
    "image/jpeg": ".jpeg",
    "image/png": ".png",
    "image/webp": ".webp",
    "video/mp4": ".mp4",
    "video/webm": ".webm"
}


@upload_blueprint.route("/uploading", methods=["POST"])
@shared_code.login_validation
def upload_file():
    file = flask.request.files["image-file"]
    print("FILE", file)
    is_image = False
    file_buffer = io.BytesIO(file.stream.read(200 * 1024 * 1024))
    file.stream.seek(0)
    mime = magic.from_buffer(file_buffer.getvalue(), mime=True)
    if mime == "video/quicktime" and file.mimetype == "video/mp4":
        mime = "video/mp4"
    print("MIME", mime)
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
    if mime.startswith("image/"):
        is_image = True
    hash = None
    connection = medialib_db.common.make_connection()
    is_alternate_version = False
    if is_image:
        img = PIL.Image.open(file_buffer)
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
    
    MEDIALIB_ROOT = shared_code.root_dir.joinpath("pictures").joinpath("medialib")
    
    current_date = datetime.datetime.now()
    outdir = MEDIALIB_ROOT.joinpath(
        str(current_date.year), str(current_date.month), str(current_date.day)
    )
    outdir.mkdir(parents=True, exist_ok=True)

    filename = ''.join(random.choices(string.ascii_letters+string.digits, k=16)) + \
        EXTENSIONS_BY_MIME[mime]
    file_path = outdir.joinpath(filename)
    print("SAVE OUTPUT FILE", file_path)
    file.save(file_path)

    description = None
    if len(flask.request.form["description"]) > 0:
        description = flask.request.form["description"]
    
    origin_name = None
    if len(flask.request.form["origin_name"]) > 0:
        origin_name = flask.request.form["origin_name"]
    
    origin_id = None
    if len(flask.request.form["origin_id"]) > 0:
        origin_id = flask.request.form["origin_id"]

    content_new_data = {
        'content_title': file.filename,
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