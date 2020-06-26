#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import io
import subprocess

import PIL.Image
import cairosvg

svg_tag = re.compile(r'<svg[^>]*>')
attributes = re.compile(r'[a-zA-Z\:]+\s?=\s?[\'\"][^\'\"]+[\'\"]')


def is_svg(file_path):
    file = open(file_path, 'r')
    try:
        data = file.read()
    except UnicodeDecodeError:
        file.close()
        return False
    file.close()
    return svg_tag.search(data) is not None


def get_resolution(file_path):
    file = open(file_path, 'r')
    data = file.read()
    file.close()
    svg_tag_data = svg_tag.search(data).group(0)
    svg_raw_attributes = attributes.findall(svg_tag_data)
    svg_attributes = dict()
    for raw_attribute in svg_raw_attributes:
        attribute_name, attribute_value = raw_attribute.split('=')
        if attribute_name[-1] == ' ':
            attribute_name = attribute_name[:-1]
        if attribute_value[0] == ' ':
            attribute_value = attribute_value[1:]
        if (attribute_value[0] == '\'' and attribute_value[-1] == '\'') or \
                (attribute_value[0] == '\"' and attribute_value[-1] == '\"'):
            attribute_value = attribute_value[1:-1]
        svg_attributes[attribute_name] = attribute_value
    if 'width' in svg_attributes and 'height' in svg_attributes:
        return (float(svg_attributes['width']), float(svg_attributes['height']))
    elif 'viewBox' in svg_attributes:
        values = svg_attributes['viewBox'].split(' ')
        return (float(values[2]), float(values[3]))
    else:
        return None


def decode(file_path, required_size=None):
    scale = 1
    try:
        if required_size is not None:
            width, height = get_resolution(file_path)
            if (required_size[0] / width * height) <= required_size[1]:
                scale = required_size[0] / width
            else:
                scale = required_size[1] / height
    except ValueError:
        pass
    buffer = None
    import defusedxml
    try:
        buffer = io.BytesIO(cairosvg.svg2png(url=str(file_path), scale=scale))
    except defusedxml.common.EntitiesForbidden:
        buffer = io.BytesIO(subprocess.run(
            ['rsvg-convert', '--format=png', '-z', str(scale), str(file_path)],
            capture_output=True
        ).stdout)
    return PIL.Image.open(buffer)