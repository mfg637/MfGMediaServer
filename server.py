import hashlib

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

import decoders

image_file_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.webm', '.svg', '.mkv', '.mp4'}
supported_file_extensions = image_file_extensions.union({'.mp3', ".m4a", ".ogg", ".oga", ".opus", ".flac"})


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


def base64_to_str(base64code):
    return base64.b64decode(bytes.fromhex(base64code)).decode("utf-8")


def str_to_base64(string):
    return base64.b64encode(string.encode("utf-8")).hex()


def cache_check(path):
    src_hash = hashlib.sha3_256(path.read_bytes()).hexdigest()
    try:
        if flask.request.headers['If-None-Match'][1:-1] == src_hash:
            status_code = flask.Response(status=304)
            return src_hash, status_code
    except KeyError:
        pass
    return src_hash, None


def simplify_filename(name):
    return re.sub(r"[_-]", ' ', name)


@app.route('/')
def app_root():
    return browse(root_dir)


@app.route('/orig/<string:pathstr>')
def get_original(pathstr):
    path = pathlib.Path(base64_to_str(pathstr))
    print(flask.request.headers)
    if path.is_file():
        src_hash, status_code = cache_check(path)
        if status_code is not None:
            return status_code
        abspath = path.absolute()
        f = flask.send_from_directory(
            str(abspath.parent),
            str(abspath.name),
            add_etags=False,
            mimetype=magic.from_file(str(abspath), mime=True),
            conditional=True
        )
        f.set_etag(src_hash)
        return f
    else:
        flask.abort(404)


@app.route('/image/<string:format>/<string:pathstr>')
def transcode_image(format:str, pathstr):
    path = pathlib.Path(base64_to_str(pathstr))
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
        else:
            img.save(buffer, format="JPEG", quality=90)
            mime = "image/jpeg"
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
    path = pathlib.Path(base64_to_str(pathstr))
    if path.is_file():
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
        f.set_etag(src_hash)
        return f
    else:
        flask.abort(404)


def browse(dir):
    dirlist, filelist = browse_folder(dir)
    itemslist = list()
    if dir != root_dir:
        itemslist.append({
            "icon": flask.url_for('static', filename='images/updir_icon.svg'),
            "name": ".."
        })
        if dir.parent == root_dir:
            itemslist[0]["link"] = "/"
        else:
            itemslist[0]["link"] = "/browse/{}".format(dir.parent.relative_to(root_dir))

    for _dir in dirlist:
        itemslist.append(
            {
                "link": "/browse/{}".format(_dir.relative_to(root_dir)),
                "icon": flask.url_for('static', filename='images/folder icon.svg'),
                "object_icon": False,
                "name": simplify_filename(_dir.name)
            }
        )
        if _dir.joinpath(".imgview-dir-config.json").exists():
            itemslist[-1]["object_icon"] = True
            itemslist[-1]["icon"] = "/folder_icon_paint/{}".format(_dir.relative_to(root_dir))
    for file in filelist:
        base64path = str_to_base64(str(file.relative_to(root_dir)))
        itemslist.append(
            {
                "link": "/orig/{}".format(base64path),
                "icon": None,
                "object_icon": False,
                "name": simplify_filename(file.name)
            }
        )
        if file.suffix.lower() in image_file_extensions:
            itemslist[-1]['icon'] = "/thumbnail/webp/192x144/{}".format(base64path)
        if file.suffix == '.mkv':
            itemslist[-1]['link'] = "/videostream_vp8/{}".format(base64path)
        if file.suffix.lower() in {'.jpg', '.jpeg'}:
            jpg = decoders.jpeg.JPEGDecoder(file)
            try:
                if (jpg.arithmetic_coding()):
                    itemslist[-1]['link'] = "/image/webp/{}".format((base64path))
            except ValueError:
                itemslist[-1]['link'] = "/image/webp/{}".format((base64path))
    title = ''
    if dir == root_dir:
        title = "root"
    else:
        title = dir.name
    return flask.render_template('index.html', title=title, itemslist=itemslist)

@app.route('/browse/<path:pathstr>')
def browse_dir(pathstr):
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
    else:
        flask.abort(404)

@app.route('/helloword')
def hello_world():
    return 'Hello, World!'


@app.route('/videostream_vp8/<string:pathstr>')
def ffmpeg_vp8_simplestream(pathstr):
    import subprocess
    path = pathlib.Path(base64_to_str(pathstr))
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
        commandline = [
                'ffmpeg',
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
    import static.images.folder_icon_painter as folder_icon_painter
    import json
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
            str_to_base64(str(thumbnail_path.relative_to(root_dir)))
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


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=3709)