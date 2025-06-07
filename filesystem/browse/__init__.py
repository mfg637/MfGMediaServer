import dataclasses
from typing import Type

import flask
import json
import pathlib
import math

import medialib_db
import shared_code
import shared_code.enums as shared_enums
import pyimglib

load_acceleration = shared_enums.LoadAcceleration.NONE

image_file_extensions = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".svg",
    ".avif",
    ".jxl",
}
video_file_extensions = {".mkv", ".mp4", ".webm"}
audio_file_extensions = {".mp3", ".m4a", ".ogg", ".oga", ".opus", ".flac"}
supported_file_extensions = (
    image_file_extensions.union(video_file_extensions)
    .union(audio_file_extensions)
    .union({".mpd", ".srs", ".m3u8"})
)

from . import InfoExtractor

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


def browse_folder(folder):
    path_dir_objects = []
    path_file_objects = []
    path_srs_objects = []
    path_mpd_objects = []
    for entry in folder.iterdir():
        if entry.is_file() and entry.suffix.lower() == ".srs":
            path_srs_objects.append(entry)
        elif entry.is_file() and entry.suffix.lower() == ".mpd":
            path_mpd_objects.append(entry)
        elif (
            entry.is_file()
            and entry.suffix.lower() in supported_file_extensions
        ):
            path_file_objects.append(entry)
        elif entry.is_dir() and entry.name[0] != ".":
            path_dir_objects.append(entry)
    return (
        path_dir_objects,
        path_file_objects,
        path_srs_objects,
        path_mpd_objects,
    )


def extract_mtime_key(file: pathlib.Path):
    return file.stat().st_mtime


def browse(dir):
    global page_cache
    items_per_page = int(
        flask.request.args.get("per_page", flask.session["items_per_page"])
    )
    dirlist, filelist, srs_filelist, mpd_filelist = [], [], [], []
    glob_pattern = flask.request.args.get("glob", None)
    itemslist, dirmeta_list, filemeta_list = page_cache.get_cache(
        dir, glob_pattern
    )
    if len(itemslist) == 0:
        items_count: int = 0

        if glob_pattern is None:
            dirlist, filelist, srs_filelist, mpd_filelist = browse_folder(dir)
            if dir != shared_code.root_dir:
                itemslist.append(
                    {
                        "icon": flask.url_for(
                            "static", filename="images/updir_icon.svg"
                        ),
                        "name": "..",
                    }
                )
                if dir.parent == shared_code.root_dir:
                    itemslist[0]["link"] = "/"
                else:
                    itemslist[0]["link"] = "/browse/{}".format(
                        dir.parent.relative_to(shared_code.root_dir)
                    )
                items_count += 1
            for _dir in dirlist:
                dirmeta = {
                    "link": "/browse/{}".format(
                        _dir.relative_to(shared_code.root_dir)
                    ),
                    "icon": flask.url_for(
                        "static", filename="images/folder icon.svg"
                    ),
                    "object_icon": False,
                    "name": shared_code.simplify_filename(_dir.name),
                    "sources": None,
                    "item_index": items_count,
                    "type": "dir",
                }
                try:
                    if _dir.joinpath(".imgview-dir-config.json").exists():
                        dirmeta["object_icon"] = True
                        dirmeta["icon"] = "/folder_icon_paint/{}".format(
                            _dir.relative_to(shared_code.root_dir)
                        )
                except PermissionError:
                    pass
                itemslist.append(dirmeta)
                items_count += 1
        else:
            itemslist.append(
                {
                    "icon": flask.url_for(
                        "static", filename="images/updir_icon.svg"
                    ),
                    "name": ".",
                    "link": flask.request.path,
                }
            )
            items_count += 1
            for file in dir.glob(glob_pattern):
                if file.is_file() and file.suffix.lower() == ".srs":
                    srs_filelist.append(file)
                elif file.is_file() and file.suffix.lower() == ".mpd":
                    mpd_filelist.append(file)
                elif (
                    file.is_file()
                    and file.suffix.lower() in supported_file_extensions
                ):
                    filelist.append(file)
        excluded_filelist = []
        for srs_file in srs_filelist:
            f = srs_file.open("r")
            content, streams, cl_level = pyimglib.ACLMMP.srs_parser.parseJSON(
                f
            )
            f.close()
            excluded_filelist.extend(
                pyimglib.ACLMMP.srs_parser.get_files_list(
                    srs_file, content, streams
                )
            )
            filelist.append(srs_file)
        for mpd_file in mpd_filelist:
            dash_handler = (
                pyimglib.transcoding.encoders.dash_encoder.DashVideoEncoder(1)
            )
            dash_handler.set_manifest_file(mpd_file)
            files = dash_handler.get_files()[:-1]
            excluded_filelist.extend(files)
            filelist.append(mpd_file)
        filelist.sort(key=extract_mtime_key, reverse=True)

        filemeta_list, items_count = files_processor(
            filelist, excluded_filelist, items_count
        )

        itemslist.extend(filemeta_list)
        page_cache = PageCache(
            dir, (itemslist, dirmeta_list, filemeta_list), glob_pattern
        )
    title = ""
    if dir == shared_code.root_dir:
        title = "root"
    else:
        title = dir.name
    template_kwargs = {
        "title": title,
        "_glob": glob_pattern,
        "url": flask.request.base_url,
        "args": "",
        "enable_external_scripts": shared_code.enable_external_scripts,
    }
    page = int(flask.request.args.get("page", 0))
    max_pages = math.ceil(len(itemslist) / items_per_page)
    min_index = page * items_per_page
    max_index = min_index + items_per_page
    final_filemeta_list = list()
    final_dirmeta_list = list()

    calc_item_page_index(
        dirmeta_list, final_dirmeta_list, min_index, max_index
    )
    calc_item_page_index(
        filemeta_list, final_filemeta_list, min_index, max_index
    )
    return flask.render_template(
        "index.html",
        itemslist=itemslist[min_index:max_index],
        dirmeta=json.dumps(final_dirmeta_list),
        filemeta=json.dumps(final_filemeta_list),
        query_data=json.dumps(shared_code.tag_query_placeholder),
        pagination=True,
        page=page,
        max_pages=max_pages,
        items_per_page=items_per_page,
        thumbnail=shared_code.get_thumbnail_size(),
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


def db_content_processing(
    content_list,
    initial_item_count,
    extractor_type: Type[
        InfoExtractor.MedialibDefaultExtractor
    ] = InfoExtractor.MedialibDefaultExtractor,
    **kwargs
):
    items_count = initial_item_count
    content_data_list = list()
    for file in content_list:
        extractor = extractor_type(*file, items_count=items_count, **kwargs)
        file_data = extractor.get_filemeta()
        items_count = extractor.get_current_item_number()
        content_data_list.append(file_data)
    return content_data_list


@dataclasses.dataclass(frozen=True)
class DataElement:
    db_content: medialib_db.content.Content
    origins: list[medialib_db.origin.Origin] | None


def db_dataclass_processing(
    data_list: list[DataElement],
    initial_item_count,
    extractor_type: Type[
        InfoExtractor.MedialibDefaultDataExtractor
    ] = InfoExtractor.MedialibDefaultDataExtractor,
    **kwargs
):
    items_count = initial_item_count
    content_data_list = list()
    for data in data_list:
        if data.origins is None:
            extractor = extractor_type(
                data.db_content, items_count=items_count, **kwargs
            )
        else:
            extractor = extractor_type(
                data.db_content,
                data.origins,
                items_count=items_count,
                **kwargs
            )
        file_data = extractor.get_filemeta()
        items_count = extractor.get_current_item_number()
        content_data_list.append(file_data)
    return content_data_list


def get_file_info(file: pathlib.Path, items_count=0):
    extractor = InfoExtractor.FileExtractor(file, items_count)
    return extractor.get_filemeta()


def get_db_content_info(
    content_id: int,
    file_str: str,
    content_type,
    title,
    items_count=0,
    icon_scale=1,
):
    extractor = InfoExtractor.MedialibDefaultExtractor(
        content_id, file_str, content_type, title, items_count, icon_scale
    )
    return extractor.get_filemeta(), extractor.get_current_item_number()
