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
	
	this.setBufferRange = function(buffered, offset, duration){
		while (bufferRanges.firstChild) {
        	bufferRanges.removeChild(bufferRanges.firstChild);
    	}
        for (i=0; i<buffered.length; i++){
            bufferRange = document.createElement('div');
            bufferRange.classList.add("bufferRange");
            start = buffered.start(i) + offset;
            end = buffered.end(i) + offset;
            bufferRange.style.left=(start/duration)*100+'%';
            bufferRange.style.width=(end-start)/duration*100+'%';
            bufferRanges.appendChild(bufferRange);
        }
	}
}

function RainbowVideoPlayer(filemeta){
	//state variables
	this.cntxt = this;
	var muted=false,
		duration=0,
		offset = 0,
		durRefleshInt,
		vp8_active = false;
    var _filemeta = filemeta;
	this.showControlsTime = 0;

	postersrcurl=filemeta.icon;
	srcurl=filemeta.link;

	this.container=document.createElement('div');
	this.container.classList.add('videocontainer');
	//this.container.classList.add('off');
    this.container.classList.add('popup');
	this.container.cntxt=this;
    body_tag.appendChild(this.container);
    body_tag.style.overflow="hidden";
	this.videoElement = document.createElement('video');
	var loadBanner = document.createElement('div'),
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
	this.container.appendChild(this.videoElement);
	this.videoElement.cntxt=this;
	this.container.appendChild(loadBanner);
	loadBanner.classList.add('loader');
	this.container.appendChild(controls);
	controls.classList.add('controls');
    
	scrollbar.appendTo(controls);

	controls.appendChild(playButton);
	playButton.classList.add('play-pause_button');
	playButton.classList.add('button-icon');
	playButton.cntxt = this;
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
	fullscreenButton.cntxt = this;
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
	loop_button.cntxt = this;
	controls.appendChild(loop_button);
	vp8_mode_btn.innerText="VP8";
	vp8_mode_btn.classList.add("vp8_mode_btn");
    if (_filemeta.is_vp8){
        vp8_mode_btn.classList.add('active');
        vp8_active = true;
    }
	controls.appendChild(vp8_mode_btn);
	close_btn.classList.add('closebtn');
	close_btn.cntxt = this;
	this.container.appendChild(close_btn);
	if (srcurl) {this.videoElement.src=srcurl}
    
    close_btn.onclick = function(){
        window.removeEventListener('resize', this.start);
        body_tag.removeChild(this.cntxt.container);
        body_tag.style.overflow="auto";
    }
    
	function formatmmss(seconds){
		var n=Math.floor(seconds%60);
		if (n<10) {return Math.floor(seconds/60)+':'+0+n;}
				else{return Math.floor(seconds/60)+':'+n;}
	}

	this.load_metadata = function() {
		function callback(raw_data) {
			data = JSON.parse(raw_data);
			this.setDuration(parseFloat(data.format.duration));
		}
		ajaxConnect("/ffprobe_json/" + _filemeta.base32path, callback, this);
	}

	this.setDuration = function(_duration){
		duration=_duration;
		durationTimeLabel.data=formatmmss(duration);
	}

	this._updateCurrentTime = function(){
		let current_time = this.videoElement.currentTime + offset
		scrollbar.setVideoSliderValue(current_time, duration);
		currentTimeLabel.data=formatmmss(current_time);
	}
	
	function _play(){
		this.videoElement.play();
		playButton.classList.add('pause');
		durRefleshInt = setInterval(this._updateCurrentTime.bind(this), 1000/8);
	}
	
	function _pause(){
		this.videoElement.pause();
		playButton.classList.remove('pause');
		clearInterval(durRefleshInt);
	}
	
	this.playpause=function(){
		if(this.cntxt.videoElement.paused){
			_play.call(this.cntxt);
		}else{
			_pause.call(this.cntxt);
		}
	}

	this.pause = function(){
		let paused = this.videoElement.paused;
		if (!paused){
			_pause.call(this);
		}
		return paused;
	}
	this.play = function(){
		let paused = this.videoElement.paused;
		if (paused){
			_play.call(this);
		}
	}
    playButton.onclick = this.playpause;
	this.muteToggle = function(){
		if (muted) {
			this.cntxt.videoElement.muted = false;
			muted=false;
			muteButton.classList.remove('mute');
		}else{
			this.cntxt.videoElement.muted = true;
			muted=true;
			muteButton.classList.add('mute');
		}
	}
	
	this.toggle_loop = function(){
		if (this.cntxt.videoElement.loop){
			this.cntxt.videoElement.loop = false;
			this.classList.remove('active');
		}else{
			this.cntxt.videoElement.loop = true;
			this.classList.add('active');
		}
	}
	loop_button.onclick = this.toggle_loop;
	this.hideControls = function(){
		this.container.classList.add('hide')
	}
	this.showControls = function(){
		clearTimeout(this.showControlsTime);
		if (this.container.classList.contains('hide')){this.container.classList.remove('hide')};
		this.showControlsTime=setTimeout(this.hideControls.bind(this), 5000);
	}

	this.start = function() {
		this.container.classList.remove('off');
		muteButton.onclick = function(){this.cntxt.muteToggle()};
		this.container.onmousemove = function(){this.cntxt.showControls()}
		this.container.onmouseout=function(){clearTimeout(this.cntxt.showControlsTime)}
		this.container.onclick=function(event){
            if ((event.target === event.currentTarget) || (event.target === this.videoElement))
                this.cntxt.showControls();
        }
        scrollbar.init();
		this.showControls();
		this.playpause();
	}
	
	this.seek = function(position){
		let seek_position = position * duration;
		if (vp8_active && !this.videoElement.loop){
			this.videoElement.src = "/vp8/" + _filemeta.base32path + "?seek="+seek_position;
			offset = seek_position;
		}
		else {
			this.videoElement.currentTime = seek_position;
			offset = 0;
		}
	}

	this.bind_video = function () {
		this.videoElement.onloadedmetadata=function() {
			this.cntxt.setDuration(this.duration);
			this.cntxt.load_metadata.call(this.cntxt);
		}
		this.videoElement.onprogress=function() {
			console.log("OnProgress");
			this.cntxt.buffer();
		};
		this.videoElement.oncanplaythrough=function () {
			console.log("Can Play event");
			this.cntxt.play();
		}
	}
	this.bind_video();

	this.buffer=function(){
		if(this.videoElement.buffered.length){
			scrollbar.setBufferRange(this.videoElement.buffered, offset, duration);
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
			this.classList.remove('back');
		} else{
			if(this.cntxt.container.requestFullScreen) {
				this.cntxt.container.requestFullScreen();
			} else if(this.cntxt.container.requestFullscreen) {
				this.cntxt.container.requestFullscreen();
			}
			this.classList.add('back');
		}
	}
	fullscreenButton.onclick = fullscreen;
	this.container.onfullscreenchange = function(){
		scrollbar.init();
	}
	
	vp8_mode_btn.cntxt = this;
	vp8_mode_btn.onclick = function(){
		console.log(this.cntxt);
        if (!_filemeta.is_vp8){
            if (vp8_active){
                this.videoElement.src = _filemeta.link;
                vp8_mode_btn.classList.remove('active');
                vp8_active = false;
                offset = 0;
            }else{
                this.videoElement.src = "/vp8/"+_filemeta.base32path;
                vp8_mode_btn.classList.add("active");
                vp8_active = true;
            }
            this.cntxt.start();
        }
    }

    this.disable_vp8_mode = function () {
		controls.removeChild(vp8_mode_btn);
	}

	this.start();
    window.addEventListener('resize', this.start);

}

function RainbowDASHVideoPlayer(filemeta) {/*


@@@@@@@@@@@@@@@@@@@@@@@@@@@(((((((((((((((//////(((((((((((((((((((((((((@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@((((((((((((((((((&&(((((((((((((((((((((((((((((((((%@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@(((%@@****,,,,,,,**((((((((((((((((((((((((((((((((//////((((@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@***,,,,,,,,((((/(((((((((((((((((((((((/////////////////((((@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@&***,,,,,,(((((((((((((((((((((((((///////////////////////////(((#@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@***,,,,*(((/(((((((((((((((((////////////////////////////////,...,(((@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@***,,,/(((((((((((((((((////////////////////////////////////..........((((@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@***,*((((((((((((((//////////////////////////////////////,...............,(((@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@(**,(((((((((((/////////////////////////////////////////,.....................(((@@@@@@@********@@@@@@@@@@
@@@@@@@@@@@@@*///((/((((///////////////////////////////////////////...........................(((@@&***,,,,,,***@@@@@@@@
//@@@@@@@@@@*((((///////////////////////////////////////////////,...............................((***,,,,,,,,,***@@@@@@@
//@@@@@@@@@(((///////////////////////////////////////////////*...................................**,,,,,,,,,,,,***@@@@@@
//@@@@@@@(((/////////////(/////////////////////////////////....................................***,,,,,,,,,,,,,,**(@@@@@
//@@@@@#((/////////(((//////////////////////////////////,.....................................***,,,,,,,,,,,,,,,***@@@@@
//@@@@(((/////(((((///////////////////////////////////.......................................***,,,,,,,,,,,,*,,,,**@@@@@
//@@(((//((((*(((//////////////////////////////////,.......................................((**,,,,,,,,,,,,,*,,,,***@@@@
//@(((((((**,((//////////////////////////////////.......................................(((***,,,,,,,,,,,,,,*,,,,***@@@@
/*((((&@@@*(((/////////////////////////////////...../(((((((((((//**(((..............(((*,,,*,,,,,,,,,,,,,,**,,,,***@@@@
@((@@@@@@(((////////////////////////////////(((((((*,,,,,,,,,,,,,(((.............((((,,,,,,,,,,,,,,,,,,,,,,**,,,,,**@@@@
@@@@@@@@(((///////////////////////////(((((/,,,,,,,,,,,,,,,,,((((............((((*,,,,,,,,,,,,,,,,,,,,,,,,**,,,,,***@@@@
@@@@@@@((////////////////////////((((/  @@,,,,,,,,,,,,,,/((((...........(((((,,,,,,,,,,,,,,,,,,,,,,,,,,,,,*,,,,,,***@@@@
@@@@@@((////////////////////(((((&&&&&&&,@@,,,,,,,,(((((,......./(((((((,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,*,,,,,,,**@@@@@
*///@((/////////////////((((#&&&&&&&&&&&&&@@,,,,,,*/((((((((((/*,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,*,,,,,,,**(@@@@@
/*@@((///////////////(((,#&&&&&@@@@      ,&@*,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,/@@@@@@@@,,,,,,,,/@,,,*,,,,,,,,**///@@@@
/*@(((///////////((((   &&&&&@@@@@         @@,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,/@@,          @@,,%@&,,,,,,,,,,,,,***@@@@@@@
@@%((/////////(((,    *&&&&@@@@@@@         (@,,,,,,,,,,,,,,,,,,,,,,,,,,,,,@@&&&&&&%         @@,,,,,,,,,,,,,,***&@@@@@@@@
@@((///////(((*,.    ,&&&&@@@@@@@@         *@,,,,,,,,,,,,,,,,,,,,,,,,,,,@@&&&&&&&&&&&&       @@,,,,,,,,,,,,***@@@@@@@@@@
@&((////((((**,,     %%%&@@@@@@@@@@        (@,,,,,,,,,,,,,,,,,,,,,,,,,@@&@@@@      &&&&(      @@@@%(*,,,,***@@@@@@@@@@@@
@(((//(((@@/**,,    /%%%@@@@@@     @*      @#,,,,,,,,,,,,,,,,,,,,,,,*@@@@@@@         &&&/     @#,,,,,,,***@@@@@@@@@@@@@@
@(((((#@@@@/**,,    %%%%@@@@@@@    @@@@(..@@,,,,,,,,,,,,,,,,,,,,,,,%@@@@@@@/          &&&     #*,,,,***@@@@@@@@@@@@@@@@@
@(((@@@@@@@/**,,    ((((@@@@@@@@@@@@@@@@@@@%,,,,,,,,,,,,,,,,,,,,,,%@@@@@@@@@           &&,    ,*@@@@@@@@@@@@@@@@@@@@@@@@
@(@@@@@@@@@%**,,    ((((@@@@@@@@@@@@@@@@@@@,,,,,,,,,,,,,,,,,,,,,,*@@@@@@@@@@#          &&,    .,**@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@**,,,    ,,,@@@@@@@@@@@@@@@@@@,,,,,,,,,,,,,,,,,,,,,,,@@@@@@@    %@        .%%     ,***@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@***,,    ,,,#@@@@@@@@@@@@@@@@,,,,,,,,,,,,,,,,,,,,,,,%@@@@@@@@    @@@.    %%%%    .***@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@**,,,    #%%%%@@@@@@@@@@@%#,,,,,,,,,,,,,,,,,,,,,,,,@@@@@@@@@@@@@@@@@@@@%%%%     ,**&@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@%**,,,     %%%%%%%@&%%%%%,,,,,,,,*******,,,,,,,,,,,@@@@@@@@@@@@@@@@@@@%%%%.    ,**(@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@(**,,,.     %%%%%%%%%%,,,,,,,,,,,,,,,,,,,*,,,,,,,,@@@@@@@@@@@@@@@@@@((((     ,***@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@%**,,,,.           ,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,%@@@@@@@@@@@@@@@*,(((     ,**((((((((%@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@***,,,,,,,,,,,,,,,,,,,,,,*,,,,,,,,,,,,,,,,,,,,,%%%@@@@@@@@@@@*,,,,     .***%%%%%%%%%(((((((((@@@@@@@@@@
@@@@@@@@@@@@@@@@@@(**,,,,,,,,,,,,,,,,,,,,**,,,,,,,,,,,,,,,,,,,,,*%%%%%&@@&%%%%%%,      ,**///((((#%%%%%%%%%%%((((((@@@@@
//@@@@@@@@@@@@@@@@@@***,,,,,,,,,,,,,,,*,,,,,,,,,,,,,,**,,,,,,,,,, #%%%%%%%%%%/       ,*****/((((((((((#%%%%%%%%%%%(((((@
//@@@@@@@@@@@@@@@@@@@@/***,,,,,,,,,,,,**,,,,,,,,,,,,,,,,*,,,,,,,,,.               ,,*************/((((((((#%%%%%%%%%%%((
//@@@@@@@@@@@@@@@@@@@@@@%***,,,,,,,,,,,**,,,,,,,,,,,,,**,,,,,,,,,,,,,         .,,***,..,*************/(((((((%%%%%%%%%%%
//@@@@@@@@@@@@@@@@@@@@@@@@@#****,,,,,,,,,,***,,,,,****,,,,,,,,,,,,,,,,,,,,,,,,***,...........***********(((((((#%%%%%%%%
//@@@@@@@@@@@@@@@@@@@@@@@@@@@@@*****,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,****..................**********/((((((#%%%%%%
//@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@********,,,,,,,,,,,,,,,,,,,,,,,,,,,*****((//////.................*********/((((((%%%%%
//@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@***,,,,,,****************************/((((((/////////...............*********((((((#%%%
//@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@**,,,,,,,,,,,,,,,,,,,,,,,,,,,((*****((((((((///////////,.............*********(((((((%#


	RainbowVideoPlayer.call(this, filemeta);
	var url = filemeta.link;
	var player = dashjs.MediaPlayer().create();
	player.initialize(this.videoElement, url, true);
	this.videoElement = player.getVideoElement();
	this.bind_video();
	this.disable_vp8_mode();
	console.log(player);
}
