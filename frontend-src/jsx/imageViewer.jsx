import React, {useEffect} from 'react';
import { useState } from "react";
import { createRoot } from 'react-dom/client';

const meta_tags = document.getElementsByTagName('meta')

let filemeta = null
let dirmeta = null


for (let i = 0; i < meta_tags.length; i++) {
    if (meta_tags[i].getAttribute('name') === 'filemeta_json') {
        filemeta = JSON.parse(meta_tags[i].getAttribute('content'))
    }
    else if (meta_tags[i].getAttribute('name') === 'dirmeta_json') {
        dirmeta = JSON.parse(meta_tags[i].getAttribute('content'))
    }
}

const dpi_scale_coef = window.devicePixelRatio;

const FILETYPE = 0;
const DIRTYPE = 1;

let viewImage = function () {}

function Image(props) {
  let imgTag = null;

  const compatibilityLevel = Number(localStorage.getItem("clevel"));
  let sources = [];

  if (props.filemeta.suffix === ".avif" && compatibility_level <= 1) {
    sources.push(<source srcSet={props.filemeta.link} type="image/avif"/>)
  } else if (props.filemeta.suffix === ".jpg" || props.filemeta.suffix === ".jpeg"){
    sources.push(<source srcSet={props.filemeta.link} type="image/jpeg"/>)
  }

  const css_width = window.innerWidth;
  const css_height = window.innerHeight;
  const pixel_width = Math.round(css_width * window.devicePixelRatio);
  const pixel_height = Math.round(css_height * window.devicePixelRatio);
  const base32src = props.filemeta.base32path;
  const content_id = props.filemeta.content_id;

  const cssSizeLimit = {maxWidth: `${css_width}px`, maxHeight: `${css_height}px`};

  if (props.filemeta.suffix === '.gif')
    imgTag = <img src={props.filemeta.link} style={cssSizeLimit}/>
  else if (props.filemeta.custom_icon){
    imgTag = <img src={props.filemeta.icon} style={cssSizeLimit}/>
  }else {
    let format = 'avif';
    if (compatibilityLevel === 3) {
      format = 'webp';
    } else if (compatibilityLevel === 4) {
      format = 'jpeg'
    }

    if (content_id === null){
      imgTag = (<img
        src={`/thumbnail/${format}/${pixel_width}x${pixel_height}/${base32src}?allow_origin=1`}
        style={cssSizeLimit}
      />)
    } else {
      imgTag = (<img
        src={`/medialib/thumbnail/${format}/${pixel_width}x${pixel_height}/id${content_id}?allow_origin=1`}
        style={cssSizeLimit}
      />)
    }
  }

  return (
    <picture id="i" className="photo">
      {sources.map((value) => value)}
      {imgTag}
    </picture>
  )
}

function Caption(props){
  let captionText = null;
  if (props.filemeta.name !== null){
    captionText = <div className="title">{props.filemeta.name}</div>;
  }
  return (
    <div className="imageview-text">
      { props.currentImageID } / {props.imageCount}
      { captionText }
    </div>
  );
}

function ImageView(props){
  function applySideEffects(){
    document.body.style.overflow = "hidden";
  }
  function cancelSideEffects(){
    document.body.style.overflow = "auto";
  }

  useEffect(() => {
    applySideEffects()
    return () => {
      cancelSideEffects()
    };
  }, []);

  return (
    <div
      id="contimgbox"
      className=
        {(props.isLoading? "load " : "") + (props.controllsHidden ? "hideControls " : "") + "photoview-wraper container"}
    >
      <div className="container">
        <Image {...props} />
      </div>
      <div className="container">
        <div id="btn" >{/* TODO: close event handler */}</div>
        { props.currentImageID > 0 ? (
          <div id="plink" className="photoview-left-plink-bar">{/* TODO: close event handler */}</div>
        ) : null }
        { props.currentImageID < (props.imageCount - 1) ? (
          <div id="nlink" className="photoview-right-plink-bar">{/* TODO: close event handler */}</div>
        ) : null }
        <Caption {...props} />
        {/* TODO: EmptySpaceClickEventHandlers */}
      </div>
    </div>
  )
}

export function ImageViewer(props){
  const [currentImageID, setCurrentImageID] = useState(-1);

  viewImage = function (imageID){
    setCurrentImageID(imageID);
  }

  function page_init(){
    const links = document.getElementsByTagName('a'),countPhoto = 0;

    const itemLinks = document.querySelectorAll(".item")
    for (let i=0; i<props.filemeta.length; i++){
      const link = itemLinks[filemeta[i].item_index].getElementsByTagName('a')[0];
      itemLinks[props.filemeta[i].item_index].imageID = i;
      link.imageID = i;
      itemLinks[props.filemeta[i].item_index].ftype = FILETYPE;
      link.ftype = FILETYPE;
      if ((props.filemeta[i].type === "picture") || (props.filemeta[i].type === "image")){
        link.onclick=function(e){
          e.stopPropagation();
          console.log(this.imageID);
          viewImage(this.imageID);
          return false;
        }
      }else if (props.filemeta[i].type === "video"){
        link.onclick=function(){
            new RainbowVideoPlayer(props.filemeta[this.imageID]);
            return false;
        }
      }
      else if (props.filemeta[i].type === "DASH"){
        link.onclick=function(){
            new RainbowDASHVideoPlayer(props.filemeta[this.imageID]);
            return false;
        }
      }
    }
    for (let i=0; i<props.dirmeta.length; i++){
        itemLinks[props.dirmeta[i].item_index].imageID = i;
        itemLinks[props.dirmeta[i].item_index].ftype = DIRTYPE;
    }
    console.log("init done");
  }

  useEffect(() => {page_init()}, []);

  return (
    <>
      {currentImageID > -1? (
        <ImageView
          filemeta={props.filemeta[currentImageID]}
          currentImageID={currentImageID}
          imageCount={props.filemeta.length}
        />
      ) : null}
    </>
  )
}

let mounting_root_element = document.createElement('div');
mounting_root_element.id = 'writeCodeJS'
document.getElementsByTagName('body')[0].appendChild(mounting_root_element);
const mounting_root = createRoot(mounting_root_element)
let imageViewer = <ImageViewer filemeta={filemeta} dirmeta={dirmeta} />
let ImageViewerWrapper = (
  <div>
    {imageViewer}
    <link rel="stylesheet" type="text/css" href="/static/css/imgbox.css"/>
  </div>
);
mounting_root.render(ImageViewerWrapper)
