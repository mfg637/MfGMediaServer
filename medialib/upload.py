import flask
import shared_code


upload_blueprint = flask.Blueprint('upload', __name__, url_prefix='/upload')


@upload_blueprint.route("/")
@shared_code.login_validation
def show_upload_page():
    return flask.render_template("upload.html")