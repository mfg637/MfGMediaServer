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

var intersectionObserver = new IntersectionObserver(function(entries) {
  // If intersectionRatio is 0, the target is out of view
  // and we do not need to do anything.
    for (entry_index=0; entry_index<entries.length; entry_index++){
        if (entries[entry_index].intersectionRatio <= 0) continue;
        fmeta = null
        if (entries[entry_index].target.ftype === FILETYPE)
            fmeta = filemeta[entries[entry_index].target.imageID]
        else if (entries[entry_index].target.ftype === DIRTYPE)
            fmeta = dirmeta[entries[entry_index].target.imageID]
        placeholder = entries[entry_index].target.getElementsByTagName('img')[0]
        if (((typeof fmeta)!="undefined") && (placeholder.classList.contains('placeholder'))){
            new_elem = null
            if (entries[entry_index].target.ftype === FILETYPE) {
                if (fmeta.sources !== null) {
                    picture_elem = document.createElement('picture');
                    for (source_index = 0; source_index < fmeta.sources.length; source_index++) {
                        source_elem = document.createElement('source');
                        source_elem.srcset = fmeta.sources[source_index];
                        picture_elem.appendChild(source_elem);
                    }
                    img_elem = document.createElement('img');
                    img_elem.src = fmeta.icon;
                    picture_elem.appendChild(img_elem);
                    new_elem = picture_elem;
                } else {
                    img_elem = document.createElement('img');
                    img_elem.src = fmeta.icon;
                    new_elem = img_elem;
                }
            }
            else if (entries[entry_index].target.ftype === DIRTYPE){
                object_elem = document.createElement('object');
                object_elem.data = fmeta.icon+"?scale=" + dpi_scale_coef;
                new_elem = object_elem;
            }
            placeholder.parentNode.replaceChild(new_elem, placeholder);
        }
    }

});


var imageViewer = new ImageViewer();
imageViewer.init(filemeta)


function ImageViewer() {
  var container, image, img_tag, prev, next, caption;
  var id,photolist,loadViewportSizePhoto;
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
    photolist = list;

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
        if (filemeta[i].lazy_load)
            intersectionObserver.observe(links[filemeta[i].item_index]);
    }
    for (let i=0; i<dirmeta.length; i++){
        links[dirmeta[i].item_index].imageID = i;
        links[dirmeta[i].item_index].ftype = DIRTYPE;
        if (dirmeta[i].lazy_load)
            intersectionObserver.observe(links[dirmeta[i].item_index]);
    }
    console.log("init done");

  }

    default_hide_controls_click_handler = function(){
        container.classList.toggle('hideControls');
    }

    default_goto_url_click_handler = function(){
        document.location.href = photolist[id].link;
    }

    doubleclick_goto_url_click_handler = function(){
        window.open(photolist[id].link, '_blank');
    }

    default_open_video_click_handler = function(){
        new RainbowVideoPlayer(photolist[id]);
    }

    default_open_dash_video_click_handler = function(){
        new RainbowDASHVideoPlayer(photolist[id]);
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
    if (photolist[id].suffix === '.gif')
        img_tag.src = photolist[id].link;
    else if (photolist[id].custom_icon){
        img_tag.src = photolist[id].icon
    }
    else {
      if (photolist[id].suffix === ".avif" && Number(Cookies.get('clevel')) <= 1) {
        source_2 = document.createElement("source");
        source_2.srcset = photolist[id].link;
        source_2.type = "image/avif";
        image.appendChild(source_2)
      }

      scale_values = [1, 1.5, 2, 2.5, 3, 4, 6]
      function scale_base_size(width, height, scale){
        return '' + Math.round(width * scale) + 'x' +
        Math.round(height * scale)
      }

      if (Number(Cookies.get('clevel')) <= 2) {
        source_4 = document.createElement("source")
        avif_souces = []
        scale_values.forEach(
          scale_value => avif_souces.push(
            `/thumbnail/avif/${scale_base_size(window.innerWidth, window.innerHeight, scale_value)}/${photolist[id].base32path} ${scale_value}x`
          )
        );
        source_4.srcset = avif_souces.join(", ")
        source_4.type = "image/avif";
        image.appendChild(source_4)
      }

      source_1 = document.createElement("source")
      webp_souces = []
      scale_values.forEach(
        scale_value => webp_souces.push(
          `/thumbnail/webp/${scale_base_size(window.innerWidth, window.innerHeight, scale_value)}/${photolist[id].base32path} ${scale_value}x`
        )
      );
      source_1.srcset = webp_souces.join(", ")
      source_1.type = "image/webp";
      image.appendChild(source_1)
      source_3 = document.createElement("source")
      jpeg_souces = [];
      scale_values.forEach(
        scale_value => jpeg_souces.push(
          `/thumbnail/jpeg/${scale_base_size(window.innerWidth, window.innerHeight, scale_value)}/${photolist[id].base32path}  ${scale_value}x`
        )
      );
      source_3.srcset = jpeg_souces.join(", ");
      source_3.type = "image/jpeg";
      image.appendChild(source_3)
      img_tag.src = '/thumbnail/jpeg/' +
        Math.round(window.innerWidth * window.devicePixelRatio) + 'x' +
        Math.round(window.innerHeight * window.devicePixelRatio) +
        '/' + photolist[id].base32path;
      img_tag.style.maxWidth = window.innerWidth + "px";
      img_tag.style.maxHeight = window.innerHeight + "px";
      image.appendChild(img_tag)
    }


    if ((photolist[id].type=== "picture") || (photolist[id].type=== "image"))
        default_click_handler = default_hide_controls_click_handler;
    else if (photolist[id].type === "video")
        default_click_handler = default_open_video_click_handler;
    else if (photolist[id].type === "DASH")
        default_click_handler = default_open_dash_video_click_handler;
    else
        default_click_handler = default_goto_url_click_handler;



    caption.innerHTML = ( +id + 1) + '/' +
                        photolist.length;
    if (photolist[id].name !== null)
      caption.innerHTML += '<br /><span class="title">' +
                        photolist[id].name + '</span>';
    if (id>0) {
      prev.style.display='block';
    }else{
      prev.style.display='none';
    }
    if (id<photolist.length-1) {
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
        case 39:if (id < photolist.length - 1) {
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
