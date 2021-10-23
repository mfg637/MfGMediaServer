#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import subprocess
import tempfile
import abc

import flask
import os
import pathlib
import io
import PIL.Image
import filesystem
import magic

import pyimglib
import pyimglib.decoders.ffmpeg
import shared_code
import ACLMMP

from filesystem.browse import browse


tmp_file = tempfile.NamedTemporaryFile()


app = flask.Flask(__name__)


@app.route('/')
def app_root():
    shared_code.login_validation()
    return browse(shared_code.root_dir)


def static_file(path, mimetype=None):
    shared_code.login_validation()
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
    shared_code.login_validation()
    path = pathlib.Path(shared_code.base32_to_str(pathstr))
    if path.is_file():
        return body(path, **kwargs)
    else:
        flask.abort(404)


@app.route('/orig/<string:pathstr>')
def get_original(pathstr):
    def body(path):
        if pyimglib.decoders.avif.is_avif(path):
            return static_file(path, "image/avif")
        return static_file(path)
    return file_url_template(body, pathstr)


@app.route('/image/<string:format>/<string:pathstr>')
def transcode_image(format: str, pathstr):
    def body(path, format):
        src_hash, status_code = shared_code.cache_check(path)
        if status_code is not None:
            return status_code
        img = pyimglib.decoders.open_image(path)
        if isinstance(img, pyimglib.decoders.srs.ClImage):
            lods = img.progressive_lods()
            current_lod = lods.pop(0)
            current_lod_img = pyimglib.decoders.open_image(current_lod)
            while len(lods):
                if isinstance(current_lod_img, pyimglib.decoders.frames_stream.FramesStream):
                    current_lod_img = current_lod_img.next_frame()
                if current_lod_img.format != format.upper():
                    current_lod = lods.pop()
                    current_lod_img.close()
                    current_lod_img = pyimglib.decoders.open_image(current_lod)
                else:
                    break
            if current_lod_img.format == format.upper():
                base32path = shared_code.str_to_base32(str(current_lod))
                return flask.redirect(
                    "https://{}:{}/orig/{}".format(
                        config.host_name,
                        config.port,
                        base32path
                    )
                )
            else:
                img = current_lod_img
        if isinstance(img, pyimglib.decoders.frames_stream.FramesStream):
            _img = img.next_frame()
            img.close()
            img = _img
        img = img.convert(mode='RGBA')
        buffer = io.BytesIO()
        mime = ''
        if format.lower() == 'webp':
            img.save(buffer, format="WEBP", quality=90, method=4, lossless=False)
            mime = "image/webp"
        elif format.lower() == 'jpeg':
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
        f.set_etag(src_hash)
        return f
    return file_url_template(body, pathstr, format=format)


@app.route('/thumbnail/<string:format>/<int:width>x<int:height>/<string:pathstr>')
def gen_thumbnail(format: str, width, height, pathstr):
    def body(path, format, width, height):
        allow_origin = bool(flask.request.args.get('allow_origin', False))
        src_hash, status_code = None, None
        if path.stat().st_size < (1024 * 1024 * 1024):
            src_hash, status_code = shared_code.cache_check(path)
        if status_code is not None:
            return status_code
        img = pyimglib.decoders.open_image(path)
        if isinstance(img, pyimglib.decoders.srs.ClImage):
            lods = img.progressive_lods()
            current_lod = lods.pop(0)
            current_lod_img = pyimglib.decoders.open_image(current_lod)
            while len(lods):
                if isinstance(current_lod_img, pyimglib.decoders.frames_stream.FramesStream):
                    current_lod_img = current_lod_img.next_frame()
                if current_lod_img.width < width and current_lod_img.height < height:
                    current_lod = lods.pop()
                    print("CURRENT_LOD", current_lod)
                    current_lod_img.close()
                    current_lod_img = pyimglib.decoders.open_image(current_lod)
                else:
                    break
            if current_lod_img.format == "WEBP" and allow_origin:
                base32path = shared_code.str_to_base32(str(current_lod))
                return flask.redirect(
                    "https://{}:{}/orig/{}".format(
                        config.host_name,
                        config.port,
                        base32path
                    )
                )
            else:
                img = current_lod_img
        if isinstance(img, pyimglib.decoders.frames_stream.FramesStream):
            _img = img.next_frame()
            img.close()
            img = _img
        if allow_origin and img.format == "WEBP" and (img.is_animated or (img.width <= width and img.height <= height)):
            return flask.redirect(
                "https://{}:{}/orig/{}".format(
                    config.host_name,
                    config.port,
                    pathstr
                )
            )
        img = img.convert(mode='RGBA')
        img.thumbnail((width, height), PIL.Image.LANCZOS)
        buffer = io.BytesIO()
        mime = ''
        if format.lower() == 'webp':
            img.save(buffer, format="WEBP", quality=90, method=4, lossless=False)
            mime = "image/webp"
        else:
            img = img.convert(mode='RGB')
            img.save(buffer, format="JPEG", quality=90)
            mime = "image/jpeg"
        img.close()
        buffer.seek(0)
        f = flask.send_file(
            buffer,
            mimetype=mime,
            max_age=24 * 60 * 60,
            last_modified=path.stat().st_mtime,
        )
        if src_hash is not None:
            f.set_etag(src_hash)
        return f
    return file_url_template(body, pathstr, format=format, width=width, height=height)


@app.route('/browse/<path:pathstr>')
def browse_dir(pathstr):
    shared_code.login_validation()
    path = pathlib.Path(pathstr).absolute()
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
        return static_file(path)
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
def ffmpeg_vp8_simplestream(pathstr):
    vp8_converter = VP8_VideoTranscoder()
    return vp8_converter.do_convert(pathstr)


@app.route('/vp9/<string:pathstr>')
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
def ffmpeg_nvenc_filestream(pathstr):
    nvenc_converter = NVENC_VideoTranscoder()
    return nvenc_converter.do_convert(pathstr)


@app.route('/aclmmp_webm/<string:pathstr>')
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
        print(minimal_content_compatibility_level, LEVEL, minimal_content_compatibility_level > LEVEL)
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
def icon_paint(pathstr):
    shared_code.login_validation()
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
def gen_m3u8(pathstr):
    shared_code.login_validation()
    path = pathlib.Path(shared_code.base32_to_str(pathstr))
    if path.is_file():
        buffer = io.StringIO()
        with path.open("r") as f:
            for line in f:
                if '#' in line:
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
def root_open_file(pathstr):
    shared_code.login_validation()
    path = pathlib.Path(pathstr).absolute()
    if pathlib.Path(path).is_file():
        return static_file(path)
    else:
        flask.abort(404)


@app.route('/ffprobe_json/<string:pathstr>')
def ffprobe_response(pathstr):
    shared_code.login_validation()
    path = pathlib.Path(shared_code.base32_to_str(pathstr))
    if path.is_file():
        return flask.Response(pyimglib.decoders.ffmpeg.probe(path), mimetype="application/json")
    else:
        flask.abort(404)


@app.route('/webvtt/<string:pathstr>')
def get_vtt_subs(pathstr):
    shared_code.login_validation()
    path = pathlib.Path(shared_code.base32_to_str(pathstr) + ".vtt")
    if path.is_file():
        return static_file(path, mimetype="text/vtt")
    else:
        flask.abort(404)


@app.errorhandler(401)
def show_login_form(event):
    f = None
    if 'redirect_to' in flask.request.form:
        f = flask.render_template('login.html', redirect_to=str(flask.request.form['redirect_to']))
    else:
        f = flask.render_template('login.html', redirect_to=str(flask.request.url))
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
        return flask.redirect(flask.request.form['redirect_to'])
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
    filesystem.browse.load_acceleration = config.load_acceleration_method
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
