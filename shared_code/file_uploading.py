import io
import logging
import random
import string

import magic

logger = logging.getLogger(__name__)

EXTENSIONS_BY_MIME = {
    "image/jpeg": ".jpeg",
    "image/png": ".png",
    "image/webp": ".webp",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "image/avif": ".avif",
}

MOV_MIMETYPE = "video/quicktime"
MPEG4V_MIMETYPE = "video/mp4"
JPEG_MIMETYPE = "image/jpeg"
JPEG_XL_MIMETYPE = "image/jxl"
AVIF_MIMETYPE = "image/avif"
PNG_MIMETYPE = "image/png"
WEBP_MIMETYPE = "image/webp"
UNDEFINED_MIMETYPE = "application/octet-stream"
PNG_HEADER_SEQUENCE = b"\x89PNG\x0d\x0a\x1a\x0a"
MAX_TITLE_LENGTH = 63
MAX_SAMPLE_LENGTH = 2**20 * 200  # 200 MiB


def generate_filename(mime):
    title_only = "".join(
        random.choices(string.ascii_letters + string.digits, k=16)
    )
    return title_only + EXTENSIONS_BY_MIME[mime], title_only


def detect_file_type(file_buffer: io.BytesIO, request_header_mimetype):
    mime = magic.from_buffer(file_buffer.getvalue(), mime=True)
    if mime == MOV_MIMETYPE and request_header_mimetype == MPEG4V_MIMETYPE:
        mime = MPEG4V_MIMETYPE
    if mime == UNDEFINED_MIMETYPE:
        file_buffer.seek(0)
        # check PNG header
        header = file_buffer.read(8)
        if header == PNG_HEADER_SEQUENCE:
            mime = PNG_MIMETYPE
    is_image = False
    if mime.startswith("image/"):
        is_image = True
        file_type = None
        file_type = "image"
    if mime.startswith("video/"):
        file_type = "video"
    elif mime.startswith("audio/"):
        file_type = "audio"
    elif is_image:
        pass
    else:
        logger.error(f"undetected content type, mime: {mime}")
        raise Exception("undetected content type")
    return mime, file_type, is_image
