import flask
import shared_code


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