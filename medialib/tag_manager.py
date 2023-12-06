from flask import Blueprint, render_template, request, redirect, url_for
import medialib_db
import dataclasses
import shared_code

# this code is ChatGPT assisted

tag_manager_blueprint = Blueprint('tag_manager', __name__, url_prefix='/tag_manager')

@tag_manager_blueprint.route('/edit_tag', methods=['POST'])
@shared_code.login_validation
def edit_tag():
    tag_id = int(request.form['tagID'])
    tag_name = request.form['tagName']
    tag_category = request.form['tagType']

    connection = medialib_db.common.make_connection()
    medialib_db.tags_indexer.set_tag_properties(tag_id, tag_name, tag_category, connection)
    connection.close()

    # Redirect to the show_tag route with the tag_id
    return redirect(url_for('medialib.tag_manager.show_tag_properties', tag_id=tag_id))

@dataclasses.dataclass(frozen=True)
class SimpleTagProperties:
    id: int
    name: str

@dataclasses.dataclass(frozen=True)
class TagProperties:
    id: int
    name: str
    category: str
    alias_names: list[str]
    parents: list[SimpleTagProperties]

@tag_manager_blueprint.route('/show_tag/<int:tag_id>', methods=['GET'])
@shared_code.login_validation
def show_tag_properties(tag_id: int):
    connection = medialib_db.common.make_connection()
    raw_tag_info = medialib_db.tags_indexer.get_tag_info_by_tag_id(tag_id, connection)
    aliases_list = medialib_db.tags_indexer.get_tag_aliases(tag_id, connection)
    parents_list = []
    parent_id = raw_tag_info[3]
    while parent_id is not None:
        _raw_tag_info = medialib_db.tags_indexer.get_tag_info_by_tag_id(parent_id, connection)
        parents_list.append(
            SimpleTagProperties(_raw_tag_info[0], _raw_tag_info[1])
        )
        parent_id = _raw_tag_info[3]
    tag_properties = TagProperties(
        raw_tag_info[0], raw_tag_info[1], raw_tag_info[2], aliases_list, parents_list
    )
    connection.close()
    return render_template("tag_properties.html", tag=tag_properties)
