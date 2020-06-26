#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess, json
from . import exceptions
from platform import system

if system() == "Windows":
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW


def get_output(commandline):
    global si
    if system() == "Windows":
        try:
            return subprocess.check_output(commandline, startupinfo=si)
        except OSError:
            si = None
            return subprocess.check_output(commandline)
    else:
        return subprocess.check_output(commandline)


def probe(source):
    try:
        commandline = ['ffprobe', '-loglevel', '24', '-hide_banner', '-print_format', 'json',
                       '-show_format', '-show_streams', '-show_chapters', source]
        return json.loads(str(get_output(commandline), 'utf-8'))
    except UnicodeEncodeError:
        raise exceptions.InvalidFilename(source)


def get_PPM_commandline(source: str, size=None, force=False):
    commandline = ['ffmpeg', '-loglevel', '24', '-i', source,
                   '-vframes', '1']
    if size is not None:
        commandline += ['-vf']
        if force:
            commandline += ['scale=size=' + size]
        else:
            size = size.split('x')
            commandline += [('scale=w=\'min(' + size[0] + ', iw)\':h=\'min(' + size[1] + ', ih)\'' +
                             ':force_original_aspect_ratio=decrease')]
    commandline += ['-vcodec', 'ppm', '-f', 'image2pipe', '-']
    return commandline


def get_PPM_Image(source: str, size=None, force=False):
    commandline = get_PPM_commandline(source, size, force)
    return get_output(commandline)


def get_sPPM_Stream(source: str, size=None, force=False):
    commandline = get_PPM_commandline(source, size, force)
    return subprocess.Popen(commandline, stdout=subprocess.PIPE)


# commandline = ['ffmpeg',
#                '-i', net.request_url(self.file),
#                '-f', 'image2pipe',
#                '-pix_fmt', 'rgb24',
#                '-an',
#                '-vcodec', 'rawvideo', '-']

# ffprocess = subprocess.Popen(commandline, stdout=subprocess.PIPE)
# buffer = ffprocess.stdout.read(self.width * self.height * 3)
# while len(buffer) == self.width * self.height * 3:
#     self.frames.append(
#         PIL.ImageTk.PhotoImage(PIL.Image.frombuffer("RGB", (self.width, self.height), buffer, "raw", "RGB", 0, 1)))
#     buffer = ffprocess.stdout.read(self.width * self.height * 3)
# ffprocess.stdout.close()

# if stream['codec_type'] == "video":
#     video = stream
# fps = eval(video['r_frame_rate'])
# self.delay = int(round(1 / fps * 1000))
# if self.width is None or self.height is None:
#     self.width = video["width"]
#     self.height = video["height"]