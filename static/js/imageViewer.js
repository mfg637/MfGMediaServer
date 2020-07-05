meta_tags = document.getElementsByTagName('meta')

filemeta = null

for (i=0; i<meta_tags.length;i++)
    if (meta_tags[i].getAttribute('name') === 'filemeta_json'){
        filemeta = JSON.parse(meta_tags[i].getAttribute('content'))
    }

var imageViewer = new ImageViewer();
imageViewer.init(filemeta)


function ImageViewer() {
  var photo,id,photolist,loadViewportSizePhoto,container;
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
        links[filemeta[i].item_index].photoId = i
        links[filemeta[i].item_index].onclick=function(){
          imageViewer.watchPhoto(this.photoId);
          return false;
        }
    }
    
  }
  this.watchPhoto = function(photoID) {
    clearTimeout(loadViewportSizePhoto);
    id=photoID;
    if (photo) {
      replacePhoto(this);
    } else {
      createPhoto(this);
    };
  }
  replacePhoto = function() {
    document.getElementById('contimgbox').classList.add('load');

    //URL generator
    photo.src = '/thumbnail/webp/' + 
      Math.round(window.innerWidth * window.devicePixelRatio) + 'x' + Math.round(window.innerHeight * window.devicePixelRatio) +
      '/'+ photolist[id].base64path;

    document.getElementById('text').innerHTML = ( +id + 1) + '/' +
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
    container.classList.add('load');
    jscontainer.appendChild(container);
    container.innerHTML = 
      '<div id="bacgr" class="photoview-background"></div>' +
      '<img id="i" class="photo">' +
      '<div id="plink" class="photoview-left-plink-bar">' +
        '<div class="icon"></div></div>' +
      '<div id="nlink" class="photoview-right-plink-bar">' +
        '<div class="icon"></div></div>' +
      '<div id="btn">' +
        '<div class="icon"></div></div>' +
      '<button id="clzone" class="close-photoview"></button>' +
      '<div id="text" class="photoview-text"></div>' +
      '<div class="photoview-load-anim"></div>';

    document.body.style.overflow = "hidden";
    document.getElementById('clzone').onclick = close;
    document.getElementById('btn').onclick = close;
    photo = document.getElementById('i');
    document.getElementById('bacgr').onclick = function() {
      container.classList.toggle('hideControls');
    }

    prev = document.getElementById('plink');
    next = document.getElementById('nlink');
  
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
