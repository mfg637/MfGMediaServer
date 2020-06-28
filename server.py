import hashlib

import flask
import sys
import os
import pathlib
import io
import PIL.Image
import base64

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


@app.route('/')
def app_root():
    return browse(root_dir)


@app.route('/thumbnail/<string:format>/<int:width>x<int:height>/<path:pathstr>')
def gen_thumbnail(format:str, width, height, pathstr):
    path = pathlib.Path(base64.b64decode(bytes.fromhex(pathstr)).decode("utf-8"))
    print(path)
    if path.is_file():
        src_hash = hashlib.sha3_256(path.read_bytes()).hexdigest()
        try:
            if flask.request.headers['If-None-Match'][1:-1] == src_hash:
                status_code = flask.Response(status=304)
                return status_code
        except KeyError:
            pass
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
            add_etags=src_hash,
            cache_timeout=24*60*60,
            last_modified=path.stat().st_mtime,
        )
        f.set_etag(src_hash)
        return f
    else:
        flask.abort(404)


def browse(dir):
    dirlist, filelist = browse_folder(dir)
    buffer = io.StringIO('')
    if dir == root_dir:
        buffer.write(header("root"))
    else:
        buffer.write((header(dir.name)))
    if dir != root_dir:
        buffer.write("<p>")
        if dir.parent == root_dir:
            buffer.write("<a href=\"/\">")
        else:
            buffer.write("<a href=\"/browse/{}\">".format(dir.parent.relative_to(root_dir)))
        buffer.write('..')
        buffer.write("</a>")
        buffer.write("</p>\n")
    for file in dir.iterdir():
        buffer.write("<p>")
        if file.is_dir():
            buffer.write("<a href=\"/browse/{}\">".format(file.relative_to(root_dir)))
        if file.is_file() and file.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp', '.svg'}:
            buffer.write("<img src=\"/thumbnail/webp/192x144/{}\" />".format(
                base64.b64encode(str(file.relative_to(root_dir)).encode("utf-8")).hex()
            ))
        elif file.is_dir():
            buffer.write("<img src=\"{}\" />".format(flask.url_for('static', filename='images/folder icon.svg')))
        buffer.write(str(file.name))
        if file.is_dir():
            buffer.write("</a>")
        buffer.write("</p>\n")
    buffer.write(footer())
    return buffer.getvalue()

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