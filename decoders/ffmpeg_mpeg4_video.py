from PIL import Image
from . import ffmpeg_video


def _accept(prefix):
    return prefix[4:12] == b"ftypisom" or prefix[4:12] == b"ftypmp42"


class WebM_Video(ffmpeg_video.Video):

    format = "MPEG4"
    format_description = "MPEG4 video file"

    def ffmpeg_format_name(self):
        return "mov,mp4,m4a,3gp,3g2,mj2"


Image.register_open(WebM_Video.format, WebM_Video, _accept)

Image.register_extension(WebM_Video.format, ".mp4")