style_tag = document.createElement('link');
style_tag.type = 'text/css';
style_tag.rel = 'stylesheet';
style_tag.href="/static/css/videoplayer.css";
body_tag = document.getElementsByTagName('body')[0]
body_tag.appendChild(style_tag);

	function fixEvent(e) {
		e = e || window.event;
		if (!e.target) e.target = e.srcElement;
		if (e.pageX == null && e.clientX != null ) {
    		var html = document.documentElement;
   			var body = document.body;
			e.pageX = e.clientX + (html.scrollLeft || body && body.scrollLeft || 0);
			e.pageX -= html.clientLeft || 0;
			e.pageY = e.clientY + (html.scrollTop || body && body.scrollTop || 0);
			e.pageY -= html.clientTop || 0;
		}
		if (!e.which && e.button) {
			e.which = e.button & 1 ? 1 : ( e.button & 2 ? 3 : ( e.button & 4 ? 2 : 0 ) )
		}
		return e;
	}
	function getCoords(elem) {
		var box = elem.getBoundingClientRect();
		var body = document.body;
		var docElem = document.documentElement;
		var scrollTop = window.pageYOffset || docElem.scrollTop || body.scrollTop;
		var scrollLeft = window.pageXOffset || docElem.scrollLeft || body.scrollLeft;
		var clientTop = docElem.clientTop || body.clientTop || 0;
		var clientLeft = docElem.clientLeft || body.clientLeft || 0;
		var top  = box.top +  scrollTop - clientTop;
		var left = box.left + scrollLeft - clientLeft;
		return { top: Math.round(top), left: Math.round(left) };
	}

function Scrollbar(root){
	var _root = root;
	var paused = null;
	var wrapper_for_slider = document.createElement('div'),
		scrollbar = document.createElement('div'),
		bufferRanges = document.createElement('div'),
		wachedRange = document.createElement('div'),
		scrollButton = document.createElement('span');
	var pixelsPerValue = null;
	var newLeft = null;
	wrapper_for_slider.classList.add('slider-wrapper');
	wrapper_for_slider.appendChild(scrollbar);
	scrollbar.classList.add('slider-line');
	scrollbar.cntxt=this;
	scrollbar.appendChild(bufferRanges);
	//bufferRange.classList.add('bufferRange');
	wachedRange.classList.add('slider-scrool-line');
    scrollbar.appendChild(wachedRange);
	scrollbar.appendChild(scrollButton);
	scrollButton.classList.add('slider-scrool');

	
	scrollButton.ondragstart = function() { return false; };
	
	this.init = function(){
		pixelsPerValue=scrollbar.clientWidth-scrollButton.clientWidth;
	}
	
    this.appendTo = function(elem){
        elem.appendChild(wrapper_for_slider);
    }
    
    this.setVideoSliderValue = function(currentTime, duration){
		var playing = (currentTime/duration)*pixelsPerValue + 'px';
		scrollButton.style.left=playing;
		wachedRange.style.width=playing;
	}
	
	function dragRange(e){
		paused = root.pause();
		var thumbCoords = getCoords(scrollButton);
		var shiftX = e.pageX - thumbCoords.left;
		var sliderCoords = getCoords(scrollbar);
		e = fixEvent(e);
		newLeft = e.pageX-sliderCoords.left;
		scrollButton.style.left = newLeft + 'px';
		thumbCoords = getCoords(scrollButton);
		shiftX = e.pageX - thumbCoords.left;
		shiftY = e.pageY - thumbCoords.top;
		document.onmousemove = function(e) {
			e = fixEvent(e);
			newLeft = e.pageX - shiftX - sliderCoords.left;
			if (newLeft < 0) {
				newLeft = 0;
			}
			var rightEdge = scrollbar.offsetWidth - scrollButton.offsetWidth;
			if (newLeft > rightEdge) {
				newLeft = rightEdge;
			}
		}
		scrollButton.style.left = newLeft + 'px';
		document.onmouseup = function() {
			wachedRange.style.width=newLeft+'px';
			root.seek(newLeft/pixelsPerValue)
			document.onmousemove = document.onmouseup = null;
			root.buffer();
			if (!paused)
				root.play();
			return false;
		};
	}
	scrollbar.onmousedown = dragRange;
	
	this.setBufferRange = function(buffered, duration){
		while (bufferRanges.firstChild) {
        	bufferRanges.removeChild(bufferRanges.firstChild);
    	}
        for (i=0; i<buffered.length; i++){
            bufferRange = document.createElement('div');
            bufferRange.classList.add("bufferRange");
            start = buffered.start(i);
            end = buffered.end(i);
            bufferRange.style.left=(start/duration)*100+'%';
            bufferRange.style.width=(end-start)/duration*100+'%';
            bufferRanges.appendChild(bufferRange);
        }
	}
}

function RainbowVideoPlayer(filemeta){
	//state variables
	var muted=false,
	pixelsPerValue=0,
	durationTime=0,
	durRefleshInt,
	starBuffer=0,
	endBuffer=0;
    var _filemeta = filemeta;
    var vp8_active = false;
	this.showControlsTime = 0;

	postersrcurl=filemeta.icon;
	srcurl=filemeta.link;

	var container=document.createElement('div');
	container.classList.add('videocontainer');
	//container.classList.add('off');
    container.classList.add('popup');
	container.cntxt=this;
    body_tag.appendChild(container);
    body_tag.style.overflow="hidden";
	var videoElement = document.createElement('video'),
	loadBanner = document.createElement('div'),
	controls = document.createElement('div'),
    
    scrollbar = new Scrollbar(this),
    
	playButton = document.createElement('a'),
	span_element_in_play_button = document.createElement('span'),
	timeLabel = document.createElement('span'),
	currentTimeLabel = document.createTextNode('0:00'),
	timeDelimiter = document.createTextNode(' / '),
	durationTimeLabel = document.createTextNode('0:00'),
	fullscreenButton = document.createElement('a'),
	span_element_in_fullscreen_button = document.createElement('span'),
	muteButton = document.createElement('a'),
	span_element_in_mute_button = document.createElement('span'),
	loop_button = document.createElement('a'),
	close_btn = document.createElement('div'),
	vp8_mode_btn = document.createElement('a');
	loop_button.appendChild(document.createElement('span'))
	container.appendChild(videoElement);
	videoElement.cntxt=this;
	container.appendChild(loadBanner);
	loadBanner.classList.add('loader');
	container.appendChild(controls);
	controls.classList.add('controls');
    
	scrollbar.appendTo(controls);

	controls.appendChild(playButton);
	playButton.classList.add('play-pause_button');
	playButton.classList.add('button-icon')
	playButton.appendChild(span_element_in_play_button);
	controls.appendChild(timeLabel);
	timeLabel.classList.add('time');
	timeLabel.appendChild(currentTimeLabel);
	timeLabel.appendChild(timeDelimiter);
	timeLabel.appendChild(durationTimeLabel);
	controls.appendChild(fullscreenButton);
	fullscreenButton.classList.add('fullscreen');
	fullscreenButton.classList.add('button-icon');
	fullscreenButton.classList.add('x16-button');
	fullscreenButton.appendChild(span_element_in_fullscreen_button);
	controls.appendChild(muteButton);
	muteButton.classList.add('speacer');
	muteButton.classList.add('button-icon')
	muteButton.classList.add('x16-button');
	muteButton.cntxt=this;
	muteButton.appendChild(span_element_in_mute_button);
	loop_button.classList.add('loop-button');
	loop_button.classList.add('button-icon');
	loop_button.classList.add('x16-button');
	controls.appendChild(loop_button);
	vp8_mode_btn.innerText="VP8";
	vp8_mode_btn.classList.add("vp8_mode_btn");
    if (_filemeta.is_vp8){
        vp8_mode_btn.classList.add('active');
        vp8_active = true;
    }
	controls.appendChild(vp8_mode_btn);
	close_btn.classList.add('closebtn');
	container.appendChild(close_btn);
	if (srcurl) {videoElement.src=srcurl}
    
    close_btn.onclick = function(){
        window.removeEventListener('resize', this.start);
        body_tag.removeChild(container);
        body_tag.style.overflow="auto";
    }
    
	function formatmmss(seconds){
		var n=Math.floor(seconds%60);
		if (n<10) {return Math.floor(seconds/60)+':'+0+n;}
				else{return Math.floor(seconds/60)+':'+n;}
	}
	videoElement.onloadedmetadata=function() {this.cntxt.setDuration()}
	this.setDuration = function(){
		durationTime=videoElement.duration;
		durationTimeLabel.data=formatmmss(durationTime);
	}
	function updateCurrenTime(){
		scrollbar.setVideoSliderValue(videoElement.currentTime, durationTime);
		currentTimeLabel.data=formatmmss(videoElement.currentTime);
	}
	
	function _play(){
		videoElement.play();
		playButton.classList.add('pause');
		durRefleshInt=setInterval(updateCurrenTime, 1000/8);
	}
	
	function _pause(){
		videoElement.pause();
		playButton.classList.remove('pause');
		clearInterval(durRefleshInt);
	}
	
	this.playpause=function(){
		if(videoElement.paused){
			_play();
		}else{
			_pause();
		}
	}
	this.pause = function(){
		var paused = videoElement.paused;
		if (!paused){
			_pause();
		}
		return paused;
	}
	this.play = function(){
		var paused = videoElement.paused;
		if (paused){
			_play();
		}
	}
    playButton.onclick = this.playpause;
	this.muteTogle = function(){
		if (muted) {
			muted=false;
			muteButton.classList.remove('mute');
		}else{
			muted=true;
			muteButton.classList.add('mute');
		}
	}
	
	this.toggle_loop = function(){
		if (videoElement.loop){
			videoElement.loop = false;
			loop_button.classList.remove('active');
		}else{
			videoElement.loop = true;
			loop_button.classList.add('active');
		}
	}
	loop_button.onclick = this.toggle_loop;
	this.hideControls = function(){
		container.classList.add('hide')
	}
	this.showControls = function(){
		clearTimeout(this.showControlsTime);
		if (container.classList.contains('hide')){container.classList.remove('hide')};
		this.showControlsTime=setTimeout(this.hideControls, 5000);
	}
	this.start = function() {
		container.classList.remove('off');
		muteButton.onclick = function(){this.cntxt.muteTogle()};
		container.onmousemove = function(){this.cntxt.showControls()}
		container.onmouseout=function(){clearTimeout(this.cntxt.showControlsTime)}
		container.onclick=function(event){
            if ((event.target==event.currentTarget) || (event.target == videoElement))
                this.cntxt.showControls();
        }
        scrollbar.init();
		this.showControls();
		this.playpause();
	}
	
	this.seek = function(position){
		videoElement.currentTime = position*videoElement.duration;
	}


	videoElement.onprogress=function() {
		console.log("OnProgress")
		this.cntxt.buffer()
	};
	this.buffer=function(){
		if(videoElement.buffered.length){
			scrollbar.setBufferRange(videoElement.buffered, durationTime);
		}
	}
	
	function fullscreen(){
		if (document.fullScreen||document.mozFullScreen||document.webkitIsFullScreen) {
			if(document.cancelFullScreen) {
				document.cancelFullScreen();
			} else if(document.mozCancelFullScreen) {
				document.mozCancelFullScreen();
			} else if(document.webkitCancelFullScreen) {
				document.webkitCancelFullScreen();
			}
			fullscreenButton.classList.remove('back');
		} else{
			if(container.requestFullScreen) {
				container.requestFullScreen();
			} else if(container.requestFullscreen) {
				container.requestFullscreen();
			}else if(video.container.webkitRequestFullScreen) {
				container.webkitRequestFullscreen();
			} else if(video.container.mozRequestFullScreen) {
				container.mozRequestFullScreen();
			}
			fullscreenButton.classList.add('back');
		};
	}
	fullscreenButton.onclick = fullscreen;
	container.onfullscreenchange = function(){
		scrollbar.init();
	}
	
	vp8_mode_btn.root = this;
	vp8_mode_btn.onclick = function(){
        if (!_filemeta.is_vp8){
            if (vp8_active){
                videoElement.src = _filemeta.link;
                vp8_mode_btn.classList.remove('active');
                vp8_active = false;
            }else{
                videoElement.src = "/vp8/"+_filemeta.base64path;
                vp8_mode_btn.classList.add("active");
                vp8_active = true;
            }
            this.root.start();
        }
    }
	this.start();
    window.addEventListener('resize', this.start);

}

var videoElement=document.getElementsByTagName('video'),
players=[];

for (var i = 0; i < videoElement.length; i++) {
	players[i] = new RainbowVideoPlayer(videoElement[i]);
}
