#!/usr/bin/env python3
# -*- coding: utf-8 -*-


class CustomDecoder:
    def get_size(self):
        raise NotImplementedError

    def decode(self):
        raise NotImplementedError


class IncorrectFileType(Exception):
    def __init__(self, decoder):
        self.decoder = decoder

    def error_msg(self):
        return "Incorrect {} file".format(self.decoder)
