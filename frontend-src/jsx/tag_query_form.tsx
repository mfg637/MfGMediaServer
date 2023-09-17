import React, {MouseEventHandler, useEffect, useId} from 'react';
import { useState } from "react";
import { createRoot } from 'react-dom/client';

type TagFieldsChangeNotifier = (tags: string[]) => void;

interface TagFieldsProps{
    tags: string[],
    notifyChange: TagFieldsChangeNotifier
}

function TagFields(props: TagFieldsProps) {
    const tags = props.tags.length > 0 ? props.tags : [""];

    function changeFieldEvent(e: React.ChangeEvent<HTMLInputElement>) {
        const position = parseInt(e.currentTarget.getAttribute("data-index"));
        const value = e.target.value;
        let new_tags = [...tags];
        new_tags[position] = value;
        props.notifyChange(new_tags);
    }

    function closeFieldEvent(e: React.MouseEvent<HTMLButtonElement>) {
        e.preventDefault();
        let new_tags = tags.slice(0, tags.length - 1);
        props.notifyChange(new_tags);
    }

    function addFieldEvent(e: React.MouseEvent<HTMLButtonElement>) {
        e.preventDefault();
        let new_tags = [...tags];
        new_tags.push("")
        props.notifyChange(new_tags);
    }

    return (
        <>
            <div className="tag_fields">
                {tags.map((tagName, index) => <input
                    type="text"
                    name="tags"
                    value={tagName}
                    onChange={changeFieldEvent}
                    key={index}
                    data-index={index}
                />)
                }
            </div>
            <button
                className="close_field"
                id="ml_first_close_button"
                disabled={props.tags.length<2}
                onClick={closeFieldEvent}
            >X</button>
            <button id="ml_first_or_button" onClick={addFieldEvent}>OR</button>
        </>
    )
}

interface TagGroup {
    not: boolean,
    tags: string[],
    tags_count: number
}

type GroupChangeNotifier = (tagGroup: TagGroup, groupIndex: number) => void;

interface TagGroupFormProps{
    tagGroup: TagGroup,
    groupIndex: number,
    notifyChange: GroupChangeNotifier
}

function TagGroupForm(props: TagGroupFormProps){
    const field_id = useId();
    function notFieldChangeEvent(e: React.ChangeEvent<HTMLInputElement>) {
        let newTagGroup = {...props.tagGroup};
        newTagGroup.not = !props.tagGroup.not;
        props.notifyChange(newTagGroup, props.groupIndex);
    }

    function tagFieldChangeEvent(tags: string[]) {
        let newTagGroup = {...props.tagGroup};
        newTagGroup.tags = tags;
        newTagGroup.tags_count = tags.length;
        props.notifyChange(newTagGroup, props.groupIndex)
    }

    return (
        <div className="field">
            <input
                type="checkbox"
                name="not"
                value="1"
                id={field_id}
                defaultChecked={props.tagGroup.not}
                onChange={notFieldChangeEvent}
            />
            <input type="hidden" name="not" value="0" id="not_1_hidden" disabled={props.tagGroup.not}/>
            <input className="counter" type="hidden" name="tags_count" value={props.tagGroup.tags.length} />
            <label htmlFor={field_id}>NOT</label>
            <TagFields tags={props.tagGroup.tags} notifyChange={tagFieldChangeEvent}/>
        </div>
    )
}

enum MedialibSortingMode{
    DATE_DECREASING = 1,
    DATE_INCREASING,
    NO_SORT,
    RANDOM
}

enum MedialibFilteringMode{
    FILTER = 1,
    SHOW,
    ONLY_HIDDEN
}

interface TagQueryFormProps{
    tagGroups: TagGroup[],
    sortingMode: MedialibSortingMode,
    filteringMode: MedialibFilteringMode
}


const MedialibSortingLabels = [
    "date decreasing",
    "date increasing",
    "no sort",
    "random"
]

const MedialibFilteringLabels = [
    "filter",
    "show",
    "show only hidden"
]


function TagQueryForm(props: TagQueryFormProps) {

    const [tagGroups, setTagGroups] =
        useState<TagGroup[]>(
            props.tagGroups.length>0?props.tagGroups:[{not: false, tags:[""], tags_count:1}]
        );

    const [sortingMode, setSortingMode] = useState<number>(props.sortingMode);
    const [filteringMode, setFilteringMode] =
        useState<number>(props.filteringMode);

    function groupChange(tagGroup: TagGroup, groupIndex: number) {
        let newTagGroups = [...tagGroups];
        newTagGroups[groupIndex] = tagGroup;
        setTagGroups(newTagGroups);
    }

    function addNewGroup(e: React.MouseEvent<HTMLButtonElement>) {
        e.preventDefault();
        let newTagGroups = [...tagGroups];
        newTagGroups.push({not: false, tags:[""], tags_count:1});
        setTagGroups(newTagGroups);
    }

    function deleteGroup(e: React.MouseEvent<HTMLButtonElement>){
        e.preventDefault()
        let newTagGroups = tagGroups.slice(0, tagGroups.length - 1);
        setTagGroups(newTagGroups);
    }

    function sortingModeSelected(e: React.ChangeEvent<HTMLSelectElement>) {
        setSortingMode(parseInt(e.target.value));
    }

    function filteringModeSelected(e: React.ChangeEvent<HTMLSelectElement>) {
        setFilteringMode(parseInt(e.target.value));
    }

    return (
        <form className="medialib-search-form" action="/medialib/tag-search">
            Put your tags in fields below:<br/>
            <div id="fields-area">
                {
                    tagGroups.map((group, index) =>
                        <TagGroupForm tagGroup={group} groupIndex={index} key={index} notifyChange={groupChange}/>)
                }
            </div>
            <button id="medialib-add-field" onClick={addNewGroup}>AND</button><br />
            {
                tagGroups.length > 1?
                    <button id="medialib-delete-field" onClick={deleteGroup}>Delete group</button> : null
            }
            <label htmlFor="ml-sorting-order">Sort by:</label>
            <select id="ml-sorting-order" name="sorting_order" onChange={sortingModeSelected}>
                {
                    MedialibSortingLabels.map((value, key) =>
                        <option key={key} value={key + 1} selected={key === sortingMode - 1}>
                            {value}
                        </option>
                    )
                }
            </select>
            <br/>
            Hidden content
            <select id="ml-hidden_filtering" name="hidden_filtering" onChange={filteringModeSelected}>
                {
                    MedialibFilteringLabels.map((value, key) =>
                        <option key={key} value={key + 1} selected={filteringMode - 1 === key}>
                            {value}
                        </option>
                    )
                }
            </select>
            <input type="submit" value="Search in Medialib database"/>
        </form>
    )
}

interface QueryDataSerialised{
    "tags_groups": TagGroup[],
    "order_by": MedialibSortingMode,
    "hidden_filtering": MedialibFilteringMode
}

let queryData: QueryDataSerialised | null = null;
const meta_elems = document.getElementsByTagName("meta");
for (let i = 0; i < meta_elems.length; i++) {
    const metaElement = meta_elems[i];
    const dataName = metaElement.getAttribute("name")
    if (dataName === "query_data_json")
        queryData = JSON.parse(metaElement.getAttribute("content"));
}

const tagQueryForm =
    <TagQueryForm tagGroups={queryData.tags_groups}
                  sortingMode={queryData.order_by}
                  filteringMode={queryData.hidden_filtering}
    />;
const tqf_mounting_root_element = document.getElementById("medialib-tag-query-form-placeholder");
const tqf_mounting_root = createRoot(tqf_mounting_root_element);

tqf_mounting_root.render(tagQueryForm);
