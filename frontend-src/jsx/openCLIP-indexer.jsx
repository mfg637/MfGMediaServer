import React from 'react';
import { createRoot } from 'react-dom';

const domContainer = document.querySelector('#react-wrapper');
const react_root = createRoot(domContainer);


class Loader extends React.Component {
  render(){
    return (
      <div className="loader-wrapper">
        <div className="loader-label">{this.props.done}/{this.props.total}</div>
        <div className="progressbar-wrapper">
          <progress value={this.props.done} max={this.props.total}></progress>
        </div>
      </div>
    );
  }
}

class TagElement extends React.Component{
  constructor(props) {
    super(props);
    this.toggleTagState = this.toggleTagState.bind(this);
  }
  toggleTagState(){
    this.props.toggleTagState(this.props.tag_id);
  }
  render(){
    return (
      <div className="tag-wrapper">
        <input type="checkbox" onChange={this.toggleTagState}/>
        <span className="tag-name">{this.props.dataTagName} </span>
        <span className="tag-category">({this.props.category}): </span>
        <span className="tag=probability">{this.props.probability}</span>
      </div>
    );
  }
}

class TagsSelector extends React.Component {
  constructor(props) {
    super(props);
    this.submitHandler = this.submitHandler.bind(this);
  }
  submitHandler(e){
    e.preventDefault();
    this.props.sendTags();
  }
  render() {
    return (
      <div className="tag-selector-wrapper">
        <h1>Select tags</h1>
        <div>
          Several tags detected:
        </div>
        <form>
          {this.props.taglist.map(
            (tagProps) => <TagElement
              key={tagProps.tag_id}
              toggleTagState={this.props.toggleTagState}
              {...tagProps}
            />
          )}
          <input type="submit" onClick={this.submitHandler}/>
        </form>
      </div>
    );
  }
}

class AppControl extends React.Component{
  constructor(props) {
    super(props);
    this.state = {
      tagList: null,
      content_id: null,
      done: 0,
      total: 0
    };
    this.toggleTagState = this.toggleTagState.bind(this);
    this.sendTags = this.sendTags.bind(this);
  }
  componentDidMount() {
    this.updateInterval = setInterval(() => this.updateStatus(),1000);
  }
  componentWillUnmount() {
    clearInterval(this.updateInterval);
  }
  updateStatus(){
    fetch("/medialib/openCLIP-status-update").then(
      (response) => {
        if (response.ok) {
          response.json().then(
            (data) => {
              if (data.status === "loading") {
                this.setState({
                  done: data.done,
                  total: data.total
                })
              } else if (data.status === "result"){
                this.setState({
                  tagList: data.tagList,
                  content_id: data.content_id,
                });
                clearInterval(this.updateInterval);
              }
            }
          )
        } else {
          throw new Error(`HTTP error! Status: ${response.status}`);
        }
      }
    );
  }

  toggleTagState(tag_id){
    for (let i = 0; i < this.state.tagList.length; i++) {
      if (this.state.tagList[i].tag_id === tag_id){
        this.state.tagList[i].enabled = !this.state.tagList[i].enabled;
      }
    }
  }

  sendTags(){
    let tag_ids = [];
    for (const tagListElement of this.state.tagList) {
      if (tagListElement.enabled){
        tag_ids.push(tagListElement.tag_id);
      }
    }
    const result_object = {
      content_id: this.state.content_id,
      tag_ids: tag_ids
    }
    console.log(result_object);
    this.postJSON(result_object);
  }

  async postJSON(data) {
    try {
      const response = await fetch("/medialib/post-tags", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(data),
      });

      const result = await response.text();
      console.log("Success:", result);
      window.location.href =
        `${window.location.protocol}//${window.location.host}/content_metadata/mlid${this.state.content_id}`;
    } catch (error) {
      console.error("Error:", error);
    }
  }

  render(){
    if (this.state.tagList !== null){
      const img_src = `/medialib/thumbnail/webp/512x384/id${this.state.content_id}`;
      return (
        <div className="app-wrapper">
          <img src={img_src} alt="thumbnail"/>
          <TagsSelector taglist={this.state.tagList} toggleTagState={this.toggleTagState} sendTags={this.sendTags}/>
        </div>
      )
    }else {
      return (
        <div className="app-wrapper">
          <Loader done={this.state.done} total={this.state.total} />
        </div>
      );
    }
  }
}

const app = <AppControl />;
react_root.render(app);