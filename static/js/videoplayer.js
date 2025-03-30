body_tag = document.getElementsByTagName('body')[0]
let videoPlayer = null;


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
    this.pixelsPerValue = null;
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
        this.pixelsPerValue=scrollbar.clientWidth-scrollButton.clientWidth;
    }

    this.appendTo = function(elem){
        elem.appendChild(wrapper_for_slider);
    }

    this.setVideoSliderValue = function(currentTime, duration){
        var playing = (currentTime/duration)*this.pixelsPerValue + 'px';
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
        var mouse_up = function() {
            wachedRange.style.width=newLeft+'px';
            //this.init();
            root.seek(newLeft/this.pixelsPerValue)
            document.onmousemove = document.onmouseup = null;
            root.buffer();
            if (!paused)
                root.play();
            return false;
        };
        document.onmouseup = mouse_up.bind(this.cntxt);
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
    videoPlayer = this;
    let muted = false,
        duration = 0,
        offset = 0,
        durRefleshInt,
        vp8_active = false,
        nvenc_active = false;
    let _filemeta = filemeta;
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
    this.controls = document.createElement('div');
    let loadBanner = document.createElement('div'),

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
    this.container.appendChild(this.controls);
    this.controls.classList.add('controls');

    scrollbar.appendTo(this.controls);

    this.controls.appendChild(playButton);
    playButton.classList.add('play-pause_button');
    playButton.classList.add('button-icon');
    playButton.cntxt = this;
    playButton.appendChild(span_element_in_play_button);
    this.controls.appendChild(timeLabel);
    timeLabel.classList.add('time');
    timeLabel.appendChild(currentTimeLabel);
    timeLabel.appendChild(timeDelimiter);
    timeLabel.appendChild(durationTimeLabel);
    this.controls.appendChild(fullscreenButton);
    fullscreenButton.classList.add('fullscreen');
    fullscreenButton.classList.add('button-icon');
    fullscreenButton.classList.add('x16-button');
    fullscreenButton.cntxt = this;
    fullscreenButton.appendChild(span_element_in_fullscreen_button);
    this.controls.appendChild(muteButton);
    muteButton.classList.add('speacer');
    muteButton.classList.add('button-icon')
    muteButton.classList.add('x16-button');
    muteButton.cntxt=this;
    muteButton.appendChild(span_element_in_mute_button);
    loop_button.classList.add('loop-button');
    loop_button.classList.add('button-icon');
    loop_button.classList.add('x16-button');
    loop_button.cntxt = this;
    this.controls.appendChild(loop_button);
    vp8_mode_btn.innerText="VP8";
    vp8_mode_btn.classList.add("text_btn");
    if (_filemeta.is_vp8){
        vp8_mode_btn.classList.add('active');
        vp8_active = true;
    }
    this.controls.appendChild(vp8_mode_btn);
    close_btn.classList.add('closebtn');
    close_btn.cntxt = this;
    this.container.appendChild(close_btn);
    if (srcurl) {this.videoElement.src=srcurl}

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

    this.togglePlayPause=function(){
        if(this.cntxt.videoElement.paused){
            _play.call(this.cntxt);
        }else{
            _pause.call(this.cntxt);
        }
    }

    this.keyboardControl = function(keyEvent){
        switch (keyEvent.code) {
            case "Space":
                videoPlayer.togglePlayPause();
                break;
            case "Escape":
                videoPlayer.closePlayer();
                break;
        }
    }

    window.addEventListener("keyup", this.keyboardControl)

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
    playButton.onclick = this.togglePlayPause;
    this.toggleControlsShow = function (){
        if (this.container.classList.contains("hide")){
            this.showControls()
        }else {
            this.hideControls()
        }
    }
    this.videoElement.addEventListener("click", function (event){
        this.cntxt.toggleControlsShow();
    })
    //this.container.ondblclick = this.playpause;
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
        this.container.classList.add('hide');
        clearTimeout(this.showControlsTime);
    }

    this.showControls = function(){
        clearTimeout(this.showControlsTime);
        if (this.container.classList.contains('hide')){this.container.classList.remove('hide');}
        this.showControlsTime=setTimeout(this.hideControls.bind(this), 10000);
    }

    this.start = function() {
        this.cntxt.container.classList.remove('off');
        muteButton.onclick = function(){this.cntxt.muteToggle()};
        this.cntxt.container.onmousemove = function(){this.cntxt.showControls()}
        this.cntxt.container.onmouseout=function(){this.cntxt.hideControls()}
        this.cntxt.container.onclick=function(event){
            if ((event.target === event.currentTarget) || (event.target === this.videoElement))
                this.cntxt.showControls();
        }
        scrollbar.init();
        this.cntxt.showControls();
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

    this.reseek = function(){
        let seek_position = this.videoElement.currentTime;
        this.videoElement.currentTime = seek_position;
    }

    this.bind_video = function () {
        this.videoElement.onloadedmetadata=function() {
            this.cntxt.setDuration(this.duration);
            this.cntxt.load_metadata.call(this.cntxt);
        }
        this.videoElement.onprogress=function() {
            this.cntxt.buffer();
        };
        this.videoElement.oncanplaythrough=function () {
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

    vp8_mode_btn.cntxt = this;
    vp8_mode_btn.onclick = function(){
        if (!_filemeta.is_vp8){
            if (vp8_active){
                this.cntxt.videoElement.src = _filemeta.link;
                this.classList.remove('active');
                vp8_active = false;
                offset = 0;
            }else{
                this.cntxt.videoElement.src = "/vp8/"+_filemeta.base32path;
                this.classList.add("active");
                vp8_active = true;
            }
            this.cntxt.start();
        }
    }

    this.disable_live_transcoding_buttons = function () {
        this.controls.removeChild(vp8_mode_btn);
    }

    this.start();
    this.togglePlayPause();
    window.addEventListener('resize', this.start.bind(this));


    this.closePlayer = function (){
        this.videoElement.pause();
        this.videoElement.removeAttribute("src");
        this.videoElement.load();
        window.removeEventListener('resize', this.start);
        window.removeEventListener("keyup", this.keyboardControl)
        body_tag.removeChild(this.container);
        body_tag.style.overflow="auto";
        videoPlayer = null;
    }

    close_btn.onclick = function(){this.cntxt.closePlayer()}

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
    this.dash_js_player = dashjs.MediaPlayer().create();
    this.dash_js_player.initialize(this.videoElement, url, true);
    this.representation_filter_callback = function (representation){
        const compatibility_level = Number(localStorage.getItem("clevel"));
        console.log("compatibility_level", compatibility_level);
        let mediaCapabilitiesResponse = false;
        console.log("representation: ", representation);

        const codec_name = representation.codecs.split(".")[0];
        let is_compatible = false;
        if ("width" in representation) {
            console.log("video representation detected");
            const cl1_compatible_codecs = ["av01", "av1", "vp09", "vp9", "vp8", "avc1"];
            const cl2_compatible_codecs = ["vp09", "vp9", "vp8", "avc1"];
            const cl3_compatible_codecs = ["vp8", "avc1"];
            let is_codec_compatible = false;
            let compatible_codec_list = null;
            if (compatibility_level <= 1) {
                compatible_codec_list = cl1_compatible_codecs;
            } else if (compatibility_level === 2) {
                compatible_codec_list = cl2_compatible_codecs;
            } else if (compatibility_level >= 3) {
                compatible_codec_list = cl3_compatible_codecs;
            }
            for (const compatibleCodecListElement of compatible_codec_list) {
                if (codec_name === compatibleCodecListElement) {
                    is_codec_compatible = true;
                    break;
                }
            }

            const framerate_str = representation.frameRate.split("/");
            const framerate_number = Number(framerate_str[0]) / Number(framerate_str[1]);
            console.log("framerate_number", framerate_number);

            let fps_compatible = true;
            if ((compatibility_level >= 3) && (framerate_number > 30)) {
                fps_compatible = false;
            }else if ((compatibility_level >= 0) && (framerate_number > 60)) {
                fps_compatible = false;
            }

            const width = representation.width;
            const height = representation.height;
            let max_side = width;
            let min_side = height;

            if (height > width){
                max_side = height;
                min_side = width;
            }
            let size_compatible = false;
            if (compatibility_level >= 3){
                size_compatible = min_side <= 720 && max_side <= 1280;
            } else if (compatibility_level === 2){
                size_compatible = min_side <= 1080 && max_side <= 1920;
            }
            else {
                size_compatible = true;
            }
            console.log(
              "is_codec_compatible: ", is_codec_compatible,
              ", fps_compatible: ", fps_compatible,
              ", size_compatible: ", size_compatible
            );
            is_compatible = is_codec_compatible && fps_compatible && size_compatible;
        } else { is_compatible = true;}
        console.log("return ", is_compatible);
        return is_compatible;
    }
    this.dash_js_player.registerCustomCapabilitiesFilter(this.representation_filter_callback);
    this.videoElement = this.dash_js_player.getVideoElement();
    this.dash_js_player.cntxt=this;
    this.dash_js_player.updateSettings({
        "streaming": {
            "capabilities": {
                "useMediaCapabilitiesApi": true
            },
            "trackSwitchMode": {
                "video": "alwaysReplace"
            }
        }
    })
    console.log("config", this.dash_js_player.getSettings());
    this.dash_js_player.on(dashjs.MediaPlayer.events['PLAYBACK_ERROR'], (function (event) {
        console.log("PLAYBACK_ERROR happened", event);
        console.log("active stream: ", this.dash_js_player.getActiveStream())
        console.log("current video track: ", this.dash_js_player.getCurrentTrackFor("video"))
        console.log("available video tracks: ", this.dash_js_player.getTracksFor("video"))
    }).bind(this))
    this.bind_video();
    this.disable_live_transcoding_buttons();
}
