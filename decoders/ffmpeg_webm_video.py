from PIL import Image
from . import ffmpeg_video


def _accept(prefix):
    return prefix[:4] == b"\x1a\x45\xdf\xa3"


class WebM_Video(ffmpeg_video.Video):

    format = "WEBM"
    format_description = "WebM video file"

    def ffmpeg_format_name(self):
        return "matroska,webm"


Image.register_open(WebM_Video.format, WebM_Video, _accept)

Image.register_extension(WebM_Video.format, ".webm")
Image.register_extension(WebM_Video.format, ".mkv")