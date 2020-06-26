#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import PIL.Image
from . import jpeg, ffmpeg_webm_video, ffmpeg_mpeg4_video, webp, svg, apng


def open_image(file_path, required_size=None):
    if jpeg.is_JPEG(file_path):
        decoder = jpeg.JPEGDecoder(file_path)
        decoded_jpg = decoder.decode(required_size)
        img = PIL.Image.open(decoded_jpg.stdout)
        return img
    else:
        pil_image = None
        try:
            pil_image = PIL.Image.open(file_path)
        except PIL.Image.UnidentifiedImageError:
            if svg.is_svg(file_path):
                return svg.decode(file_path, required_size)
            else:
                raise ValueError()
        else:
            return pil_image