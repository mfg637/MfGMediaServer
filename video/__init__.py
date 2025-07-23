import abc
import json
import logging
import pathlib
import subprocess
import flask
import pyimglib
import pyimglib.common
import shared_code
import xml.dom.minidom


logger = logging.getLogger(__name__)


def mpd_processing(mpd_file: pathlib.Path):
    subs_file = mpd_file.with_suffix(".mpd.subs")
    logger.debug("subs file: {} ({})".format(subs_file, subs_file.exists()))
    if subs_file.exists():
        mpd_document: xml.dom.minidom.Document = xml.dom.minidom.parse(
            str(mpd_file)
        )
        period: xml.dom.minidom.Element = mpd_document.getElementsByTagName(
            "Period"
        )[0]
        with subs_file.open() as f:
            subs = json.load(f)
            for subtitle in subs:
                last_repr_id = int(
                    mpd_document.getElementsByTagName("Representation")[
                        -1
                    ].getAttribute("id")
                )
                if "webvtt" in subtitle:
                    _as: xml.dom.minidom.Element = mpd_document.createElement(
                        "AdaptationSet"
                    )
                    _as.setAttribute("mimeType", "text/vtt")
                    _as.setAttribute("lang", subtitle["lang2"])

                    _repr: xml.dom.minidom.Element = (
                        mpd_document.createElement("Representation")
                    )
                    _repr.setAttribute("id", str(last_repr_id + 1))
                    _repr.setAttribute("bandwidth", "123")

                    url: xml.dom.minidom.Element = mpd_document.createElement(
                        "BaseURL"
                    )
                    url_text_node = mpd_document.createTextNode(
                        subtitle["webvtt"]
                    )

                    url.appendChild(url_text_node)
                    _repr.appendChild(url)
                    _as.appendChild(_repr)

                    period.appendChild(_as)
        return flask.Response(
            mpd_document.toprettyxml(), mimetype="application/dash+xml"
        )
    else:
        return shared_code.route_template.static_file(mpd_file)


class VideoTranscoder(abc.ABC):
    def __init__(self):
        self._buffer = None
        self._io = None
        self.process = None

    @abc.abstractmethod
    def get_specific_commandline_part(self, path, fps) -> list[str]:
        pass

    @abc.abstractmethod
    def get_output_buffer(self):
        pass

    @abc.abstractmethod
    def read_input_from_pipe(self, pipe_output):
        pass

    @abc.abstractmethod
    def get_mimetype(self):
        pass

    def do_convert(self, pathstr):
        def body(path):
            data = pyimglib.common.ffmpeg.probe(path)
            video = None
            for stream in data["streams"]:
                if stream["codec_type"] == "video" and (
                    video is None or stream["disposition"]["default"] == 1
                ):
                    video = stream
            fps = None
            if video["avg_frame_rate"] == "0/0":
                fps = eval(video["r_frame_rate"])
            else:
                fps = eval(video["avg_frame_rate"])
            seek_position = flask.request.args.get("seek", None)
            commandline = [
                "ffmpeg",
            ]
            if seek_position is not None:
                commandline += ["-ss", seek_position]
            commandline += self.get_specific_commandline_part(path, fps)
            self.process = subprocess.Popen(
                commandline, stdout=subprocess.PIPE
            )
            self.read_input_from_pipe(self.process.stdout)
            f = flask.send_file(
                self.get_output_buffer(),
                etag=False,
                mimetype=self.get_mimetype(),
            )
            return f

        return shared_code.route_template.file_url_template(body, pathstr)


class VP8_VideoTranscoder(VideoTranscoder):
    def __init__(self):
        super().__init__()
        self._encoder = "libvpx"

    def get_mimetype(self):
        return "video/webm"

    def read_input_from_pipe(self, pipe_output):
        self._io = pipe_output

    def get_specific_commandline_part(self, path, fps):
        width = flask.request.args.get("width", 1440)
        height = flask.request.args.get("height", 720)
        return [
            "-i",
            str(path),
            "-vf",
            "scale='min({},iw)':'min({}, ih)'".format(width, height)
            + ":force_original_aspect_ratio=decrease"
            + (",fps={}".format(fps / 2) if fps > 30 else ""),
            "-deadline",
            "realtime",
            "-cpu-used",
            "5",
            "-vcodec",
            self._encoder,
            "-crf",
            "10",
            "-b:v",
            "8M",
            "-ac",
            "2",
            "-acodec",
            "libopus",
            "-b:a",
            "144k",
            "-f",
            "webm",
            "-",
        ]

    def get_output_buffer(self):
        return self._io


class VP9_VideoTranscoder(VP8_VideoTranscoder):
    def __init__(self):
        super().__init__()
        self._encoder = "libvpx-vp9"


video_blueprint = flask.Blueprint("video", __name__, url_prefix="/video")


@video_blueprint.route("/vp8/<string:pathstr>")
@shared_code.login_validation
def ffmpeg_vp8_simplestream(pathstr):
    vp8_converter = VP8_VideoTranscoder()
    return vp8_converter.do_convert(pathstr)


@video_blueprint.route("/vp9/<string:pathstr>")
@shared_code.login_validation
def ffmpeg_vp9_simplestream(pathstr):
    vp9_converter = VP9_VideoTranscoder()
    return vp9_converter.do_convert(pathstr)


@video_blueprint.route("/ffprobe_json/<string:pathstr>")
@shared_code.login_validation
def ffprobe_response(pathstr):
    path = pathlib.Path(shared_code.route_template.base32_to_str(pathstr))
    if path.is_file():
        return flask.Response(
            pyimglib.common.ffmpeg.probe(path), mimetype="application/json"
        )
    else:
        flask.abort(404)
