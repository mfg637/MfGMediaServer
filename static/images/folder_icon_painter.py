#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import lxml.etree
import PIL.ImageColor as Color


def rgbnorm_to_hsl(r: float, g: float, b: float):
    # r, g, b - [0; 1]
    # h - [0; 360] degrees
    # s, l - [0; 1]
    rgbmin = min(r, g, b)
    rgbmax = max(r, g, b)
    sum = rgbmin + rgbmax
    l = sum/2
    diff = rgbmax - rgbmin
    h = 0
    if rgbmax == rgbmin:
        pass
    elif rgbmax == r and g >= b:
        h = ((g - b)/diff) * 60
    elif rgbmax == r and g < b:
        h = ((g - b) / diff) * 60 + 360
    elif rgbmax == g:
        h = ((b - r) / diff) * 60 + 120
    elif rgbmax == b:
        h = ((r - g) / diff) * 60 + 240
    s = 0
    if l == 0 or rgbmax == rgbmin:
        pass
    elif 0 < l <= 0.5:
        s = diff/sum
    elif l <= 1:
        s = diff/(2-sum)
    return h, s, l


def hsl_to_rgbnorm(h, s, l):
    # h - [0; 360] degrees
    # s, l - [0; 1]
    # r, g, b - [0; 1]

    # fix incorrect values
    while h < 0:
        h = 360 + h
    while h >= 360:
        h -= 360
    if s < 0:
        s=0
    elif s>1:
        s=1
    if l<0:
        s=0
    elif l>1:
        l=1

    # algorithm
    c = (1-abs(2*l-1)) * s
    x = c * (1 - abs((h/60) % 2 - 1))
    m = l - c/2
    if 0 <= h < 60:
        return c + m, x + m, m
    elif 60 <= h < 120:
        return x + m, c + m, m
    elif 120 <= h < 180:
        return m, c + m, x + m
    elif 180 <= h < 240:
        return m, x + m, c + m
    elif 240 <= h < 300:
        return x + m, m, c + m
    else:
        return c + m, m, x + m


def hex_color(*rgb):
    return "#{}{}{}".format(*[hex(rgb[i])[2:].rjust(2, '0') for i in range(len(rgb))])


base_color_rgb = Color.getrgb("#F6D443")
base_color_hsl = rgbnorm_to_hsl(*[i / 255 for i in base_color_rgb])

stops = {
    "stop1": "#FFEA8C",
    "stop2": "#E6C229",
    "stop3": "#D6B834",
    "stop4": "#F6D443",
    "stop5": "#EDCB3A",
    "stop6": "#FFEFA8"
}

rgb_stops = dict()
for key in stops.keys():
    rgb_stops[key] = Color.getrgb(stops[key])

hsl_stops = dict()
for key in stops.keys():
    hsl_stops[key] = rgbnorm_to_hsl(*[i/255 for i in rgb_stops[key]])

hsl_stops_diff = dict()
for key in hsl_stops.keys():
    hsl_stops_diff[key] = [base_color_hsl[i] - hsl_stops[key][i] for i in range(3)]


def paint_icon(new_color_hex):

    new_color_rgb = Color.getrgb(new_color_hex)
    new_color_hsl = rgbnorm_to_hsl(*[i / 255 for i in new_color_rgb])

    new_stops = dict()

    for key in hsl_stops_diff.keys():
        new_hsl = [new_color_hsl[i] - hsl_stops_diff[key][i] for i in range(3)]
        new_rgb = [int(i * 255) for i in hsl_to_rgbnorm(*new_hsl)]
        new_stops[key] = hex_color(*new_rgb)

    return new_stops

