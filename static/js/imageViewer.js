meta_tags = document.getElementsByTagName('meta')

filemeta = null

for (i=0; i<meta_tags.length;i++)
    if (meta_tags[i].getAttribute('name') === 'filemeta_json'){
        filemeta = JSON.parse(meta_tags[i].getAttribute('content'))
    }



var intersectionObserver = new IntersectionObserver(function(entries) {
  // If intersectionRatio is 0, the target is out of view
  // and we do not need to do anything.
    for (entry_index=0; entry_index<entries.length; entry_index++){
        if (entries[entry_index].intersectionRatio <= 0) continue;
        fmeta = filemeta[entries[entry_index].target.imageID]
        placeholder = entries[entry_index].target.getElementsByTagName('img')[0]
        if (((typeof fmeta)!="undefined") && (placeholder.classList.contains('placeholder'))){
            new_elem = null
            if (fmeta.sources!==null){
                picture_elem = document.createElement('picture');
                for (source_index=0; source_index<fmeta.sources.length; source_index++){
                    source_elem = document.createElement('source');
                    source_elem.srcset = fmeta.sources[source_index];
                    picture_elem.appendChild(source_elem);
                }
                img_elem = document.createElement('img');
                img_elem.src=fmeta.icon;
                picture_elem.appendChild(img_elem);
                new_elem = picture_elem;
            }else{
                img_elem = document.createElement('img');
                img_elem.src=fmeta.icon;
                new_elem = img_elem;
            }
        
            placeholder.parentNode.replaceChild(new_elem, placeholder);
        }
    }

});

    
var imageViewer = new ImageViewer();
imageViewer.init(filemeta)


function ImageViewer() {
  var container, photo, prev, next, caption;
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

    links = document.querySelectorAll("a.item")
    for (i=0; i<filemeta.length; i++){
        links[filemeta[i].item_index].imageID = i
        if (filemeta[i].type === "picture"){
            links[filemeta[i].item_index].onclick=function(){
                imageViewer.watchPhoto(this.imageID);
                return false;
            }
        }else if (filemeta[i].type === "video"){
            links[filemeta[i].item_index].onclick=function(){
                new RainbowVideoPlayer(filemeta[this.imageID]);
                return false;
            }
        }
        else if (filemeta[i].type === "DASH"){
            links[filemeta[i].item_index].onclick=function(){
                new RainbowDASHVideoPlayer(filemeta[this.imageID]);
                return false;
            }
        }
        if (filemeta[i].lazy_load)
            intersectionObserver.observe(links[filemeta[i].item_index]);
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
    if (photo) {
      replacePhoto(this);
    } else {
      createPhoto(this);
    }
  }
  replacePhoto = function() {
    container.classList.add('load');

    if (photolist[id].suffix === '.gif')
        photo.src = photolist[id].link;
    else if (photolist[id].custom_icon){
        photo.src = photolist[id].icon
    }
    else
        photo.src = '/thumbnail/webp/' + 
        Math.round(window.innerWidth * window.devicePixelRatio) + 'x' + 
        Math.round(window.innerHeight * window.devicePixelRatio) +
        '/'+ photolist[id].base32path;
    
    if (photolist[id].type === "picture")
        default_click_handler = default_hide_controls_click_handler;
    else if (photolist[id].type === "video")
        default_click_handler = default_open_video_click_handler;
    else if (photolist[id].type === "DASH")
        default_click_handler = default_open_dash_video_click_handler;
    else
        default_click_handler = default_goto_url_click_handler;



    caption.innerHTML = ( +id + 1) + '/' +
                        photolist.length + '<br /><span class="title">' + 
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
    photo=null;
    jscontainer.removeChild(container);
    document.body.style.overflow = "";
  }
  previousPhoto = function() {
    clearTimeout(loadViewportSizePhoto);
    id--;
    replacePhoto();
  }
  nextPhoto = function() {
    clearTimeout(loadViewportSizePhoto);
    id++;
    replacePhoto();
  };
  function createPhoto() {
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
    
    photo = document.createElement('img');
    photo.id = 'i';
    photo.classList.add('photo');
    object_container.appendChild(photo);
    
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
        if (event.target == event.currentTarget){
            default_click_handler();
        }
    }
    controls_container.ondblclick = function(){
        doubleclick_goto_url_click_handler();
    }
  
    replacePhoto();

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

    photo.onload=function(){
      container.classList.remove('load');
      alignPhoto();
    };
    photo.onError=function(){
      alert('Ошибка 404. Файл не найден '+nmb);
      close();
    }

    photo.onAbort=function(){
      alert('complete = '+photo.complete);
    }
  }
  function resize() {
    console.log('resize '+window.innerWidth+'x'+window.innerHeight);
    alignPhoto();
    clearTimeout(loadViewportSizePhoto);
    loadViewportSizePhoto=setTimeout(replacePhoto,2500);
  }
  function alignPhoto() {
    photo.style.margin = (container.offsetHeight - photo.offsetHeight) / 2 + 
      'px auto';
  }
}
