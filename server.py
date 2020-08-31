#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import hashlib

import json
import flask
import sys
import os
import pathlib
import io
import PIL.Image
import base64
import magic
import re
import ffmpeg
import urllib.parse

import decoders


anonymous_forbidden = True
access_tokens = dict()
# key - URL, value - token

image_file_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg'}
video_file_extensions = {'.mkv', '.mp4', '.webm'}
supported_file_extensions = \
    image_file_extensions.union(video_file_extensions)\
    .union({'.mp3', ".m4a", ".ogg", ".oga", ".opus", ".flac", ".m3u8"})\
    .union({'.mpd'})# dash manifest


def browse_folder(folder):
    path_dir_objects = []
    path_file_objects = []
    for entry in folder.iterdir():
        if entry.is_file() and entry.suffix.lower() in supported_file_extensions:
            path_file_objects.append(entry)
        elif entry.is_dir() and entry.name[0] != '.':
            path_dir_objects.append(entry)
    return path_dir_objects, path_file_objects


app = flask.Flask(__name__)

if len(sys.argv)>1:
    os.chdir(sys.argv[1])

root_dir = pathlib.Path('.').absolute()


def base32_to_str(base32code: str):
    return base64.b32decode(base32code.encode("utf-8")).decode("utf-8")


def str_to_base32(string: str):
    return base64.b32encode(string.encode("utf-8")).decode("utf-8")


def cache_check(path):
    hash = hashlib.sha3_256()
    with path.open('br') as f:
        buffer = f.read(1024)
        while len(buffer)>0:
            hash.update(buffer)
            buffer = f.read(1024*1024)
    src_hash = hash.hexdigest()
    try:
        if flask.request.headers['If-None-Match'][1:-1] == src_hash:
            status_code = flask.Response(status=304)
            return src_hash, status_code
    except KeyError:
        pass
    return src_hash, None


def simplify_filename(name):
    return re.sub(r"[_-]", ' ', name)


def login_validation():
    access_token = flask.request.args.get("access_token", None)
    if access_token is not None:
        if access_token == access_tokens[urllib.parse.unquote(flask.request.base_url)]:
            return
    if anonymous_forbidden and not flask.session.get('logged_in'):
        flask.abort(401)


@app.route('/')
def app_root():
    login_validation()
    return browse(root_dir)


def static_file(path, mimetype=None):
    login_validation()
    abspath = path.absolute()
    if mimetype is None:
        mimetype = magic.from_file(str(abspath), mime=True)
        if path.suffix == '.mpd' and mimetype == "text/xml":
            mimetype = "application/dash+xml"
    f = flask.send_from_directory(
        str(abspath.parent),
        str(abspath.name),
        add_etags=False,
        mimetype=mimetype,
        conditional=True
    )
    return f


@app.route('/orig/<string:pathstr>')
def get_original(pathstr):
    login_validation()
    path = pathlib.Path(base32_to_str(pathstr))
    if path.is_file():
        return static_file(path)
    else:
        flask.abort(404)


@app.route('/image/<string:format>/<string:pathstr>')
def transcode_image(format:str, pathstr):
    login_validation()
    path = pathlib.Path(base32_to_str(pathstr))
    if path.is_file():
        src_hash, status_code = cache_check(path)
        if status_code is not None:
            return status_code
        img = decoders.open_image(path)
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
            cache_timeout=24*60*60,
            last_modified=path.stat().st_mtime,
        )
        f.set_etag(src_hash)
        return f
    else:
        flask.abort(404)


@app.route('/thumbnail/<string:format>/<int:width>x<int:height>/<string:pathstr>')
def gen_thumbnail(format:str, width, height, pathstr):
    login_validation()
    path = pathlib.Path(base32_to_str(pathstr))
    if path.is_file():
        src_hash, status_code = None, None
        if path.stat().st_size<(1024*1024*1024):
            src_hash, status_code = cache_check(path)
        if status_code is not None:
            return status_code
        img = decoders.open_image(path)
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
            cache_timeout=24*60*60,
            last_modified=path.stat().st_mtime,
        )
        if src_hash is not None:
            f.set_etag(src_hash)
        return f
    else:
        flask.abort(404)


def extract_mtime_key(file: pathlib.Path):
    return file.stat().st_mtime


def browse(dir):
    dirlist, filelist = [], []
    itemslist = list()
    filemeta_list = list()
    items_count: int = 0
    def _icon(file, filemeta):
        filemeta["lazy_load"] = True
        icon_base32path = filemeta['base32path']
        icon_path = pathlib.Path("{}.icon".format(file))
        if icon_path.exists():
            filemeta["custom_icon"] = True
            icon_base32path = str_to_base32(str(icon_path.relative_to(root_dir)))
        filemeta['icon'] = "/thumbnail/jpeg/192x144/{}".format(icon_base32path)
        filemeta['sources'] = (
            "/thumbnail/webp/192x144/{}".format(icon_base32path) +
            ", /thumbnail/webp/384x288/{} 2x".format(icon_base32path) +
            ", /thumbnail/webp/768x576/{} 4x".format(icon_base32path),
            "/thumbnail/jpeg/192x144/{}".format(icon_base32path) +
            ", /thumbnail/jpeg/384x288/{} 2x".format(icon_base32path) +
            ", /thumbnail/jpeg/768x576/{} 4x".format(icon_base32path),
        )
    glob_pattern = flask.request.args.get('glob', None)
    if glob_pattern is None:
        dirlist, filelist = browse_folder(dir)
        if dir != root_dir:
            itemslist.append({
                "icon": flask.url_for('static', filename='images/updir_icon.svg'),
                "name": "..",
                "lazy_load": False,
            })
            if dir.parent == root_dir:
                itemslist[0]["link"] = "/"
            else:
                itemslist[0]["link"] = "/browse/{}".format(dir.parent.relative_to(root_dir))
            items_count += 1
        for _dir in dirlist:
            itemslist.append(
                {
                    "link": "/browse/{}".format(_dir.relative_to(root_dir)),
                    "icon": flask.url_for('static', filename='images/folder icon.svg'),
                    "object_icon": False,
                    "name": simplify_filename(_dir.name),
                    "sources": None,
                    "lazy_load": False,
                }
            )
            try:
                if _dir.joinpath(".imgview-dir-config.json").exists():
                    itemslist[-1]["object_icon"] = True
                    itemslist[-1]["icon"] = "/folder_icon_paint/{}".format(_dir.relative_to(root_dir))
            except PermissionError:
                pass
            items_count += 1
    else:
        itemslist.append({
            "icon": flask.url_for('static', filename='images/updir_icon.svg'),
            "name": ".",
            "lazy_load": False,
            "link": flask.request.path
        })
        items_count += 1
        for file in dir.glob(glob_pattern):
            if file.is_file() and file.suffix.lower() in supported_file_extensions:
                filelist.append(file)
        filelist.sort(key=extract_mtime_key, reverse=True)
    for file in filelist:
        base32path = str_to_base32(str(file.relative_to(root_dir)))
        filemeta = {
                "link": "/orig/{}".format(base32path),
                "icon": None,
                "object_icon": False,
                "name": simplify_filename(file.name),
                "sources": None,
                "base32path": base32path,
                "item_index": items_count,
                "lazy_load": False,
                "type": "audio",
                "is_vp8": False,
                "suffix": file.suffix,
                "custom_icon": False
            }
        icon_path = pathlib.Path("{}.icon".format(file))
        if (file.suffix.lower() in image_file_extensions) or (file.suffix.lower() in video_file_extensions):
            _icon(file, filemeta)
        if file.suffix.lower() in image_file_extensions:
            filemeta["type"] = "picture"
        elif file.suffix.lower() in video_file_extensions:
            filemeta["type"] = "video"
        elif file.suffix.lower() == '.mpd':
            filemeta['type'] = "DASH"
            filemeta['link'] = "{}/{}".format(flask.request.base_url, file.name)
            if icon_path.exists():
                _icon(file, filemeta)
        elif file.suffix.lower() == ".m3u8":
            access_token = gen_access_token()
            filemeta['link'] = "https://{}:{}/m3u8/{}.m3u8".format(config.host_name, config.port, base32path)
            access_tokens[filemeta['link']] = access_token
            filemeta['link'] += "?access_token={}".format(access_token)
            if icon_path.exists():
                _icon(file, filemeta)
        if file.suffix == '.mkv':
            filemeta['link'] = "/vp8/{}".format(base32path)
            filemeta["is_vp8"] = True
        elif file.suffix.lower() in {'.jpg', '.jpeg'}:
            try:
                jpg = decoders.jpeg.JPEGDecoder(file)
                if (jpg.arithmetic_coding()):
                    filemeta['link'] = "/image/webp/{}".format((base32path))
            except Exception:
                filemeta['link'] = "/image/webp/{}".format((base32path))
        itemslist.append(filemeta)
        filemeta_list.append(filemeta)
        items_count += 1
    title = ''
    if dir == root_dir:
        title = "root"
    else:
        title = dir.name
    return flask.render_template('index.html', title=title, itemslist=itemslist, filemeta=json.dumps(filemeta_list))


@app.route('/browse/<path:pathstr>')
def browse_dir(pathstr):
    login_validation()
    path = pathlib.Path(pathstr).absolute()
    if pathlib.Path(path).is_dir():
        in_root_dir = False
        for parent in path.parents:
            if parent == root_dir:
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


@app.route('/vp8/<string:pathstr>')
def ffmpeg_vp8_simplestream(pathstr):
    login_validation()
    import subprocess
    path = pathlib.Path(base32_to_str(pathstr))
    if path.is_file():
        data = ffmpeg.probe(path)
        video = None
        for stream in data['streams']:
            if stream['codec_type'] == "video":
                video = stream
        fps=None
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
        commandline += [
                '-i', str(path),
                '-vf',
                'scale=\'min(1440,iw)\':\'min(720, ih)\':force_original_aspect_ratio=decrease'+\
                (",fps={}".format(fps/2) if fps>30 else ""),
                '-deadline', 'realtime',
                '-vcodec', 'libvpx',
                '-crf', '10',
                '-b:v', '8M',
                '-ac', '2',
                '-acodec', 'libopus',
                '-b:a', '144k',
                '-f', 'webm',
                '-'
            ]
        process = subprocess.Popen(
            commandline
            , stdout=subprocess.PIPE
        )
        f = flask.send_file(process.stdout, add_etags=False, mimetype="video/webm")
        return f
    else:
        flask.abort(404)


@app.route('/folder_icon_paint/<path:pathstr>')
def icon_paint(pathstr):
    login_validation()
    import static.images.folder_icon_painter as folder_icon_painter
    dir=pathlib.Path(pathstr).absolute()
    data = None
    with dir.joinpath(".imgview-dir-config.json").open("r") as f:
        data = json.load(f)
    rendered_template = None
    if data['cover'] is not None:
        thumbnail_path = dir.joinpath(data['cover'])
        base_size = (174, 108)
        img = decoders.open_image(thumbnail_path, base_size)
        thumb_ratio = base_size[0]/base_size[1]
        src_ratio = img.size[0]/img.size[1]
        width, height = 0, 0
        if src_ratio>thumb_ratio:
            width = base_size[0]
            height = base_size[0]/src_ratio
        else:
            width = base_size[1]*src_ratio
            height = base_size[1]
        base_offset = (10, 30)
        xoffset = (base_size[0] - width) // 2 + base_offset[0]
        yoffset = (base_size[1] - height) // 2 + base_offset[1]
        img_url = "/thumbnail/webp/174x108/{}".format(
            str_to_base32(str(thumbnail_path.relative_to(root_dir)))
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


def gen_access_token():
    import random
    import string
    access_token = ""
    for i in random.choices(string.ascii_letters + string.digits, k=64):
        access_token += i
    return access_token


@app.route('/m3u8/<string:pathstr>.m3u8')
def gen_m3u8(pathstr):
    global access_tokens
    login_validation()
    path = pathlib.Path(base32_to_str(pathstr))
    if path.is_file():
        buffer = io.StringIO()
        with path.open("r") as f:
            for line in f:
                if '#' in line:
                    buffer.write(line)
                else:
                    base32path = str_to_base32(str(path.parent.joinpath(line)).rstrip())
                    base_url = "https://{}:{}/orig/{}".format(
                        config.host_name,
                        config.port,
                        base32path
                    )
                    access_token = gen_access_token()
                    access_tokens[base_url] = access_token
                    buffer.write(base_url+"?access_token={}\n".format(access_token))
        return flask.Response(buffer.getvalue(), mimetype="audio/x-mpegurl", status=200)
    else:
        flask.abort(404)


@app.route('/<path:pathstr>')
def root_open_file(pathstr):
    login_validation()
    path = pathlib.Path(pathstr).absolute()
    if pathlib.Path(path).is_file():
        return static_file(path)
    else:
        flask.abort(404)


@app.route('/ffprobe_json/<string:pathstr>')
def ffprobe_response(pathstr):
    login_validation()
    path = pathlib.Path(base32_to_str(pathstr))
    print(flask.request.headers)
    if path.is_file():
        return flask.Response(ffmpeg.probe_raw(path), mimetype="application/json")
    else:
        flask.abort(404)


@app.route('/webvtt/<string:pathstr>')
def get_vtt_subs(pathstr):
    login_validation()
    path = pathlib.Path(base32_to_str(pathstr)+".vtt")
    if path.is_file():
        return static_file(path, mimetype="text/vtt")
    else:
        flask.abort(404)


@app.errorhandler(401)
def show_login_form(event):
    f = flask.render_template('login.html', redirect_to=str(flask.request.base_url))
    return flask.Response(f, status=401)


@app.route('/login', methods=['POST'])
def login_handler():
    import hashlib
    import config
    if hashlib.sha3_512(flask.request.form['password'].encode("utf-8")).hexdigest() == \
            config.valid_password_hash_hex and \
            flask.request.form['login'] == config.valid_login:
        flask.session['logged_in'] = True
        return flask.redirect(flask.request.form['redirect_to'])
    else:
        flask.abort(401)


if __name__ == '__main__':
    import config
    ssl_context = None
    if len(config.certificate_file) and len(config.private_key_file):
        cert_path = os.path.join(app.root_path, config.certificate_file)
        key_path = os.path.join(app.root_path, config.private_key_file)
        if os.path.exists(cert_path) and os.path.exists(key_path):
            ssl_context=(cert_path, key_path)
    port = config.port
    i=2
    while i<len(sys.argv):
        if sys.argv[i] == '--port':
            i += 1
            port = sys.argv[i]
        elif sys.argv[i] == '--anon':
            anonymous_forbidden = False
        i += 1
    app.secret_key = os.urandom(12)
    app.run(host=config.host_name, port=port, ssl_context=ssl_context)