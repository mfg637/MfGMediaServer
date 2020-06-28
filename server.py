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

import decoders

image_file_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.webm', '.svg', '.mkv', '.mp4'}


def browse_folder(folder):
    path_dir_objects = []
    path_file_objects = []
    for entry in folder.iterdir():
        if entry.is_file() and entry.suffix.lower() in image_file_extensions:
            path_file_objects.append(entry)
        elif entry.is_dir() and entry.name[0] != '.':
            path_dir_objects.append(entry)
    return path_dir_objects, path_file_objects


app = flask.Flask(__name__)

if len(sys.argv)>1:
    os.chdir(sys.argv[1])

root_dir = pathlib.Path('.').absolute()


def header(title):
    head = ('<!DOCTYPE html>\n'
            '<html>\n'
            '   <head>\n'
            '   <meta charset="utf-8"/>\n'
            '   <title>{}</title>\n'
            '   </head>\n'
            '   <body>\n').format(title)
    return head


def footer():
    foo = ('    </body>\n'
           '</html>\n')
    return foo


def base64_to_str(base64code):
    return base64.b64decode(bytes.fromhex(base64code)).decode("utf-8")


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
    if path.is_file():
        src_hash, status_code = cache_check(path)
        if status_code is not None:
            return status_code
        abspath = str(path.absolute())
        f = flask.send_file(abspath, add_etags=False, mimetype=magic.from_file(abspath, mime=True))
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
                "name": simplify_filename(_dir.name)
            }
        )
    for file in filelist:
        base64path = base64.b64encode(str(file.relative_to(root_dir)).encode("utf-8")).hex()
        itemslist.append(
            {
                "link": "/orig/{}".format(base64path),
                "icon": "/thumbnail/webp/192x144/{}".format(base64path),
                "name": simplify_filename(file.name)
            }
        )
    title = ''
    if dir == root_dir:
        title = "root"
    else:
        title = dir.name
    return flask.render_template('index.html', title=title, itemslist=itemslist)

@app.route('/browse/<path:pathstr>')
def browse_dir(pathstr):
    print(root_dir)
    path = pathlib.Path(pathstr).absolute()
    if pathlib.Path(path).is_dir():
        in_root_dir = False
        for parent in path.parents:
            print(parent)
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

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=3709)