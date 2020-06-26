#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import struct
import subprocess
import threading

from . import CustomDecoder

START_OF_FRAME_MARKERS = {
    b'\xff\xc0',
    b'\xff\xc1',
    b'\xff\xc2',
    b'\xff\xc3',
    b'\xff\xc5',
    b'\xff\xc6',
    b'\xff\xc7',
    b'\xff\xc8',
    b'\xff\xc9',
    b'\xff\xca',
    b'\xff\xcb',
    b'\xff\xcd',
    b'\xff\xce',
    b'\xff\xcf',
}


def is_JPEG(file_path):
    file = open(file_path, 'rb')
    header = file.read(2)
    file.close()
    return header == b'\xff\xd8'


class JPEGDecoder(CustomDecoder.CustomDecoder):
    def __init__(self, file_path):
        self._file_path = file_path
        self._file = open(file_path, 'rb')
        header = self._file.read(2)
        if header != b'\xff\xd8':
            self._file.close()
            raise Exception
        self._size = None
        self._process = None

    def get_size(self):
        if self._size is None:
            while self._size is None:
                marker = self._file.read(2)
                # fix marker reading position
                if marker[0] != 255 and marker[1] == 255:
                    self._file.seek(-1, 1)
                    marker = self._file.read(2)
                if marker == b'\xff\x00':
                    raise ValueError("jpeg marker not found")
                if marker in START_OF_FRAME_MARKERS:
                    self._file.seek(3, 1)
                    self._size = struct.unpack('>HH', self._file.read(4))
                else:
                    frame_len = struct.unpack('>H', self._file.read(2))[0]
                    self._file.seek(frame_len-2, 1)
            #self._file.close()
        return self._size

    def load_image(self):
        self._file.seek(0, 0)
        data = self._file.read(1024)
        while len(data):
            self._process.stdin.write(data)
            data = self._file.read(1024)
        self._process.stdin.close()

    def decode(self, required_size=None):
        commandline = ['djpeg']
        if required_size is not None:
            if self._size is None:
                self.get_size()
            commandline += ['-scale']
            if (required_size[0]/self._size[1]*self._size[0]) <= required_size[1]:
                commandline += ["{}/{}".format(required_size[0], self._size[1])]
            else:
                commandline += ["{}/{}".format(required_size[1], self._size[0])]
        self._process = subprocess.Popen(
            commandline,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE
        )
        threading.Thread(target=self.load_image).start()
        return self._process

    def __del__(self):
        self._file.close()
