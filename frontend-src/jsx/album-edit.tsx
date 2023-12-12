import React, {MouseEventHandler, useEffect} from 'react';
import { useState } from "react";
import { createRoot } from 'react-dom/client';
//import {postJSON} from "./ajax";

type parametlessCallback = () => void;

export async function postJSON(data: any, url: string) {
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    });

    return response.text();
  } catch (error) {
    console.error("Error:", error);
  }
}

const meta_tags = document.getElementsByTagName('meta')

interface IContent {
  album_order: number | null,
  base32path: string,
  content_id: number,
  custom_icon: boolean,
  description: string | null,
  file_name: string,
  icon: string,
  is_vp8: boolean,
  item_index: number,
  link: string,
  name: string | null,
  object_icon: boolean,
  origin_content_id: string | null,
  origin_name: string | null,
  sources: string[],
  suffix: string,
  type: 'image' | 'audio' | 'video' | 'video-loop'
}

let content_list: IContent[] = [];

interface IAlbumTagIds {
  set_id: number,
  artist_id: number
}

let tag_ids: IAlbumTagIds | null = null

for (let i = 0; i < meta_tags.length; i++) {
  if (meta_tags[i].getAttribute('name') === 'content_list') {
    content_list = JSON.parse(meta_tags[i].getAttribute('content'))
  }
  if (meta_tags[i].getAttribute('name') === 'tag_ids') {
    tag_ids = JSON.parse(meta_tags[i].getAttribute('content'))
  }
}

const domContainer = document.getElementById("react-app-container");
const react_root = createRoot(domContainer);

// React components starts here

function Thumbnail(props: IContent){
  const sources = props.sources.map(
    (sourceElement, index) => (<source key={index} srcSet={sourceElement}/>)
  );
  return (
    <a className="thumbnail-wrapper" href={props.link}>
        <picture>
            {sources}
            <img src={props.icon} alt=""/>
        </picture>
    </a>
  );
}

type UpdateOrderCallback = (content_id: number, order: number) => void;

interface IContentItemProps {
  content: IContent,
  contentOrder: ISortingOrder,
  orderUpdated: UpdateOrderCallback,
}

function ContentItem(props: IContentItemProps) {
  const [currentValue, setCurrentValue] = useState<string>(
      typeof(props.contentOrder.order) === "number"? String(props.contentOrder.order): ""
  );
  const [isEdited, setIsEdited] = useState<boolean>(false);
  function updateValue(event: React.FocusEvent<HTMLInputElement>) {
    if (isNaN(parseInt(event.target.value, 10))){
        event.target.value = currentValue;
        return;
    }
    const new_order = event.target.value.length ? Number(event.target.value) : null;
    setCurrentValue(event.target.value);
    props.orderUpdated(props.content.content_id, new_order);
    setIsEdited(false);
  }

  function allowEditing(event: React.FocusEvent<HTMLInputElement>) {
    setIsEdited(true);
  }
  
  function editValue(event: React.ChangeEvent<HTMLInputElement>) {
    const _currentValue = currentValue;
    const newValue = event.target.value;
    if (isNaN(parseInt(event.target.value, 10))){
      event.target.value = _currentValue;
      return;
    }else {
      setCurrentValue(newValue);
    }
  }

  const props_value = typeof(props.contentOrder.order) === "number"? String(props.contentOrder.order): "";
  const field_value = isEdited? currentValue : props_value;

  if (!isEdited){
    if (props_value != currentValue)
      setCurrentValue(props_value);
  }

  return (
    <div className="container-box content-item wrapper-accent">
      <Thumbnail {...props.content} />
      <div className="content-info">
        <div className="label">Title:</div>
        <div className="value">{props.content.name}</div>
        <div className="label">Description:</div>
        <div className="value">{props.content.description}</div>
        <div className="label">Source:</div>
        <div className="value source-id">
          <span className={props.content.origin_name}>{props.content.origin_content_id}</span>
        </div>
        <div className="label">Order:</div>
        <div className="value">
          <input
            type="number"
            value={field_value}
            onChange={editValue}
            onBlur={updateValue}
            onFocus={allowEditing}
          />
        </div>
      </div>
    </div>
  );
}

const REALLY_LARGE_NUMBER: number = Math.pow(2, 64);

interface ISortingOrder {
  id: number,
  order: number | null
}

interface IContentListProps {
  content_list: IContent[],
  content_list_index: number[],
  sorted_array: number[],
  content_order: ISortingOrder[],
  orderUpdated: UpdateOrderCallback,
}

function ContentList(props: IContentListProps) {
  const elementsList = props.sorted_array.map(
    (content_id) => {
      const index = props.content_list_index.indexOf(content_id);
      return <ContentItem
        key={content_id}
        content={props.content_list[index]}
        contentOrder={props.content_order[index]}
        orderUpdated={props.orderUpdated}
      />
    }
  );
  return (
    <div className="list-wrapper">
      {elementsList}
    </div>
  );
}

interface IAutosortingProps {
  copy_origin_callback: parametlessCallback
}

function Autosorting(props: IAutosortingProps) {
  function CopyIDsButtonMouseClickHandler(event: React.MouseEvent<HTMLButtonElement>) {
    props.copy_origin_callback();
  }
  function CopyIDsButtonKeyboardHandler(event: React.KeyboardEvent<HTMLButtonElement>) {
    if (event.key === 'Enter')
      props.copy_origin_callback();
  }

  return (
    <div className="container-box wrapper-accent">
      <h2>Autosorting</h2>
      <button onClick={CopyIDsButtonMouseClickHandler} onKeyDown={CopyIDsButtonKeyboardHandler}>
        Copy origin IDs (when possible)
      </button>
      <button>Auto numbering by origin IDs</button>
    </div>
  )
}

interface ApplicationProps {
  content_list: IContent[],
  tag_ids: IAlbumTagIds
}

function Application(props: ApplicationProps) {
  const [contentListIndex, setContentListIndex] = useState<number[]>(
    props.content_list.map(
      (contentItem) => contentItem.content_id
    )
  );
  const [contentOrder, setContentOrder] = useState<ISortingOrder[]>(
    props.content_list.map(
      (contentItem: IContent): ISortingOrder => ({
        id: contentItem.content_id,
        order: typeof(contentItem.album_order) === "number"? contentItem.album_order : null
      })
    )
  );
  function sortListCallback(a: ISortingOrder, b: ISortingOrder):number {
    return a.order - b.order
  }
  function doListSorting(): number[]{
    let sortableArray: ISortingOrder[] = contentOrder.map(
      (contentItem: ISortingOrder): ISortingOrder => ({
        id: contentItem.id,
        order: typeof(contentItem.order) === "number"? contentItem.order : REALLY_LARGE_NUMBER
      })
    );
    sortableArray.sort(sortListCallback);
    return sortableArray.map((element) => element.id);
  }

  const [sortedArray, setSortedArray] = useState<number[]>(
    doListSorting()
  );

  function updateOrder(content_id: number, order: number){
    let new_order: ISortingOrder[] = [...contentOrder];
    const index: number = contentListIndex.indexOf(content_id);
    new_order[index] = {id: contentOrder[index].id, order: order};
    setContentOrder(new_order);
    setSortedArray(doListSorting());
  }
  function commitChanges(){
    let changes_to_commit: ISortingOrder[] = [];
    for (let i = 0; i < props.content_list.length; i++) {
      if (contentOrder[i].order !== props.content_list[i].album_order)
        changes_to_commit.push(contentOrder[i]);
    }
    let post_data = {
      set_id: props.tag_ids.set_id,
      artist_id: props.tag_ids.artist_id,
      content_order_changes: changes_to_commit
    }
    console.log(post_data);
    postJSON(
      post_data, "/medialib/album/update"
    ).then(
      r =>alert("Successful commit!")
    ).catch(error =>alert("ERROR: " + error));
  }
  function SubmitButtonMouseClickHandler(event: React.MouseEvent<HTMLButtonElement>) {
    commitChanges();
  }
  function SubmitButtonKeyboardHandler(event: React.KeyboardEvent<HTMLButtonElement>) {
    if (event.key === 'Enter')
      commitChanges();
  }

  function copyOriginIDs(){
    let new_order: ISortingOrder[] = [];
    for (let i = 0; i < props.content_list.length; i++) {
      let content_id_int = parseInt(props.content_list[i].origin_content_id, 10);
      if (isNaN(content_id_int))
        new_order.push({id: contentOrder[i].id, order: null});
      else
        new_order.push({id: contentOrder[i].id, order: content_id_int});
    }
    setContentOrder(new_order);
    setSortedArray(doListSorting());
  }

  return (
    <div className="application-wrapper">
      <Autosorting copy_origin_callback={copyOriginIDs}/>
      <ContentList
        content_list={props.content_list}
        content_list_index={contentListIndex}
        sorted_array={sortedArray}
        content_order={contentOrder}
        orderUpdated={updateOrder}
      />
      <button onClick={SubmitButtonMouseClickHandler} onKeyDown={SubmitButtonKeyboardHandler}>COMMIT</button>
    </div>
  );
}

const application = <Application content_list={content_list} tag_ids={tag_ids}/>;
react_root.render(application);