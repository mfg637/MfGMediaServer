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

export function ImageViewer(props){
  let imageList = [];
  const [currentImageID, setCurrentImageID] = useState(-1);

  viewImage = function (imageID){
    setCurrentImageID(imageID);
  }

  function page_init(){
    console.log("page_init called")
    const links = document.getElementsByTagName('a'),countPhoto = 0;
    imageList = props.filemeta;

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
      {currentImageID > -1? <img src={props.filemeta[currentImageID].link}/> : null}
    </>
  )
}

let mounting_root_element = document.createElement('div')
document.getElementsByTagName('body')[0].appendChild(mounting_root_element);
const mounting_root = createRoot(mounting_root_element)
let imageViewer = <ImageViewer filemeta={filemeta} dirmeta={dirmeta} />

mounting_root.render(imageViewer)
