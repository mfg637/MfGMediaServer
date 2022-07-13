import flask
import json
import pathlib

import shared_code
import shared_code.enums as shared_enums
import pyimglib
import config

load_acceleration = shared_enums.LoadAcceleration.NONE

items_per_page = 1


class PageCache:
    def __init__(self, path, cache, glob_pattern):
        self._path = path
        self._cache = cache
        self._glob_pattern = glob_pattern

    def is_cached(self, path, glob_pattern):
        return path == self._path and glob_pattern == self._glob_pattern

    def get_cache(self, path, glob_pattern):
        if self.is_cached(path, glob_pattern):
            return self._cache
        else:
            return list(), list(), list()


page_cache = PageCache(None, None, None)

image_file_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.avif', '.jxl'}
video_file_extensions = {'.mkv', '.mp4', '.webm'}
audio_file_extensions = {'.mp3', ".m4a", ".ogg", ".oga", ".opus", ".flac"}
supported_file_extensions = \
    image_file_extensions.union(video_file_extensions).union(audio_file_extensions)\
        .union({'.mpd', '.srs', ".m3u8"})


def browse_folder(folder):
    path_dir_objects = []
    path_file_objects = []
    path_srs_objects = []
    for entry in folder.iterdir():
        if entry.is_file() and entry.suffix.lower() == '.srs':
            path_srs_objects.append(entry)
        elif entry.is_file() and entry.suffix.lower() in supported_file_extensions:
            path_file_objects.append(entry)
        elif entry.is_dir() and entry.name[0] != '.':
            path_dir_objects.append(entry)
    return path_dir_objects, path_file_objects, path_srs_objects


def extract_mtime_key(file: pathlib.Path):
    return file.stat().st_mtime


def browse(dir):
    global page_cache
    dirlist, filelist, srs_filelist = [], [], []
    glob_pattern = flask.request.args.get('glob', None)
    itemslist, dirmeta_list, filemeta_list = page_cache.get_cache(dir, glob_pattern)
    if len(itemslist) == 0:
        items_count: int = 0

        if glob_pattern is None:
            dirlist, filelist, srs_filelist = browse_folder(dir)
            if dir != shared_code.root_dir:
                itemslist.append({
                    "icon": flask.url_for('static', filename='images/updir_icon.svg'),
                    "name": "..",
                    "lazy_load": False,
                })
                if dir.parent == shared_code.root_dir:
                    itemslist[0]["link"] = "/"
                else:
                    itemslist[0]["link"] = "/browse/{}".format(dir.parent.relative_to(shared_code.root_dir))
                items_count += 1
            for _dir in dirlist:
                dirmeta = {
                    "link": "/browse/{}".format(_dir.relative_to(shared_code.root_dir)),
                    "icon": flask.url_for('static', filename='images/folder icon.svg'),
                    "object_icon": False,
                    "name": shared_code.simplify_filename(_dir.name),
                    "sources": None,
                    "lazy_load": False,
                    "item_index": items_count,
                    "type": "dir",
                }
                try:
                    if _dir.joinpath(".imgview-dir-config.json").exists():
                        dirmeta["object_icon"] = True
                        dirmeta["icon"] = "/folder_icon_paint/{}".format(_dir.relative_to(shared_code.root_dir))
                        if load_acceleration in {
                            shared_enums.LoadAcceleration.LAZY_LOAD,
                            shared_enums.LoadAcceleration.BOTH
                        }:
                            dirmeta["lazy_load"] = True
                            dirmeta_list.append(dirmeta)
                except PermissionError:
                    pass
                itemslist.append(dirmeta)
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
                if file.is_file() and file.suffix.lower() == ".srs":
                    srs_filelist.append(file)
                elif file.is_file() and file.suffix.lower() in supported_file_extensions:
                    filelist.append(file)
        excluded_filelist = []
        for srs_file in srs_filelist:
            f = srs_file.open('r')
            content, streams, cl_level = pyimglib.ACLMMP.srs_parser.parseJSON(f)
            f.close()
            excluded_filelist.extend(pyimglib.ACLMMP.srs_parser.get_files_list(srs_file, content, streams))
            filelist.append(srs_file)
        filelist.sort(key=extract_mtime_key, reverse=True)

        filemeta_list, items_count = files_processor(filelist, excluded_filelist, items_count)

        itemslist.extend(filemeta_list)
        page_cache = PageCache(dir, (itemslist, dirmeta_list, filemeta_list), glob_pattern)
    title = ''
    if dir == shared_code.root_dir:
        title = "root"
    else:
        title = dir.name
    template_kwargs = {
        'title': title,
        '_glob': glob_pattern,
        'url': flask.request.base_url,
        "args": "",
        "medialib_sorting": shared_code.get_medialib_sorting_constants_for_template(),
        'enable_external_scripts': shared_code.enable_external_scripts
    }
    if load_acceleration in {shared_enums.LoadAcceleration.NONE, shared_enums.LoadAcceleration.LAZY_LOAD}:
        return flask.render_template(
            'index.html',
            itemslist=itemslist,
            dirmeta=json.dumps(dirmeta_list),
            filemeta=json.dumps(filemeta_list),
            pagination=False,
            page=0,
            max_pages=0,
            **template_kwargs
        )
    else:
        import math
        page = int(flask.request.args.get('page', 0))
        max_pages = math.ceil(len(itemslist) / items_per_page)
        min_index = page * items_per_page
        max_index = min_index + items_per_page
        final_filemeta_list = list()
        final_dirmeta_list = list()

        calc_item_page_index(dirmeta_list, final_dirmeta_list, min_index, max_index)
        calc_item_page_index(filemeta_list, final_filemeta_list, min_index, max_index)
        return flask.render_template(
            'index.html',
            itemslist=itemslist[min_index:max_index],
            dirmeta=json.dumps(final_dirmeta_list),
            filemeta=json.dumps(final_filemeta_list),
            pagination=True,
            page=page,
            max_pages=max_pages,
            **template_kwargs
        )


def calc_item_page_index(item_list, output_list, min_index, max_index):
    for item in item_list:
        if min_index <= item["item_index"] < max_index:
            final_item = item.copy()
            final_item["item_index"] -= min_index
            output_list.append(final_item)
        elif item["item_index"] >= max_index:
            break


def files_processor(filelist, excluded_filelist, initial_item_count):
    items_count = initial_item_count
    filemeta_list = list()
    for file in filelist:
        if file not in excluded_filelist:

            filemeta_list.append(get_file_info(file, items_count))
            items_count += 1
    return filemeta_list, items_count


def get_file_info(file: pathlib.Path, items_count=0):

    def _icon(file, filemeta):
        filemeta["lazy_load"] = load_acceleration in {
            shared_enums.LoadAcceleration.LAZY_LOAD,
            shared_enums.LoadAcceleration.BOTH
        }
        icon_base32path = filemeta['base32path']
        icon_path = pathlib.Path("{}.icon".format(file))
        if icon_path.exists():
            filemeta["custom_icon"] = True
            icon_base32path = shared_code.str_to_base32(str(icon_path.relative_to(shared_code.root_dir)))
        filemeta['icon'] = "/thumbnail/jpeg/192x144/{}".format(icon_base32path)
        filemeta['sources'] = (
            "/thumbnail/webp/192x144/{}".format(icon_base32path) +
            ", /thumbnail/webp/384x288/{} 2x".format(icon_base32path) +
            ", /thumbnail/webp/768x576/{} 4x".format(icon_base32path),
            "/thumbnail/jpeg/192x144/{}".format(icon_base32path) +
            ", /thumbnail/jpeg/384x288/{} 2x".format(icon_base32path) +
            ", /thumbnail/jpeg/768x576/{} 4x".format(icon_base32path),
        )

    base32path = shared_code.str_to_base32(str(file))
    filemeta = {
        "link": "/orig/{}".format(base32path),
        "icon": None,
        "object_icon": False,
        "name": shared_code.simplify_filename(file.name),
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
        filemeta['link'] = "/{}{}".format(
            ('' if dir == shared_code.root_dir else 'browse/'),
            str(file.relative_to(shared_code.root_dir))
        )
        if icon_path.exists():
            _icon(file, filemeta)
    elif file.suffix.lower() == '.srs':
        TYPE = pyimglib.decoders.srs.type_detect(file)
        if TYPE == pyimglib.ACLMMP.srs_parser.MEDIA_TYPE.VIDEO or \
                TYPE == pyimglib.ACLMMP.srs_parser.MEDIA_TYPE.VIDEOLOOP:
            filemeta['type'] = "video"
            filemeta['link'] = "/aclmmp_webm/{}".format(base32path)
        elif TYPE == pyimglib.ACLMMP.srs_parser.MEDIA_TYPE.IMAGE:
            filemeta['type'] = "picture"
            filemeta['link'] = "/image/autodetect/{}".format(base32path)
        _icon(file, filemeta)
    elif file.suffix.lower() == ".m3u8":
        access_token = shared_code.gen_access_token()
        filemeta['link'] = "https://{}:{}/m3u8/{}.m3u8".format(config.host_name, config.port, base32path)
        shared_code.access_tokens[filemeta['link']] = access_token
        filemeta['link'] += "?access_token={}".format(access_token)
        if icon_path.exists():
            _icon(file, filemeta)
    if file.suffix == '.mkv':
        filemeta['link'] = "/vp8/{}".format(base32path)
        filemeta["is_vp8"] = True
    elif file.suffix.lower() in {'.jpg', '.jpeg'}:
        try:
            jpg = pyimglib.decoders.jpeg.JPEGDecoder(file)
            if (jpg.arithmetic_coding()):
                filemeta['link'] = "/image/webp/{}".format(base32path)
        except Exception:
            filemeta['link'] = "/image/webp/{}".format(base32path)
    return filemeta

