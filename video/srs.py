import pathlib
import logging
import json
import flask
import tempfile
import string
import random
import pyimglib.common
import shared_code
import medialib_db
import pyimglib


logger = logging.getLogger(__name__)


srs_video_blueprint = flask.Blueprint("srs_video", __name__, url_prefix="/srs")


multiplexed_file: tempfile._TemporaryFileWrapper | None = None
tempfile_id: str | None = None
file_mimetype: str | None = None
manifest_filename: str | None = None


@srs_video_blueprint.route("/file/<string:file_id>")
@shared_code.login_validation
def access_tempfile(file_id):
    if (
        tempfile_id is None
        or multiplexed_file is None
        or file_id != tempfile_id
        or file_mimetype is None
        or manifest_filename is None
    ):
        flask.abort(404)
    return flask.send_file(
        multiplexed_file.name, file_mimetype, download_name=manifest_filename
    )


def get_manifest_file(
    pathstr: str | None, content_id: int | None
) -> pathlib.Path:
    if pathstr is not None:
        path = pathlib.Path(shared_code.route_template.base32_to_str(pathstr))
        if not path.is_file():
            flask.abort(404, "SRS manifest file not found")
    elif content_id is not None:
        connection = medialib_db.common.make_connection()
        content_data = medialib_db.content.get_content_metadata_by_id(
            content_id, connection
        )
        connection.close()
        if content_data is None:
            flask.abort(404, "content not found")
        path = content_data.file_path
        if not path.is_file():
            flask.abort(404, "SRS manifest file not found")
    else:
        flask.abort(400)

    return path


def extract_streams(srs_file: pathlib.Path, compatibility_level: int):
    with srs_file.open("r") as f:
        parsed_data = pyimglib.ACLMMP.srs_parser.parseJSON(f)
    content_metadata, streams_metadata, minimal_content_compatibility_level = (
        parsed_data
    )
    video, audio_streams, subtitle_streams, image = streams_metadata
    if video is not None:
        video_stream = video.get_compatible_files(compatibility_level)
    else:
        flask.abort(500, "Incorrect srs file or parsing error")
    print("video_stream", video_stream)
    compatible_audio_streams = []
    if audio_streams is not None:
        for _as in audio_streams:
            compatible_audio_streams.append(
                _as.get_compatible_files(compatibility_level)
            )
        print("audio streams", compatible_audio_streams)
        return video_stream, compatible_audio_streams
    else:
        return video_stream, None


def generate_tempfile_id():
    global tempfile_id
    population = string.ascii_letters + string.digits
    tempfile_id = "".join(random.choices(population, k=64))
    return tempfile_id


@srs_video_blueprint.route(
    "/multiplex/mlid<int:content_id>", defaults={"pathstr": None}
)
@srs_video_blueprint.route(
    "/multiplex/file/<string:pathstr>", defaults={"content_id": None}
)
@shared_code.login_validation
def srs_multiplexing(pathstr: str | None, content_id: int | None):
    global file_mimetype
    global multiplexed_file
    global manifest_filename
    path = get_manifest_file(pathstr, content_id)
    manifest_filename = path.name
    path_parent_dir = path.parent
    compatibility_level = int(
        flask.request.args.get(
            "compatibility_level",
            flask.session.get(
                "clevel", flask.request.cookies.get("clevel", 3)
            ),
        )
    )
    video_streams, audio_streams = extract_streams(path, compatibility_level)
    if audio_streams is None:
        video_stream_path = path_parent_dir.joinpath(video_streams[0])
        return shared_code.route_template.static_file(video_stream_path)
    else:
        video_file_path = path_parent_dir.joinpath(video_streams[0])
        audio_file_path = path_parent_dir.joinpath(audio_streams[0][0])
        file_id = generate_tempfile_id()
        if multiplexed_file is not None:
            multiplexed_file.close()
            multiplexed_file = None
        multiplexed_file = tempfile.NamedTemporaryFile()
        if video_file_path.suffix == ".webm" and audio_file_path.suffix in {
            ".oga",
            ".opus",
        }:
            _format = "webm"
            file_mimetype = "video/webm"
        else:
            _format = "mp4"
            file_mimetype = "video/mp4"
        commandline = [
            "ffmpeg",
            "-y",
            "-i",
            str(video_file_path),
            "-i",
            str(audio_file_path),
            "-c",
            "copy",
            "-f",
            _format,
            multiplexed_file.name,
        ]
        pyimglib.common.utils.run_subprocess(commandline, capture_out=False)
        return flask.redirect(f"/video/srs/file/{file_id}")
