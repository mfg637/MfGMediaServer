import flask
import shared_code
import medialib_db
import math
import urllib.parse
import filesystem
import json
import pyimglib
import pathlib
import PIL.Image
import config
import logging

logger = logging.getLogger(__name__)


NUMBER_OF_ITEMS = 0
CACHED_REQUEST = None


medialib_blueprint = flask.Blueprint('medialib', __name__, url_prefix='/medialib')


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
            tag["tags"].append(tags_list.pop(0))
    page = int(flask.request.args.get('page', 0))
    order_by = int(flask.request.args.get("sorting_order", medialib_db.files_by_tag_search.ORDERING_BY.DATE_DECREASING.value))
    hidden_filtering = int(flask.request.args.get("hidden_filtering",
                                                  medialib_db.files_by_tag_search.HIDDEN_FILTERING.FILTER.value))

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
        tags_group["group_str"] = " or ".join([medialib_db.get_tag_name_by_alias(tag) for tag in tags_group["tags"]])

    title = "Search query results for {}".format(
        (" and ".join([("not " if tags_group["not"] else "") + tags_group["group_str"] for tags_group in tags_groups]))
    )
    template_kwargs = {
        'title': title,
        '_glob': None,
        'url': flask.request.base_url,
        'args': _args,
        'medialib_sorting': shared_code.get_medialib_sorting_constants_for_template(),
        'medialib_hidden_filtering': medialib_db.files_by_tag_search.HIDDEN_FILTERING,
        'enable_external_scripts': shared_code.enable_external_scripts
    }

    return flask.render_template(
        'index.html',
        itemslist=itemslist,
        dirmeta=json.dumps(dirmeta_list),
        filemeta=json.dumps(content_list),
        page=page,
        max_pages=max_pages,
        thumbnail=shared_code.get_thumbnail_size(),
        **template_kwargs
    )


@medialib_blueprint.route('/show-album/id<int:album_id>')
@shared_code.login_validation
def medialib_show_album(album_id: int):
    db_connection = medialib_db.common.make_connection()

    _album_title = medialib_db.get_album_title(album_id, connection=db_connection)
    title = "{} by {}".format(_album_title[0], _album_title[1])
    raw_content_list = medialib_db.get_album_content(album_id, connection=db_connection)

    items_count = 0
    itemslist = [{
        "icon": flask.url_for('static', filename='images/updir_icon.svg'),
        "name": "back to file browser",
        "lazy_load": False,
    }]
    itemslist[0]["link"] = "/"
    items_count += 1

    content_list = filesystem.browse.db_content_processing(raw_content_list, items_count)
    itemslist.extend(content_list)

    template_kwargs = {
        'title': title,
        '_glob': None,
        'url': flask.request.base_url,
        'args': [],
        'medialib_sorting': shared_code.get_medialib_sorting_constants_for_template(),
        'medialib_hidden_filtering': medialib_db.files_by_tag_search.HIDDEN_FILTERING,
        'enable_external_scripts': shared_code.enable_external_scripts
    }

    return flask.render_template(
        'index.html',
        itemslist=itemslist,
        dirmeta=json.dumps([]),
        filemeta=json.dumps(content_list),
        page=0,
        max_pages=0,
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


@medialib_blueprint.route('/thumbnail/<string:_format>/<int:width>x<int:height>/id<int:content_id>')
@shared_code.login_validation
def gen_thumbnail(_format: str, width: int, height: int, content_id: int | None):
    def complex_formats_processing(img, file_path, allow_origin) -> PIL.Image.Image | flask.Response:
        logger.info("complex_formats_processing")
        if isinstance(img, pyimglib.decoders.frames_stream.FramesStream):
            img = shared_code.extract_frame_from_video(img)
            logger.debug("extracted frame: {}".format(img.__repr__()))
        return img

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
        representations = medialib_db.get_representation_by_content_id(content_id, db_connection)
        if len(representations) == 0:
            logger.debug("register representations for content id = {}".format(content_id))
            cursor = db_connection.cursor()
            medialib_db.srs_indexer.srs_update_representations(content_id, file_path, cursor)
            db_connection.commit()
            cursor.close()
            representations = medialib_db.get_representation_by_content_id(content_id, db_connection)
        if allow_origin:
            for representation in representations:
                if representation.compatibility_level >= compatibility_level:
                    db_connection.close()
                    base32path = shared_code.str_to_base32(str(representation.file_path))
                    return flask.redirect(
                        "https://{}:{}/orig/{}".format(
                            config.host_name,
                            config.port,
                            base32path
                        )
                    )
            logger.info("generate thumbnail from best available representation")
            img = pyimglib.decoders.open_image(representations[0].file_path)
            file_path = representations[0].file_path
        else:
            logger.info("generate thumbnail from worst available representation")
            # allow_hashing = False
            file_path = representations[-1].file_path
            img = pyimglib.decoders.open_image(representations[-1].file_path)
    else:
        logger.info("default thumbnail generation")
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
