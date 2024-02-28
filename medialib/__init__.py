import dataclasses
import datetime
import io

import flask
import shared_code
import medialib_db
import math
import urllib.parse
import filesystem
import json
import pyimglib
import pathlib
import PIL.Image as PILimage
from PIL.Image import Image as PILimageClass
import PIL.Image
import config
import logging
import multiprocessing.managers

from shared_code import jpeg_xl_fast_decode
from . import album, tag_manager

logger = logging.getLogger(__name__)


NUMBER_OF_ITEMS = 0
CACHED_REQUEST = None

process: multiprocessing.Process | None = None
manager = None
shared_state: multiprocessing.managers.Namespace | None = None
result_pipe: multiprocessing.connection.Connection | None = None
clip_processing_content_id = None


medialib_blueprint = flask.Blueprint('medialib', __name__, url_prefix='/medialib')

medialib_blueprint.register_blueprint(album.album_blueprint)
medialib_blueprint.register_blueprint(tag_manager.tag_manager_blueprint)


@medialib_blueprint.route('/tag-search')
@shared_code.login_validation
def medialib_tag_search():
    global NUMBER_OF_ITEMS
    global CACHED_REQUEST

    tags_count = flask.request.args.getlist('tags_count')
    tags_list = flask.request.args.getlist('tags')
    not_tag = flask.request.args.getlist('not')
    tags_groups = [{"not": bool(int(not_tag[i])), "tags": [], "count": int(tags_count[i])} for i in range(len(tags_count))]
    for tag in tags_groups:
        tags_count = tag["count"]
        for i in range(tags_count):
            value = tags_list.pop(0)
            if value.isdigit():
                value = int(value)
            tag["tags"].append(value)
    page = int(flask.request.args.get('page', 0))
    order_by = int(flask.request.args.get("sorting_order", medialib_db.files_by_tag_search.ORDERING_BY.DATE_DECREASING.value))
    hidden_filtering = int(flask.request.args.get("hidden_filtering",
                                                  medialib_db.files_by_tag_search.HIDDEN_FILTERING.FILTER.value))
    query_data = {
        "tags_groups": tags_groups,
        "order_by": order_by,
        "hidden_filtering": hidden_filtering
    }

    _args = ""
    for key in flask.request.args:
        if key != "page":
            for value in flask.request.args.getlist(key):
                _args += "&{}={}".format(urllib.parse.quote_plus(key), urllib.parse.quote_plus(value))

    global page_cache
    itemslist, dirmeta_list, content_list = [], [], []


    max_pages = 0
    raw_content_list = medialib_db.files_by_tag_search.get_media_by_tags(
        *tags_groups,
        limit=flask.session['items_per_page'] + 1,
        offset=flask.session['items_per_page'] * page,
        order_by=medialib_db.files_by_tag_search.ORDERING_BY(order_by),
        filter_hidden=medialib_db.files_by_tag_search.HIDDEN_FILTERING(hidden_filtering)
    )
    if CACHED_REQUEST is not None and CACHED_REQUEST == tuple(tags_groups):
        max_pages = math.ceil(NUMBER_OF_ITEMS / filesystem.browse.items_per_page)
    else:
        CACHED_REQUEST = tuple(tags_groups)
        NUMBER_OF_ITEMS = medialib_db.files_by_tag_search.count_files_with_every_tag(
            *tags_groups,
            filter_hidden=medialib_db.files_by_tag_search.HIDDEN_FILTERING(hidden_filtering)
        )
        max_pages = math.ceil(NUMBER_OF_ITEMS / flask.session['items_per_page'])


    items_count = 0
    itemslist.append({
        "icon": flask.url_for('static', filename='images/updir_icon.svg'),
        "name": "back to file browser",
        "lazy_load": False,
    })
    itemslist[0]["link"] = "/"
    items_count += 1

    content_list = filesystem.browse.db_content_processing(raw_content_list, items_count)

    itemslist.extend(content_list)

    tags_group_str = []
    for tags_group in tags_groups:
        group_list = []
        for tag in tags_group["tags"]:
            if type(tag) is int:
                group_list.append(medialib_db.get_tag_name_by_id(tag))
            else:
                group_list.append(medialib_db.get_tag_name_by_alias(tag))
        tags_group["group_str"] = " or ".join([tag for tag in group_list])

    title = "Search query results for {}".format(
        (" and ".join([("not " if tags_group["not"] else "") + tags_group["group_str"] for tags_group in tags_groups]))
    )
    template_kwargs = {
        'title': title,
        '_glob': None,
        'url': flask.request.base_url,
        'args': _args,
        'enable_external_scripts': shared_code.enable_external_scripts
    }

    return flask.render_template(
        'index.html',
        itemslist=itemslist,
        dirmeta=json.dumps(dirmeta_list),
        filemeta=json.dumps(content_list),
        query_data=json.dumps(query_data),
        page=page,
        max_pages=max_pages,
        thumbnail=shared_code.get_thumbnail_size(),
        **template_kwargs
    )


@medialib_blueprint.route('/show-duplicates/')
@shared_code.login_validation
def medialib_show_duplicates():
    db_connection = medialib_db.common.make_connection()

    show_alternates = bool(int(flask.request.args.get('show_alternates', 0)))

    items_count = 0
    content_list = []

    duplicated_group_items = medialib_db.find_duplicates(connection=db_connection, show_alternates=show_alternates)
    for group in duplicated_group_items:
        for content in group.duplicated_images:
            content_metadata = filesystem.browse.db_content_processing(
                [(content.content_id, content.file_path, content.content_type, content.title)], items_count
            )
            content.content_metadata = content_metadata[0]
            content_list.append(content_metadata)
            items_count += 1

    itemslist = content_list

    template_kwargs = {
        'url': flask.request.base_url,
        'args': [],
        'enable_external_scripts': shared_code.enable_external_scripts
    }

    return flask.render_template(
        'show_duplicates.html',
        itemslist=itemslist,
        duplicated_groups=duplicated_group_items,
        dirmeta=json.dumps([]),
        filemeta=json.dumps(content_list),
        query_data=json.dumps(shared_code.tag_query_placeholder),
        page=0,
        max_pages=0,
        thumbnail=shared_code.get_thumbnail_size(),
        **template_kwargs
    )


@medialib_blueprint.route('/content-update/<int:content_id>', methods=['POST'])
@shared_code.login_validation
def ml_update_content(content_id: int):
    if flask.request.method == 'POST':
        medialib_db_connection = medialib_db.common.make_connection()
        content_data = medialib_db.get_content_metadata_by_content_id(content_id, medialib_db_connection)
        if content_data is None:
            medialib_db_connection.close()
            return flask.abort(404)

        old_file_path = medialib_db.config.relative_to.joinpath(content_data[1])
        if old_file_path.exists():
            manifest_files_handler = None
            if old_file_path.suffix == ".srs":
                manifest_files_handler = pyimglib.transcoding.encoders.srs_image_encoder.SrsImageEncoder(1, 1, 1)
                manifest_files_handler.set_manifest_file(old_file_path)
            elif old_file_path.suffix == ".mpd":
                manifest_files_handler = pyimglib.transcoding.encoders.dash_encoder.DashVideoEncoder(1)
                manifest_files_handler.set_manifest_file(old_file_path)
            if manifest_files_handler is not None:
                manifest_files_handler.delete_result()
            else:
                old_file_path.unlink()

        f = flask.request.files['content-update-file']
        file_path = shared_code.root_dir.joinpath("pictures").joinpath("medialib").joinpath(
            "mlid{}{}".format(content_id, pathlib.Path(f.filename).suffix)
        )
        f.save(file_path)
        f.close()
        image_hash = None
        if file_path.suffix in {".jpeg", ".jpg", ".png", ".webp", ".avif"}:
            with PIL.Image.open(file_path) as img:
                image_hash = shared_code.calc_image_hash(img)
        medialib_db.update_file_path(
            content_id, file_path, image_hash, medialib_db_connection
        )
        medialib_db_connection.close()
        return 'file uploaded successfully'


@medialib_blueprint.route('/db-drop-thumbnails/<int:content_id>', methods=['GET'])
@shared_code.login_validation
def drop_thumbnails(content_id):
    connection = medialib_db.common.make_connection()
    medialib_db.drop_thumbnails(content_id, connection)
    connection.close()
    return "OK"


def load_representations(content_id: int, file_path: pathlib.Path, db_connection) -> list[medialib_db.srs_indexer.ContentRepresentationUnit]:
    representations = medialib_db.get_representation_by_content_id(content_id, db_connection)
    if len(representations) == 0:
        logger.debug("register representations for content id = {}".format(content_id))
        cursor = db_connection.cursor()
        medialib_db.srs_indexer.srs_update_representations(content_id, file_path, cursor)
        db_connection.commit()
        cursor.close()
        representations = medialib_db.get_representation_by_content_id(content_id, db_connection)
    return representations

def complex_formats_processing(img, file_path = None, allow_origin = None) -> PIL.Image.Image:
    logger.info("complex_formats_processing")
    if isinstance(img, pyimglib.decoders.frames_stream.FramesStream):
        img = shared_code.extract_frame_from_video(img)
        logger.debug("extracted frame: {}".format(img.__repr__()))
    return img

@medialib_blueprint.route('/thumbnail/<string:_format>/<int:width>x<int:height>/id<int:content_id>')
@shared_code.login_validation
def gen_thumbnail(_format: str, width: int, height: int, content_id: int | None):
    if not len(medialib_db.config.db_name):
        flask.abort(404)
    allow_origin = bool(flask.request.args.get('allow_origin', False))
    content_id = int(content_id)
    db_connection = medialib_db.common.make_connection()
    if config.thumbnail_cache_dir is not None:
        thumbnail_file_path, thumbnail_format = medialib_db.get_thumbnail_by_content_id(
            content_id,
            width, height,
            _format,
            db_connection
        )
        if thumbnail_file_path is not None:
            db_connection.close()
            return flask.send_file(
                config.thumbnail_cache_dir.joinpath(thumbnail_file_path),
                mimetype=shared_code.MIME_TYPES_BY_FORMAT[thumbnail_format],
                max_age=24 * 60 * 60
            )
    content_metadata = medialib_db.get_content_metadata_by_content_id(content_id, db_connection)

    file_path = shared_code.root_dir.joinpath(content_metadata[1])
    compatibility_level = int(flask.request.cookies.get("clevel"))

    img = None
    allow_hashing = True

    if content_metadata[3] == "image":
        if file_path.suffix == ".svg":
            allow_hashing = False
    else:
        allow_hashing = False

    if file_path.suffix == ".srs":
        representations = load_representations(content_id, file_path, db_connection)
        if allow_origin:
            for representation in representations:
                if representation.compatibility_level >= compatibility_level and representation.format == _format:
                    db_connection.close()
                    base32path = shared_code.str_to_base32(str(representation.file_path))
                    return flask.redirect(
                        "https://{}:{}/orig/{}".format(
                            config.host_name,
                            config.port,
                            base32path
                        )
                    )
            if representations[-1].format in {"webp", "jpeg", "png"}:
                db_connection.close()
                base32path = shared_code.str_to_base32(str(representations[-1].file_path))
                return flask.redirect(
                    "https://{}:{}/orig/{}".format(
                        config.host_name,
                        config.port,
                        base32path
                    )
                )
            if representations[-1].format == "jxl":
                jpeg_buffer = io.BytesIO(jpeg_xl_fast_decode(representations[-1].file_path))
                return flask.send_file(jpeg_buffer, mimetype="image/jpeg")
            logger.info("generate thumbnail from best available representation")
            img = pyimglib.decoders.open_image(representations[0].file_path)
            file_path = representations[0].file_path
        else:
            logger.info("generate thumbnail from worst available representation")
            # allow_hashing = False
            file_path = representations[-1].file_path
    else:
        logger.info("default thumbnail generation")

    if file_path.suffix == ".jxl":
        jpeg_buffer = io.BytesIO(jpeg_xl_fast_decode(file_path))
        if allow_origin:
            return flask.send_file(jpeg_buffer, mimetype="image/jpeg")
        img = PIL.Image.open(jpeg_buffer)
    else:
        img = pyimglib.decoders.open_image(file_path)

    extracted_img = complex_formats_processing(img, file_path, allow_origin)
    logger.debug("extracted_img: {}".format(extracted_img.__repr__()))
    if isinstance(extracted_img, flask.Response):
        db_connection.close()
        return extracted_img
    elif isinstance(extracted_img, PIL.Image.Image):
        img = extracted_img
    else:
        raise NotImplementedError(type(extracted_img))

    if allow_hashing:
        existing_image_hash = medialib_db.get_image_hash(content_id, db_connection)
        if existing_image_hash is None:
            image_hash = pyimglib.calc_image_hash(img)
            medialib_db.set_image_hash(content_id, image_hash, db_connection)

    buffer, mime, _format = shared_code.generate_thumbnail_image(img, _format, width, height)
    if config.thumbnail_cache_dir is not None:
        thumbnail_file_name = medialib_db.register_thumbnail_by_content_id(
            content_id, width, height, _format, db_connection
        )
        if thumbnail_file_name is not None:
            thumbnail_file_path = pathlib.Path(config.thumbnail_cache_dir).joinpath(thumbnail_file_name)
            f = thumbnail_file_path.open("bw")
            f.write(buffer.getvalue())
            f.close()
            buffer.close()
            buffer = thumbnail_file_path
    db_connection.close()
    return flask.send_file(
        buffer,
        mimetype=mime,
        max_age=24 * 60 * 60,
    )


@medialib_blueprint.route('/openCLIP/<int:content_id>', methods=['GET'])
@shared_code.login_validation
def start_openclip(content_id: int):
    global process
    global manager
    global shared_state
    global result_pipe
    global clip_processing_content_id

    clip_processing_content_id = content_id

    db_connection = medialib_db.common.make_connection()

    content_metadata = medialib_db.get_content_metadata_by_content_id(content_id, db_connection)

    file_path = shared_code.root_dir.joinpath(content_metadata[1])

    img = None

    if file_path.suffix == ".srs":
        representations = load_representations(content_id, file_path, db_connection)
        img = pyimglib.decoders.open_image(representations[-1].file_path)
    else:
        img = pyimglib.decoders.open_image(file_path)

    db_connection.close()

    process, manager, shared_state, result_pipe = \
        medialib_db.openclip_classification.start_clip_classification_process(img)

    return flask.render_template('openclip_status_display.html')


@medialib_blueprint.route('/openCLIP-status-update', methods=['GET'])
@shared_code.login_validation
def openclip_status():
    global process
    global manager
    global shared_state
    global result_pipe
    global clip_processing_content_id

    response_data = None
    if process.is_alive():
        response_data = {
            "status": "loading",
            "done": shared_state.done,
            "total": shared_state.total
        }
    else:
        result = result_pipe.recv()
        response_data = {
            "status": "result",
            "content_id": clip_processing_content_id,
            "tagList": []
        }
        for result_data in result:
            response_data["tagList"].append({
                "dataTagName": result_data[1],
                "category": result_data[2],
                "probability": result_data[3],
                "tag_id": result_data[0],
                "enabled": False
            })
    return flask.Response(json.dumps(response_data), mimetype="application/json")


@medialib_blueprint.route('/post-tags', methods=['POST'])
@shared_code.login_validation
def post_tags():
    data = flask.request.json
    db_connection = medialib_db.common.make_connection()
    medialib_db.add_tags_for_content_by_tag_ids(data["content_id"], data["tag_ids"], db_connection)
    db_connection.close()
    return "OK"

@dataclasses.dataclass(frozen=True)
class ImageData:
    content_id: int
    pathstr: str
    content_type: str
    file_suffix: str
    width: int
    height: int
    representations: list[medialib_db.srs_indexer.ContentRepresentationUnit]
    source: str
    source_id: str
    download_date: datetime.datetime
    alternate_version: bool
    image: PIL.Image.Image | None

    def calc_size(self) -> int:
        return self.width * self.height

    def calc_aspect_ratio(self) -> float:
        return self.width / self.height

@dataclasses.dataclass(frozen=True)
class CompareResult:
    first_content_id: int
    second_content_id: int
    is_size_equal: bool
    is_aspect_ratio_equal: bool
    is_first_larger: bool
    is_first_newer: bool
    is_origin_equal: bool
    both_alternate_version: bool
    no_difference: bool
    difference: float | None

def custom_dumper(obj):
    if isinstance(obj, PILimageClass):
        # side effect to prevent dumping image data to page template
        obj.close()
        return None
    elif isinstance(obj, pathlib.PurePath):
        return str(obj)
    elif isinstance(obj, datetime.datetime):
        return obj.isoformat()
    elif dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    else:
        raise TypeError("Unknown type {}".format(type(obj)))

RGBA_BANDS_COUNT = 4

@medialib_blueprint.route('/compare-by-hash')
@shared_code.login_validation
def compare_image():
    value_hash = flask.request.args.get('vhash')
    hue_hash = flask.request.args.get('hhash', type=int)
    saturation_hash = flask.request.args.get('shash', type=int)
    if value_hash is None or hue_hash is None or saturation_hash is None:
        flask.abort(404)

    db_connection = medialib_db.common.make_connection()
    content_id_list = medialib_db.find_content_by_hash(value_hash, hue_hash, saturation_hash, db_connection)
    image_data_list: list[ImageData] = list()

    for content_id, alternate_version in content_id_list:
        raw_content_data = medialib_db.get_content_metadata_by_content_id(content_id, db_connection)
        representations: list[medialib_db.srs_indexer.ContentRepresentationUnit] = list()

        file_path = shared_code.root_dir.joinpath(raw_content_data[1])

        if file_path.suffix == ".srs":
            representations = load_representations(content_id, file_path, db_connection)

        img: PIL.Image.Image | None = None
        if len(representations):
            img = pyimglib.decoders.open_image(representations[0].file_path)
        else:
            img = pyimglib.decoders.open_image(file_path)

        if not isinstance(img, PILimageClass):
            img = complex_formats_processing(img)

        if not isinstance(img, PILimageClass):
            raise TypeError("Unidentified image type: {}".format(type(img)))

        image_data = ImageData(
            content_id,
            shared_code.str_to_base32(str(raw_content_data[1])),
            raw_content_data[3],
            file_path.suffix,
            img.width,
            img.height,
            representations,
            raw_content_data[6],
            raw_content_data[7],
            raw_content_data[5],
            alternate_version,
            image=img
        )

        image_data_list.append(image_data)

    compare_results: list[CompareResult] = []

    for first_index in range(len(image_data_list)):
        for second_index in range(first_index + 1, len(image_data_list)):
            first_image_data = image_data_list[first_index]
            second_image_data = image_data_list[second_index]
            size_equal: bool = \
                first_image_data.calc_size() == second_image_data.calc_size()
            difference: float | None = None
            no_difference = False
            if size_equal:
                import PIL.ImageMath
                max_value = \
                    first_image_data.calc_size() * 255 * (RGBA_BANDS_COUNT - 1)
                pixels_sum = 0
                first_rgba_image_bands = first_image_data.image.convert(
                    mode="RGBA"
                ).split()
                second_rgba_image_bands = second_image_data.image.convert(
                    mode="RGBA"
                ).split()
                bands_diff = []
                for i in range(RGBA_BANDS_COUNT):
                    diff_image: PIL.Image.Image = PIL.ImageMath.eval(
                        "abs(a - b)",
                        a = first_rgba_image_bands[i],
                        b = second_rgba_image_bands[i]
                    )
                    diff_histogram = diff_image.histogram()
                    for value in range(256):
                        pixels_sum += value * diff_histogram[value] 
                    diff_image.close()
                if pixels_sum == 0:
                    no_difference = True
                difference = pixels_sum / max_value
            compare_result = CompareResult(
                first_image_data.content_id,
                second_image_data.content_id,
                size_equal,
                first_image_data.calc_aspect_ratio() == second_image_data.calc_aspect_ratio(),
                first_image_data.calc_size() > second_image_data.calc_size(),
                first_image_data.download_date > second_image_data.download_date,
                first_image_data.source == second_image_data.source,
                first_image_data.alternate_version == True and second_image_data.alternate_version == True,
                no_difference,
                difference
            )
            compare_results.append(compare_result)
    result = {
        "image_data": image_data_list,
        "compare_results": compare_results
    }
    db_connection.close()
    return flask.render_template(
        "compare_images.html",
        title="Compare images",
        compare_data_json=json.dumps(result, default=custom_dumper)
    )

@medialib_blueprint.route('/mark_alternate')
@shared_code.login_validation
def mark_alternate():
    content_id_list = flask.request.args.getlist('content_id', type=int)
    if len(content_id_list) != 2:
        return "function takes exactly 2 content IDs"
    connection = medialib_db.common.make_connection()
    medialib_db.mark_alternate_version(content_id_list[0], content_id_list[1], connection)
    connection.close()
    return "OK"
