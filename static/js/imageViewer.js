meta_tags = document.getElementsByTagName('meta')

filemeta = null
dirmeta = null


for (let i = 0; i < meta_tags.length; i++) {
    if (meta_tags[i].getAttribute('name') === 'filemeta_json') {
        filemeta = JSON.parse(meta_tags[i].getAttribute('content'))
    }
    else if (meta_tags[i].getAttribute('name') === 'dirmeta_json') {
        dirmeta = JSON.parse(meta_tags[i].getAttribute('content'))
    }
}

dpi_scale_coef = window.devicePixelRatio;

FILETYPE = 0;
DIRTYPE = 1;


var imageViewer = new ImageViewer();
imageViewer.init(filemeta)


function ImageViewer() {
  var container, image, img_tag, prev, next, caption;
  var id,imagelist,loadViewportSizePhoto;
  var default_click_handler,
      default_hide_controls_click_handler,
      default_goto_url_click_handler,
      default_open_video_click_handler,
      doubleclick_goto_url_click_handler;
  var jscontainer = document.createElement('div');
  jscontainer.id = 'writeCodeJS'
  jscontainer.innerHTML
    = '<link rel="stylesheet" type="text/css" href="/static/css/imgbox.css"/>';
  document.getElementsByTagName('body')[0].appendChild(jscontainer);

  this.init = function (list) {
    var links = document.getElementsByTagName('a'),countPhoto = 0;
    imagelist = list;

    links = document.querySelectorAll(".item")
    for (let i=0; i<filemeta.length; i++){
        link = links[filemeta[i].item_index].getElementsByTagName('a')[0];
        links[filemeta[i].item_index].imageID = i;
        link.imageID = i;
        links[filemeta[i].item_index].ftype = FILETYPE;
        link.ftype = FILETYPE;
        if ((filemeta[i].type === "picture") || (filemeta[i].type === "image")){
            link.onclick=function(){
                imageViewer.watchPhoto(this.imageID);
                return false;
            }
        }else if (filemeta[i].type === "video"){
            link.onclick=function(){
                new RainbowVideoPlayer(filemeta[this.imageID]);
                return false;
            }
        }
        else if (filemeta[i].type === "DASH"){
            link.onclick=function(){
                new RainbowDASHVideoPlayer(filemeta[this.imageID]);
                return false;
            }
        }
    }
    for (let i=0; i<dirmeta.length; i++){
        links[dirmeta[i].item_index].imageID = i;
        links[dirmeta[i].item_index].ftype = DIRTYPE;
    }
    console.log("init done");

  }

    default_hide_controls_click_handler = function(){
        container.classList.toggle('hideControls');
    }

    default_goto_url_click_handler = function(){
        document.location.href = imagelist[id].link;
    }

    doubleclick_goto_url_click_handler = function(){
        window.open(imagelist[id].link, '_blank');
    }

    default_open_video_click_handler = function(){
        new RainbowVideoPlayer(imagelist[id]);
    }

    default_open_dash_video_click_handler = function(){
        new RainbowDASHVideoPlayer(imagelist[id]);
    }

  this.watchPhoto = function(photoID) {
    clearTimeout(loadViewportSizePhoto);
    id=photoID;
    if (image) {
      replaceImage(this);
    } else {
      createImage(this);
    }
  }
  replaceImage = function() {
    container.classList.add('load');

    // clear sources
    while (image.firstChild) {
      image.removeChild(image.lastChild);
    }

    img_tag = document.createElement("img");
    if (imagelist[id].suffix === '.gif')
        img_tag.src = imagelist[id].link;
    else if (imagelist[id].custom_icon){
        img_tag.src = imagelist[id].icon
    }
    else {
      let compatibility_level = Number(localStorage.getItem("clevel"));
      if (imagelist[id].suffix === ".avif" && compatibility_level <= 1) {
        source_2 = document.createElement("source");
        source_2.srcset = imagelist[id].link;
        source_2.type = "image/avif";
        image.appendChild(source_2)
      }
      let format = 'avif';
      if (compatibility_level === 3) {
        format = 'webp';
      } else if (compatibility_level === 4) {
        format = 'jpeg'
      }
      let css_width = window.innerWidth;
      let css_height = window.innerHeight;
      let pixel_width = Math.round(css_width * window.devicePixelRatio);
      let pixel_height = Math.round(css_height * window.devicePixelRatio);
      let base32src = imagelist[id].base32path;
      let content_id = imagelist[id].content_id;
      if (content_id === null){
        img_tag.src = `/thumbnail/${format}/${pixel_width}x${pixel_height}/${base32src}?allow_origin=1`;
        thumbnail_id = "mlid" + imagelist[id].content_id
      } else {
        img_tag.src = `/medialib/thumbnail/${format}/${pixel_width}x${pixel_height}/id${content_id}?allow_origin=1`;
      }

      img_tag.style.maxWidth = `${css_width}px`;
      img_tag.style.maxHeight = `${css_height}px`;
      image.appendChild(img_tag)
    }


    if ((imagelist[id].type=== "picture") || (imagelist[id].type=== "image"))
        default_click_handler = default_hide_controls_click_handler;
    else if (imagelist[id].type === "video")
        default_click_handler = default_open_video_click_handler;
    else if (imagelist[id].type === "DASH")
        default_click_handler = default_open_dash_video_click_handler;
    else
        default_click_handler = default_goto_url_click_handler;



    caption.innerHTML = ( +id + 1) + '/' +
                        imagelist.length;
    if (imagelist[id].name !== null)
      caption.innerHTML += '<br /><span class="title">' +
                        imagelist[id].name + '</span>';
    if (id>0) {
      prev.style.display='block';
    }else{
      prev.style.display='none';
    }
    if (id<imagelist.length-1) {
      next.style.display='block';
    }else{
      next.style.display='none';
    }
  };
  close = function() {
    clearTimeout(loadViewportSizePhoto);
    window.removeEventListener("resize",resize,false);
    window.onkeyup=null;
    image=null;
    jscontainer.removeChild(container);
    document.body.style.overflow = "";
  }
  previousPhoto = function() {
    clearTimeout(loadViewportSizePhoto);
    id--;
    replaceImage();
  }
  nextPhoto = function() {
    clearTimeout(loadViewportSizePhoto);
    id++;
    replaceImage();
  };
  function createImage() {
    container = document.createElement('div');
    container.id = 'contimgbox';
    container.classList.add('photoview-wraper');
    container.classList.add('container');
    container.classList.add('load');
    jscontainer.appendChild(container);

    object_container = document.createElement('div');
    object_container.classList.add('container');
    container.appendChild(object_container);

    document.body.style.overflow = "hidden";

    image = document.createElement('picture');
    image.id = 'i';
    image.classList.add('photo');
    object_container.appendChild(image);

    controls_container = document.createElement('div');
    controls_container.classList.add('container');
    container.appendChild(controls_container);

    close_button = document.createElement('div');
    close_button.id = 'btn';
    close_button.onclick = close;
    controls_container.appendChild(close_button);

    prev = document.createElement('div');
    prev.id = 'plink';
    prev.classList.add('photoview-left-plink-bar');
    controls_container.appendChild(prev);

    next = document.createElement('div');
    next.id = 'nlink';
    next.classList.add('photoview-right-plink-bar');
    controls_container.appendChild(next);

    caption = document.createElement('div');
    caption.classList.add('imageview-text');
    controls_container.appendChild(caption);
    controls_container.onclick = function(event){
        if (event.target === event.currentTarget){
            default_click_handler();
        }
    }
    controls_container.ondblclick = function(){
        doubleclick_goto_url_click_handler();
    }

    replaceImage();

    prev.onclick = previousPhoto;

    next.onclick = nextPhoto;

    window.onkeyup=keyControl;
    window.addEventListener("resize", resize, false);

    function keyControl (event) {
      switch(event.keyCode){
        case 27:close(); break;
        case 37:if (id > 0) {
          previousPhoto();
        };break;
        case 39:if (id < imagelist.length - 1) {
          nextPhoto();
        };break;
      }
    }

    img_tag.onload=function(){
      container.classList.remove('load');
    };
    image.onError=function(){
      alert('Error 404 '+nmb);
      close();
    }

    image.onAbort=function(){
      alert('complete = '+image.complete);
    }
  }
  function resize() {
    console.log('resize '+window.innerWidth+'x'+window.innerHeight);
    clearTimeout(loadViewportSizePhoto);
    loadViewportSizePhoto=setTimeout(replaceImage,2500);
  }
}
