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
  const [isLoaded, setLoaded] = useState(false);
  const [naturalWidth, setWidth] = useState(-1);
  const [naturalHeight, setHeight] = useState(-1);

  function loaded(event){
    console.log("loaded");
    setLoaded(true);
    const imgTag = event.target;
    setWidth(imgTag.naturalWidth);
    setHeight(imgTag.naturalHeight);
    const content_aspect_ratio = imgTag.naturalWidth / imgTag.naturalHeight;
    console.log("content aspect ratio", content_aspect_ratio)
    props.contentLoaded()
  }

  let imgTagSource = null;

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

  let imageStyles = {}
  if ((props.viewMode === "fit") || !isLoaded)
    imageStyles = {maxWidth: `${css_width}px`, maxHeight: `${css_height}px`};
  else if (props.viewMode === "fill"){
    const content_aspect_ratio = naturalWidth / naturalHeight;
    const screen_aspect_ratio = css_width / css_height;
    if (content_aspect_ratio > screen_aspect_ratio){
      imageStyles = {maxHeight: `${css_height}px`};
    }else{
      imageStyles = {maxWidth: `${css_width}px`};
    }
  }
  if (props.xOffset !== null){
    imageStyles.position = "relative";
    imageStyles.left = props.xOffset;
  }

  if (props.filemeta.suffix === '.gif')
    imgTagSource = props.filemeta.link;
  else if (props.filemeta.custom_icon){
    imgTagSource = props.filemeta.icon;
  }else {
    let format = 'avif';
    if (compatibilityLevel === 3) {
      format = 'webp';
    } else if (compatibilityLevel === 4) {
      format = 'jpeg'
    }

    if (content_id === null){
      imgTagSource = `/thumbnail/${format}/${pixel_width}x${pixel_height}/${base32src}?allow_origin=1`;
    } else {
      imgTagSource = `/medialib/thumbnail/${format}/${pixel_width}x${pixel_height}/id${content_id}?allow_origin=1`;
    }
  }

  return (
    <picture id="i" className="photo">
      {sources.map((value, index) => <source src={value.src} type={value.type} key={index}/>)}
      <img src={imgTagSource} style={imageStyles} onLoad={loaded} alt={props.filemeta.name}/>
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
      { props.currentImageID + 1 } / {props.imageCount}
      { captionText }
    </div>
  );
}

function ImageView(props){
  const [xTouchPoint, setXTouchPoint] = useState(null);
  const [xOffset, setXOffset] = useState(null);
  const [cursorHidden, setCursorHidden] = useState(false)
  const [hideTimeout, setHideTimeout] = useState(null)
  function applySideEffects(){
    document.body.style.overflow = "hidden";
    document.body.style.touchAction = "pan-x pan-y";
    document.body.style.overscrollBehavior = "none";
    document.documentElement.requestFullscreen();
  }

  function cancelSideEffects(){
    document.body.style.overflow = "auto";
    document.body.style.touchAction = "auto";
    document.body.style.overscrollBehavior = "unset";
    document.exitFullscreen();
  }

  function expandButtonClick(e){
    e.stopPropagation();
    props.doSpecialAction();
  }

  function closeButtonClick(e){
    e.stopPropagation();
    props.closeViewer();
  }

  function prevButtonClick(e){
    e.stopPropagation();
    props.prevImage();
  }

  function nextButtonClick(e){
    e.stopPropagation();
    props.nextImage();
  }

  function touchStart(e){
    if (!props.isLoading)
      setXTouchPoint(e.touches[0].clientX);
    else
      setXTouchPoint(null);
  }

  function touchEnd(e){
    const css_width = window.innerWidth;
    const min_scroll_distanse = (css_width / 4);
    if (xTouchPoint !== null){
      if (xOffset > min_scroll_distanse){
        props.prevImage();
      } else if (xOffset < -min_scroll_distanse){
        props.nextImage();
      }
      setXTouchPoint(null);
      setXOffset(null);
    }
  }

  function touchMove(e){
    e.preventDefault();
    if (xTouchPoint !== null)
      setXOffset(e.touches[0].clientX - xTouchPoint);
  }

  function hideCursor(){
    setCursorHidden(true);
  }

  function mousemove(){
    clearTimeout(hideTimeout);
    setCursorHidden(false);
    setHideTimeout(setTimeout(hideCursor, 5000));
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
        {(props.isLoading? "load " : "") + (props.controllsHidden ? "hideControls " : "") +
          (props.viewMode !== "fit" ? "fill-mode " : "") + (cursorHidden ? "hide-cursor " : "")
          + "photoview-wraper container"}
    >
      <div className="container image-container" onClick={props.doSpecialAction}>
        <Image {...props} xOffset={xOffset} />
        <div className="loading-animation-wrapper">
          <div className="loading-spinner-x64">
            <div></div>
            <div></div>
            <div></div>
            <div></div>
            <div></div>
            <div></div>
            <div></div>
            <div></div>
          </div>
        </div>
      </div>
      <div
        className="container controls-container"
        onTouchStart={touchStart}
        onTouchEnd={touchEnd}
        onTouchCancel={touchEnd}
        onTouchMove={touchMove}
        onClick={props.doAction}
        onDoubleClick={props.doSpecialAction}
        onMouseMove={mousemove}
      >
        <div id="close-button" className="button square-button" onClick={closeButtonClick}></div>
        { props.currentImageID > 0 ? (
          <div id="previous-image-button" className="button" onClick={prevButtonClick}></div>
        ) : null }
        { props.currentImageID < (props.imageCount - 1) ? (
          <div id="next-image-button" className="button" onClick={nextButtonClick}></div>
        ) : null }
        <div id="expand-button" className="button square-button" onClick={expandButtonClick}></div>
        <Caption {...props} />
      </div>
    </div>
  )
}

export function ImageViewer(props){
  const [currentImageID, setCurrentImageID] = useState(-1);
  const [isLoaded, setLoaded] = useState(false);
  const [isControlsHidden, setControlsHidden] = useState(false);
  const [viewMode, setViewMode]= useState("fit");

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

  function closeViewer(){
    setCurrentImageID(-1);
  }

  function nextImage(){
    if ((currentImageID > -1) && ((currentImageID + 1) < props.filemeta.length)){
      setLoaded(false);
      setCurrentImageID(currentImageID + 1);
    }
  }

  function prevImage(){
    if (currentImageID > 0){
      setLoaded(false);
      setCurrentImageID(currentImageID - 1);
    }
  }

  const keyControl = function (event) {
    const ESCAPE_KEYCODE= 27;
    const LEFT_ARROW_KEYCODE = 37;
    const RIGHT_ARROW_KEYCODE = 39;
    switch (event.keyCode) {
      case ESCAPE_KEYCODE:
        closeViewer();
        break;
      case LEFT_ARROW_KEYCODE:
        prevImage();
        break;
      case RIGHT_ARROW_KEYCODE:
        nextImage();
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
    console.log("content loaded")
    setLoaded(true)
  }

  function doAction(){
    const currentFileMeta = props.filemeta[currentImageID];
    if ((currentFileMeta.type=== "picture") || (currentFileMeta.type=== "image")) {
      setControlsHidden(!isControlsHidden)
    }else if (currentFileMeta.type === "video") {
      new RainbowVideoPlayer(currentFileMeta);
    }else if (currentFileMeta.type === "DASH") {
      new RainbowDASHVideoPlayer(currentFileMeta);
    }else{
      document.location.href = currentFileMeta.link;
    }
  }

  function doSpecialAction(){
    const currentFileMeta = props.filemeta[currentImageID];
    if ((currentFileMeta.type=== "picture") || (currentFileMeta.type=== "image")) {
      if (viewMode === "fit"){
        setViewMode("fill");
      } else if (viewMode === "fill"){
        setViewMode("native");
      } else if (viewMode === "native"){
        setViewMode("fit");
      }
    }else {
      document.location.href = currentFileMeta.link;
    }
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
          viewMode={viewMode}
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

mounting_root.render(imageViewer)
