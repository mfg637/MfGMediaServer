import abc
import pathlib

import flask

import config
import pyimglib
import medialib_db
import shared_code
import shared_code.enums as shared_enums
from . import image_file_extensions, video_file_extensions

load_acceleration = shared_enums.LoadAcceleration.NONE

THUMBNAIL_FORMATS = ("webp", "jpeg")
THUMBNAIL_SCALES = (1, 1.5, 2, 3, 4)


class InfoExtractor(abc.ABC):
    def __init__(self, items_count):
        self.filemeta = {
            "icon": None,
            "object_icon": False,
            "sources": None,
            "is_vp8": False,
            "custom_icon": False,
        }
        self.items_count = items_count

    def get_filemeta(self):
        return self.filemeta

    def get_current_item_number(self):
        return self.items_count + 1

    @abc.abstractmethod
    def make_icon(self, file, filemeta, scale=1):
        pass


# dataclass extractor must be incompatible with InfoExtractor
class DataclassInfoExtractor(abc.ABC):
    def __init__(self, items_count):
        self.filemeta = {
            "icon": None,
            "object_icon": False,
            "sources": None,
            "is_vp8": False,
            "custom_icon": False,
        }
        self.items_count = items_count

    def get_filemeta(self):
        return self.filemeta

    def get_current_item_number(self):
        return self.items_count + 1

    @abc.abstractmethod
    def make_icon(self, file, filemeta, scale=1):
        pass


class FileExtractor(InfoExtractor):
    def __init__(self, file: pathlib.Path, items_count=0):
        super().__init__(items_count)
        self.file = file

        base32path = shared_code.str_to_base32(str(file))
        self.filemeta |= {
            "link": "/orig/{}".format(base32path),
            "name": shared_code.simplify_filename(file.name),
            "file_name": shared_code.simplify_filename(file.name),
            "base32path": base32path,
            "item_index": items_count,
            "type": "audio",
            "suffix": file.suffix,
            "content_id": None,
        }
        icon_path = pathlib.Path("{}.icon".format(file))
        if (file.suffix.lower() in image_file_extensions) or (
            file.suffix.lower() in video_file_extensions
        ):
            self.make_icon(file, self.filemeta)
            if file.suffix == ".jxl":
                self.filemeta["link"] = "/image/png/{}".format(base32path)
        if file.suffix.lower() in image_file_extensions:
            self.filemeta["type"] = "picture"
        elif file.suffix.lower() in video_file_extensions:
            self.filemeta["type"] = "video"
        elif file.suffix.lower() == ".mpd":
            self.filemeta["type"] = "DASH"
            self.filemeta["link"] = "/{}{}".format(
                ("" if dir == shared_code.root_dir else "browse/"),
                str(file.relative_to(shared_code.root_dir)),
            )
            self.make_icon(file, self.filemeta)
        elif file.suffix.lower() == ".srs":
            TYPE = pyimglib.decoders.srs.type_detect(file)
            if (
                TYPE == pyimglib.ACLMMP.srs_parser.MEDIA_TYPE.VIDEO
                or TYPE == pyimglib.ACLMMP.srs_parser.MEDIA_TYPE.VIDEOLOOP
            ):
                self.filemeta["type"] = "video"
                self.filemeta["link"] = "/aclmmp_webm/{}".format(base32path)
            elif TYPE == pyimglib.ACLMMP.srs_parser.MEDIA_TYPE.IMAGE:
                self.filemeta["type"] = "picture"
                self.filemeta["link"] = "/image/autodetect/{}".format(
                    base32path
                )
            self.make_icon(file, self.filemeta)
        elif file.suffix.lower() == ".m3u8":
            access_token = shared_code.gen_access_token()
            self.filemeta["link"] = "https://{}:{}/m3u8/{}.m3u8".format(
                config.host_name, config.port, base32path
            )
            shared_code.access_tokens[self.filemeta["link"]] = access_token
            self.filemeta["link"] += "?access_token={}".format(access_token)
            if icon_path.exists():
                self.make_icon(file, self.filemeta)
        if file.suffix == ".mkv":
            self.filemeta["link"] = "/vp8/{}".format(base32path)
            self.filemeta["is_vp8"] = True

    def make_icon(self, file, filemeta, scale=1):
        filemeta["lazy_load"] = load_acceleration in {
            shared_enums.LoadAcceleration.LAZY_LOAD,
            shared_enums.LoadAcceleration.BOTH,
        }
        icon_base32path = filemeta["base32path"]
        icon_path = pathlib.Path("{}.icon".format(file))
        if icon_path.exists():
            filemeta["custom_icon"] = True
            icon_base32path = shared_code.str_to_base32(
                str(icon_path.relative_to(shared_code.root_dir))
            )
        width = flask.session["thumbnail_width"]
        height = flask.session["thumbnail_height"]
        filemeta["icon"] = "/thumbnail/jpeg/{}x{}/{}".format(
            width * scale, height * scale, icon_base32path
        )

        filemeta["sources"] = []
        for _format in THUMBNAIL_FORMATS:
            source_strings = []
            for _scale in THUMBNAIL_SCALES:
                source_strings.append(
                    "/thumbnail/{}/{}x{}/{} {}x".format(
                        _format,
                        int(width * _scale * scale),
                        int(height * _scale * scale),
                        icon_base32path,
                        _scale,
                    )
                )
            filemeta["sources"].append(", ".join(source_strings))


class MedialibDefaultExtractor(InfoExtractor):
    def __init__(
        self,
        content_id: int,
        file_str: str,
        content_type,
        title,
        items_count=0,
        icon_scale=1,
        orientation: shared_code.OrientationEnum = shared_code.OrientationEnum.HORIZONTAL,
    ):
        super().__init__(items_count)

        self.content_id = content_id
        self.file = pathlib.Path(file_str)
        base32path = shared_code.str_to_base32(str(self.file))

        self.filemeta |= {
            "link": "/orig/{}".format(base32path),
            "name": title,
            "file_name": shared_code.simplify_filename(self.file.name),
            "base32path": base32path,
            "item_index": items_count,
            "suffix": self.file.suffix,
            "type": content_type,
            "content_id": content_id,
        }
        icon_path = pathlib.Path("{}.icon".format(self.file))
        if content_type in ("image", "video", "video-loop"):
            self.make_icon(self.file, self.filemeta, icon_scale, orientation)
            if self.file.suffix == ".jxl":
                self.filemeta["link"] = "/image/png/{}".format(base32path)
        if self.file.suffix.lower() == ".mpd":
            mpd_file = self.file
            if mpd_file.is_relative_to(shared_code.root_dir):
                mpd_file = mpd_file.relative_to(shared_code.root_dir)
            self.filemeta["type"] = "DASH"
            self.filemeta["link"] = "/{}{}".format(
                ("" if dir == shared_code.root_dir else "browse/"),
                str(mpd_file),
            )
            if icon_path.exists():
                self.make_icon(
                    self.file, self.filemeta, icon_scale, orientation
                )
        elif self.file.suffix.lower() == ".srs":
            if content_type in ("video", "video-loop"):
                self.filemeta["type"] = "video"
                self.filemeta["link"] = "/aclmmp_webm/{}".format(base32path)
            elif content_type == "image":
                self.filemeta["type"] = "picture"
                self.filemeta["link"] = "/image/autodetect/{}".format(
                    base32path
                )
            self.make_icon(self.file, self.filemeta, icon_scale, orientation)
        elif self.file.suffix.lower() == ".m3u8":
            access_token = shared_code.gen_access_token()
            self.filemeta["link"] = "https://{}:{}/m3u8/{}.m3u8".format(
                config.host_name, config.port, base32path
            )
            shared_code.access_tokens[self.filemeta["link"]] = access_token
            self.filemeta["link"] += "?access_token={}".format(access_token)
            if icon_path.exists():
                self.make_icon(
                    self.file, self.filemeta, icon_scale, orientation
                )
        if self.file.suffix == ".mkv":
            self.filemeta["link"] = "/vp8/{}".format(base32path)
            self.filemeta["is_vp8"] = True

    def make_icon(
        self,
        file,
        filemeta,
        scale=1,
        orientation: shared_code.OrientationEnum = shared_code.OrientationEnum.HORIZONTAL,
    ):
        default_size = shared_code.get_thumbnail_size(scale, orientation)
        filemeta["icon"] = "/medialib/thumbnail/jpeg/{}x{}/id{}".format(
            default_size["width"],
            default_size["height"],
            filemeta["content_id"],
        )
        filemeta["sources"] = []
        for _format in THUMBNAIL_FORMATS:
            source_strings = []
            for _scale in THUMBNAIL_SCALES:
                size = shared_code.get_thumbnail_size(
                    scale * _scale, orientation
                )
                source_strings.append(
                    "/medialib/thumbnail/{}/{}x{}/id{} {}x".format(
                        _format,
                        size["width"],
                        size["height"],
                        filemeta["content_id"],
                        _scale,
                    )
                )
            filemeta["sources"].append(", ".join(source_strings))


class MedialibDefaultDataExtractor(DataclassInfoExtractor):
    def __init__(
        self,
        db_content: medialib_db.content.Content,
        items_count=0,
        icon_scale=1,
        orientation: shared_code.OrientationEnum = shared_code.OrientationEnum.HORIZONTAL,
    ):
        super().__init__(items_count)

        self.content_id = db_content.content_id
        self.file = db_content.file_path
        base32path = shared_code.str_to_base32(str(self.file))

        self.filemeta |= {
            "link": "/orig/{}".format(base32path),
            "name": db_content.title,
            "file_name": shared_code.simplify_filename(self.file.name),
            "base32path": base32path,
            "item_index": items_count,
            "suffix": self.file.suffix,
            "type": db_content.content_type,
            "content_id": db_content.content_id,
        }
        icon_path = pathlib.Path("{}.icon".format(self.file))
        if db_content.content_type in ("image", "video", "video-loop"):
            self.make_icon(self.file, self.filemeta, icon_scale, orientation)
            if self.file.suffix == ".jxl":
                self.filemeta["link"] = "/image/png/{}".format(base32path)
        if self.file.suffix.lower() == ".mpd":
            mpd_file = self.file
            if mpd_file.is_relative_to(shared_code.root_dir):
                mpd_file = mpd_file.relative_to(shared_code.root_dir)
            self.filemeta["type"] = "DASH"
            self.filemeta["link"] = "/{}{}".format(
                ("" if dir == shared_code.root_dir else "browse/"),
                str(mpd_file),
            )
            if icon_path.exists():
                self.make_icon(
                    self.file, self.filemeta, icon_scale, orientation
                )
        elif self.file.suffix.lower() == ".srs":
            if db_content.content_type in ("video", "video-loop"):
                self.filemeta["type"] = "video"
                self.filemeta["link"] = "/aclmmp_webm/{}".format(base32path)
            elif db_content.content_type == "image":
                self.filemeta["type"] = "picture"
                self.filemeta["link"] = "/image/autodetect/{}".format(
                    base32path
                )
            self.make_icon(self.file, self.filemeta, icon_scale, orientation)
        elif self.file.suffix.lower() == ".m3u8":
            access_token = shared_code.gen_access_token()
            self.filemeta["link"] = "https://{}:{}/m3u8/{}.m3u8".format(
                config.host_name, config.port, base32path
            )
            shared_code.access_tokens[self.filemeta["link"]] = access_token
            self.filemeta["link"] += "?access_token={}".format(access_token)
            if icon_path.exists():
                self.make_icon(
                    self.file, self.filemeta, icon_scale, orientation
                )
        if self.file.suffix == ".mkv":
            self.filemeta["link"] = "/vp8/{}".format(base32path)
            self.filemeta["is_vp8"] = True

    def make_icon(
        self,
        file,
        filemeta,
        scale=1,
        orientation: shared_code.OrientationEnum = shared_code.OrientationEnum.HORIZONTAL,
    ):
        default_size = shared_code.get_thumbnail_size(scale, orientation)
        filemeta["icon"] = "/medialib/thumbnail/jpeg/{}x{}/id{}".format(
            default_size["width"],
            default_size["height"],
            filemeta["content_id"],
        )
        filemeta["sources"] = []
        for _format in THUMBNAIL_FORMATS:
            source_strings = []
            for _scale in THUMBNAIL_SCALES:
                size = shared_code.get_thumbnail_size(
                    scale * _scale, orientation
                )
                source_strings.append(
                    "/medialib/thumbnail/{}/{}x{}/id{} {}x".format(
                        _format,
                        size["width"],
                        size["height"],
                        filemeta["content_id"],
                        _scale,
                    )
                )
            filemeta["sources"].append(", ".join(source_strings))


class MedialibExtendedExtractor(MedialibDefaultExtractor):
    def __init__(
        self,
        content_id: int,
        file_str: str,
        content_type,
        title,
        description,
        origin_name,
        origin_content_id,
        items_count=0,
        icon_scale=1,
        orientation=shared_code.OrientationEnum.HORIZONTAL,
    ):
        super().__init__(
            content_id,
            file_str,
            content_type,
            title,
            items_count,
            icon_scale,
            orientation,
        )
        self.filemeta |= {
            "description": description,
            "origin_name": origin_name,
            "origin_content_id": origin_content_id,
        }


class MedialibExtendedDataExtractor(MedialibDefaultDataExtractor):
    def __init__(
        self,
        db_content: medialib_db.content.Content,
        origins: list[medialib_db.origin.Origin],
        items_count=0,
        icon_scale=1,
        orientation=shared_code.OrientationEnum.HORIZONTAL,
    ):
        super().__init__(db_content, items_count, icon_scale, orientation)
        origin_name: str | None = None
        origin_id: str | None = None
        for current_origin in origins:
            if not current_origin.alternate:
                origin_name = current_origin.origin_name
                origin_id = current_origin.origin_id
        if origin_name is None and len(origins) > 0:
            origin_name = origins[0].origin_name
            origin_id = origins[0].origin_id
        self.filemeta |= {
            "description": db_content.description,
            "origin_name": origin_name,
            "origin_content_id": origin_id,
        }


class MedialibAlbumDataExtractor(MedialibExtendedDataExtractor):
    def __init__(
        self,
        db_content: medialib_db.album.OrderedContent,
        origins: list[medialib_db.origin.Origin],
        items_count=0,
        icon_scale=1,
        orientation=shared_code.OrientationEnum.HORIZONTAL,
    ):
        super().__init__(
            db_content,
            origins,
            items_count,
            icon_scale,
            orientation,
        )
        self.filemeta |= {
            "album_order": db_content.order,
        }


class MedialibAlbumGalleryExtractor(MedialibDefaultExtractor):
    def __init__(
        self,
        content_id: int,
        file_str: str,
        content_type,
        title,
        album_id,
        items_count=0,
        icon_scale=1.5,
    ):
        super().__init__(
            content_id,
            file_str,
            content_type,
            title,
            items_count,
            icon_scale,
            orientation=shared_code.OrientationEnum.VERTICAL,
        )
        self.filemeta |= {
            "link": "/medialib/album/show/id{}".format(album_id),
        }
