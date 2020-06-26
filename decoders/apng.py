#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import PIL.PngImagePlugin
import PIL.ImageFile
from PIL._binary import i8, i16be as i16, i32be as i32, o16be as o16, o32be as o32


def is_png(file_path):
    file = open(file_path, 'br')
    header = file.read(8)
    file.close()
    return PIL.PngImagePlugin._accept(header)


class ApngStream(PIL.PngImagePlugin.PngStream):
    def __init__(self, fp):
        PIL.PngImagePlugin.PngStream.__init__(self, fp)
        self.im_animated = False
        self.im_nframes = 1
        self.im_info['loop'] = 1
        self.frame_control = []
        self.frames_data = []
        self.duration = []

    def chunk_acTL(self, pos, length):
        s = PIL.ImageFile._safe_read(self.fp, length)
        self.im_custom_mimetype = 'image/apng'
        self.im_animated = True
        self.im_nframes = i32(s[:4])
        self.im_info['loop'] = i32(s[4:])
        return s

    def chunk_fcTL(self, pos, length):
        s = PIL.ImageFile._safe_read(self.fp, length)
        sequence_number = i32(s)
        width = i32(s[4:])
        height = i32(s[8:])
        x_offset = i32(s[12:])
        y_offset = i32(s[16:])
        delay_num = i16(s[20:])
        delay_den = i16(s[22:])
        dispose_op = i8(s[24])
        blend_op = i8(s[25])
        self.frame_control.append((
            sequence_number,
            (x_offset, y_offset, width, height),
            dispose_op,
            blend_op
        ))
        if delay_num == 0:
            self.duration.append(0)
        else:
            if delay_den == 0:
                delay_den = 100
            self.duration.append(int(round(delay_num/delay_den*1000, 0)))
        return s

    def chunk_fdAT(self, pos, length):
        s = PIL.ImageFile._safe_read(self.fp, length)
        return s


class APNG(PIL.PngImagePlugin.PngImageFile):
    def _open(self):

        if self.fp.read(8) != PIL.PngImagePlugin._MAGIC:
            raise SyntaxError("not a PNG file")

        #
        # Parse headers up to the first IDAT chunk

        self.png = ApngStream(self.fp)

        while True:

            #
            # get next chunk

            cid, pos, length = self.png.read()

            try:
                s = self.png.call(cid, pos, length)
            except EOFError:
                break
            except AttributeError:
                PIL.PngImagePlugin.logger.debug("%r %s %s (unknown)", cid, pos, length)
                s = PIL.ImageFile._safe_read(self.fp, length)

            self.png.crc(cid, s)

        #
        # Copy relevant attributes from the PngStream.  An alternative
        # would be to let the PngStream class modify these attributes
        # directly, but that introduces circular references which are
        # difficult to break if things go wrong in the decoder...
        # (believe me, I've tried ;-)

        self.mode = self.png.im_mode
        self._size = self.png.im_size
        self.info = self.png.im_info
        self._text = None
        self.tile = self.png.im_tile
        self.custom_mimetype = self.png.im_custom_mimetype
        self._n_frames = self.png.im_nframes
        self._animated = self.png.im_animated
        self.info['duration'] = self.png.duration

        if self.png.im_palette:
            rawmode, data = self.png.im_palette
            self.palette = PIL.PngImagePlugin.ImagePalette.raw(rawmode, data)

        self._PngImageFile__idat = length  # used by load_read()

    @property
    def is_animated(self):
        return self._animated

    @property
    def n_frames(self):
        return self._n_frames

    #def tell(self):
    #    return self._current_frame

    #def seek(self, frame):
    #    if frame >= len(self._apng_obj.frames):
    #        raise EOFError
    #    self.fp = io.BytesIO(self._apng_obj.frames[frame][0].to_bytes())
