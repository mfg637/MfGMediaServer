import json

import flask

import filesystem
import medialib_db
import shared_code

album_blueprint = flask.Blueprint("album", __name__, url_prefix="/album")


def _get_content_list(
    db_connection,
    ordered_content_list: (
        list[medialib_db.album.OptionallyOrderedContent]
        | list[medialib_db.album.OrderedContent]
    ),
    items_count,
):
    content_data_elements: list[filesystem.browse.DataElement] = []
    for db_content in ordered_content_list:
        content_data_elements.append(
            filesystem.browse.DataElement(
                db_content,
                medialib_db.origin.get_origins_of_content(
                    db_connection, db_content.content_id
                ),
            )
        )

    content_list = filesystem.browse.db_dataclass_processing(
        content_data_elements,
        items_count,
        filesystem.browse.InfoExtractor.MedialibAlbumDataExtractor,
        orientation=shared_code.OrientationEnum.VERTICAL,
    )
    return content_list


@album_blueprint.route("/show/id<int:album_id>")
@shared_code.login_validation
def show_album(album_id: int):
    db_connection = medialib_db.common.make_connection()

    _album_title = medialib_db.album.get_album_title(
        album_id, connection=db_connection
    )
    if _album_title is None:
        return flask.abort(404, "album not found")
    title = "{} by {}".format(_album_title[0], _album_title[1])
    ordered_content_list = medialib_db.album.get_album_content(
        album_id, connection=db_connection
    )

    items_count = 0
    itemslist = [
        {
            "icon": flask.url_for("static", filename="images/updir_icon.svg"),
            "name": "back to file browser",
            "lazy_load": False,
        }
    ]
    itemslist[0]["link"] = "/"
    items_count += 1

    content_list = _get_content_list(
        db_connection, ordered_content_list, items_count
    )
    itemslist.extend(content_list)

    template_kwargs = {
        "title": title,
        "_glob": None,
        "url": flask.request.base_url,
        "args": [],
        "medialib_sorting": shared_code.get_medialib_sorting_constants_for_template(),
        "medialib_hidden_filtering": medialib_db.files_by_tag_search.HIDDEN_FILTERING,
        "enable_external_scripts": shared_code.enable_external_scripts,
    }

    return flask.render_template(
        "index.html",
        itemslist=itemslist,
        dirmeta=json.dumps([]),
        filemeta=json.dumps(content_list),
        page=0,
        max_pages=0,
        items_per_page=flask.session["items_per_page"],
        thumbnail=shared_code.get_thumbnail_size(
            orientation=shared_code.OrientationEnum.VERTICAL
        ),
        **template_kwargs
    )


@album_blueprint.route("/show")
@shared_code.login_validation
def show_album_gallery():
    db_connection = medialib_db.common.make_connection()

    title = "Album Gallery"
    raw_content_list = medialib_db.album.get_album_covers(db_connection)

    items_count = 0
    itemslist = [
        {
            "icon": flask.url_for("static", filename="images/updir_icon.svg"),
            "name": "back to file browser",
            "lazy_load": False,
        }
    ]
    itemslist[0]["link"] = "/"
    items_count += 1

    content_list = filesystem.browse.db_content_processing(
        raw_content_list,
        items_count,
        filesystem.browse.InfoExtractor.MedialibAlbumGalleryExtractor,
    )
    itemslist.extend(content_list)

    template_kwargs = {
        "title": title,
        "_glob": None,
        "url": flask.request.base_url,
        "args": [],
        "medialib_sorting": shared_code.get_medialib_sorting_constants_for_template(),
        "medialib_hidden_filtering": medialib_db.files_by_tag_search.HIDDEN_FILTERING,
        "enable_external_scripts": shared_code.enable_external_scripts,
    }

    return flask.render_template(
        "index.html",
        itemslist=itemslist,
        dirmeta=json.dumps([]),
        filemeta=json.dumps([]),
        page=0,
        max_pages=0,
        items_per_page=flask.session["items_per_page"],
        thumbnail=shared_code.get_thumbnail_size(
            scale=1.5, orientation=shared_code.OrientationEnum.VERTICAL
        ),
        **template_kwargs
    )


@album_blueprint.route("/get-album.json", defaults={"album_id": None})
@album_blueprint.route("/get-album/id<int:album_id>.json")
@shared_code.login_validation
def medialib_get_album(album_id: int):
    db_connection = medialib_db.common.make_connection()

    ordered_content_list = None
    if album_id is not None:
        ordered_content_list = medialib_db.album.get_album_content(
            album_id, connection=db_connection
        )
    else:
        set_tag_id = flask.request.args.get(
            "set_tag_id", type=int, default=None
        )
        artist_tag_id = flask.request.args.get(
            "artist_tag_id", type=int, default=None
        )
        if set_tag_id is None or artist_tag_id is None:
            flask.abort(404)
        ordered_content_list = medialib_db.get_album_related_content(
            set_tag_id, artist_tag_id, connection=db_connection
        )

    items_count = 0
    content_list = _get_content_list(
        db_connection, ordered_content_list, items_count
    )
    return flask.Response(
        json.dumps(content_list), mimetype="application/json"
    )


@album_blueprint.route("/edit", defaults={"album_id": None})
@album_blueprint.route("/edit/id<int:album_id>")
@shared_code.login_validation
def show_album_edit_from(album_id: int):
    db_connection = medialib_db.common.make_connection()

    ordered_content_list: (
        list[medialib_db.album.OptionallyOrderedContent]
        | list[medialib_db.album.OrderedContent]
        | None
    ) = None
    title = ""
    if album_id is not None:
        ordered_content_list = medialib_db.album.get_album_content(
            album_id, connection=db_connection
        )
        title = medialib_db.album.get_album_title(album_id, db_connection)
    else:
        set_tag_id = flask.request.args.get(
            "set_tag_id", type=int, default=None
        )
        artist_tag_id = flask.request.args.get(
            "artist_tag_id", type=int, default=None
        )
        if set_tag_id is None or artist_tag_id is None:
            flask.abort(404)
        ordered_content_list = medialib_db.album.get_album_related_content(
            set_tag_id, artist_tag_id, connection=db_connection
        )
        set_name = medialib_db.get_tag_name_by_id(db_connection, set_tag_id)
        artist = medialib_db.get_tag_name_by_id(db_connection, artist_tag_id)
        title = "{} by {}".format(set_name, artist)

    items_count = 0
    if ordered_content_list is None:
        flask.abort(404)
    content_list = _get_content_list(
        db_connection, ordered_content_list, items_count
    )
    return flask.render_template(
        "album_order_edit_blank.html",
        content_list=json.dumps(content_list),
        thumbnail=shared_code.get_thumbnail_size(),
        title=title,
        tag_ids=json.dumps({"set_id": set_tag_id, "artist_id": artist_tag_id}),
    )


@album_blueprint.route("/update", methods=["POST"])
@shared_code.login_validation
def album_commit():
    data = flask.request.json
    print(data)
    db_connection = medialib_db.common.make_connection()
    set_id = data["set_id"]
    artist_id = data["artist_id"]
    album_id = medialib_db.album.get_album_id(set_id, artist_id, db_connection)
    if album_id is None:
        album_id = medialib_db.album.make_album(
            set_id, artist_id, db_connection
        )
    for content in data["content_order_changes"]:
        medialib_db.album.set_album_order(
            album_id, content["id"], content["order"], db_connection
        )
    db_connection.commit()
    db_connection.close()
    return "OK"
