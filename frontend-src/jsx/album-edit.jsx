import React from 'react';
import { createRoot } from 'react-dom';
import {postJSON} from "./ajax.jsx";


const meta_tags = document.getElementsByTagName('meta')

let content_list = null;
let tag_ids = null

for (let i = 0; i < meta_tags.length; i++) {
    if (meta_tags[i].getAttribute('name') === 'content_list') {
        content_list = JSON.parse(meta_tags[i].getAttribute('content'))
    }else if (meta_tags[i].getAttribute('name') === 'tag_ids') {
        tag_ids = JSON.parse(meta_tags[i].getAttribute('content'))
    }
}

const domContainer = document.getElementById("react-app-container");
const react_root = createRoot(domContainer);

function Thumbnail(props){
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

class ContentItem extends React.Component{
  constructor(props) {
    super(props);
    this.state = {
      current_value: typeof(this.props.album_order === "number")? String(this.props.album_order): ""
    }
    this.updateValue = this.updateValue.bind(this);
  }
  updateValue(event){
    if (event.target.value !== this.state.current_value){
      if ((event.target.value.length > 0) && isNaN(Number(event.target.value))){
          event.target.value = this.state.current_value;
          return;
      }
      const new_order = event.target.value.length ? Number(event.target.value) : null;
      this.state.current_value = event.target.value;
      this.props.orderUpdated(this.props.content_id, new_order);
    }
  }
  render() {
    return (
      <div className="content-item wrapper-accent">
        <Thumbnail {...this.props} />
        <div className="content-info">
          <div className="label">Title:</div>
          <div className="value">{this.props.name}</div>
          <div className="label">Description:</div>
          <div className="value">{this.props.description}</div>
          <div className="label">Source:</div>
          <div className="value source-id">
            <span className={this.props.origin_name}>{this.props.origin_content_id}</span>
          </div>
          <div className="label">Order:</div>
          <div className="value">
            <input
              type="number"
              defaultValue={typeof(this.props.album_order === "number")? this.props.album_order: ""}
              onBlur={this.updateValue}
            />
          </div>
        </div>
      </div>
    );
  }
}

const REALLY_LARGE_NUMBER = Math.pow(2, 64);

class ContentList extends React.Component{
  render() {
    const elementsList = this.props.sorted_array.map(
      (content_id) =>
        <ContentItem
          key={content_id}
          {...this.props.content_list[this.props.content_list_index.indexOf(content_id)]}
          orderUpdated={this.props.orderUpdated}
        />
    );
    return (
      <div className="list-wrapper">
        {elementsList}
      </div>
    );
  }
}

class Application extends React.Component{
  constructor(props) {
    super(props);
    this.state = {
      content_list_index: this.props.content_list.map(
        (contentItem) => contentItem["content_id"]
      ),
      content_order: this.props.content_list.map(
        (contentItem) => ({
          id: contentItem["content_id"],
          order: typeof(contentItem["album_order"]) === "number"? contentItem["album_order"] : null
        })
      ),
      sortedArray: []
    }
    this.state.sortedArray = this.doListSorting();
    this.updateOrder = this.updateOrder.bind(this);
    this.commitChanges = this.commitChanges.bind(this);
  }
  commitChanges(event){
    let changes_to_commit = [];
    for (let i = 0; i < this.props.content_list.length; i++) {
      if (this.state.content_order[i].order !== this.props.content_list[i].album_order)
        changes_to_commit.push(this.state.content_order[i]);
    }
    let post_data = {
      set_id: tag_ids.set_id,
      artist_id: tag_ids.artist_id,
      content_order_changes: changes_to_commit
    }
    console.log(post_data);
    postJSON(post_data, "/medialib/update_album", function (){alert("Successful commit!");});
  }
  updateOrder(content_id, order){
    let new_order = [...this.state.content_order];
    const index = this.state.content_list_index.indexOf(content_id);
    new_order[index].order = order;
    this.setState({
      content_order: new_order
    });
    this.setState({
      sortedArray: this.doListSorting()
    });
  }
  doListSorting(){
    let sortableArray = this.state.content_order.map(
      (contentItem) => ({
        id: contentItem["id"],
        order: typeof(contentItem["order"]) === "number"? contentItem["order"] : REALLY_LARGE_NUMBER
      })
    );
    sortableArray.sort(this.sortListCallback);
    return sortableArray.map((element) => element.id);
  }
  sortListCallback(a, b){
    return a.order - b.order
  }
  render() {
    return (
      <div className="application-wrapper">
        <ContentList
          content_list={this.props.content_list}
          content_list_index={this.state.content_list_index}
          sorted_array={this.state.sortedArray}
          orderUpdated={this.updateOrder}
        />
        <button onClick={this.commitChanges}>COMMIT</button>
      </div>
    )
  }
}

const application = <Application content_list={content_list}/>;
react_root.render(application);