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

  if (props.filemeta.suffix === ".avif" && compatibilityLevel <= 1) {
    sources.push({src: props.filemeta.link, type: "image/avif"})
  } else if (props.filemeta.suffix === ".jpg" || props.filemeta.suffix === ".jpeg"){
    sources.push({src: props.filemeta.link, type: "image/jpeg"})
  }

  const css_width = window.innerWidth;
  const css_height = window.innerHeight;
  const pixel_width = Math.round(css_width * window.devicePixelRatio);
  const pixel_height = Math.round(css_height * window.devicePixelRatio);
  const base32src = props.filemeta.base32path;
  const content_id = props.filemeta.content_id;

  const cssSizeLimit = {maxWidth: `${css_width}px`, maxHeight: `${css_height}px`};

  if (props.filemeta.suffix === '.gif')
    imgTag = <img src={props.filemeta.link} style={cssSizeLimit} onLoad={props.contentLoaded} />
  else if (props.filemeta.custom_icon){
    imgTag = <img src={props.filemeta.icon} style={cssSizeLimit} onLoad={props.contentLoaded}/>
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
        onLoad={props.contentLoaded}
      />)
    } else {
      imgTag = (<img
        src={`/medialib/thumbnail/${format}/${pixel_width}x${pixel_height}/id${content_id}?allow_origin=1`}
        style={cssSizeLimit}
        onLoad={props.contentLoaded}
      />)
    }
  }

  return (
    <picture id="i" className="photo">
      {sources.map((value, index) => <source src={value.src} type={value.type} key={index}/>)}
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
      id="imageViewer"
      className=
        {(props.isLoading? "load " : "") + (props.controllsHidden ? "hideControls " : "") + "photoview-wraper container"}
    >
      <div className="container">
        <Image {...props} />
      </div>
      <div className="container" onClick={props.doAction} onDoubleClick={props.doSpecialAction}>
        <div id="close-button" onClick={props.closeViewer}></div>
        { props.currentImageID > 0 ? (
          <div id="previous-image-button" onClick={props.prevImage}></div>
        ) : null }
        { props.currentImageID < (props.imageCount - 1) ? (
          <div id="next-image-button" onClick={props.nextImage}></div>
        ) : null }
        <Caption {...props} />
      </div>
    </div>
  )
}

export function ImageViewer(props){
  const [currentImageID, setCurrentImageID] = useState(-1);
  const [isLoaded, setLoaded] = useState(false);
  const [isControlsHidden, setControlsHidden] = useState(false);

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

  function closeViewer(e){
    e.stopPropagation();
    setCurrentImageID(-1);
  }

  function nextImage(e){
    e.stopPropagation();
    if ((currentImageID > -1) && ((currentImageID + 1) < props.filemeta.length)){
      setCurrentImageID(currentImageID + 1);
    }
  }

  function prevImage(e){
    e.stopPropagation();
    if (currentImageID > 0){
      setCurrentImageID(currentImageID - 1);
    }
  }

  const keyControl = function (event) {
    console.log(event);
    const ESCAPE_KEYCODE= 27;
    const LEFT_ARROW_KEYCODE = 37;
    const RIGHT_ARROW_KEYCODE = 39;
    switch (event.keyCode) {
      case ESCAPE_KEYCODE:
        closeViewer(event);
        break;
      case LEFT_ARROW_KEYCODE:
        prevImage(event);
        break;
      case RIGHT_ARROW_KEYCODE:
        nextImage(event);
        break;
    }
  }

  useEffect(() => {
    page_init();
  }, []);

  useEffect(() => {
    window.addEventListener("keyup", keyControl);
    return () => window.removeEventListener("keyup", keyControl);
  })

  function contentLoaded(){
    setLoaded(true)
  }

  function doAction(){
    const currentFileMeta = props.filemeta[currentImageID];
    if ((currentFileMeta.type=== "picture") || (currentFileMeta.type=== "image")) {
      setControlsHidden(!isControlsHidden)
    }else if (currentFileMeta.type === "video") {
      new RainbowVideoPlayer(currentFileMeta);
    }else if (imagelist[id].type === "DASH") {
      new RainbowDASHVideoPlayer(currentFileMeta);
    }else{
      document.location.href = currentFileMeta.link;
    }
  }

  function doSpecialAction(){
    const currentFileMeta = props.filemeta[currentImageID];
    document.location.href = currentFileMeta.link;
  }

  return (
    <>
      {currentImageID > -1? (
        <ImageView
          filemeta={props.filemeta[currentImageID]}
          currentImageID={currentImageID}
          imageCount={props.filemeta.length}
          closeViewer={closeViewer}
          nextImage={nextImage}
          prevImage={prevImage}
          isLoading={!isLoaded}
          contentLoaded={contentLoaded}
          controllsHidden={isControlsHidden}
          doAction={doAction}
          doSpecialAction={doSpecialAction}
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
    <link rel="stylesheet" type="text/css" href="/static/dist/indexHTMLVisuals.css"/>
  </div>
);
mounting_root.render(ImageViewerWrapper)
