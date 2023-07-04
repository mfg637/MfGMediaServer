import shared_code.enums as shared_enums
import pyimglib
import pathlib

host_name = '0.0.0.0'
port = 3709
certificate_file = ''
private_key_file = ''

allow_anonymous = True
valid_login = ""
# sha3-512
valid_password_hash_hex = ''

items_per_page = 15

pyimglib.config.jpeg_xl_tools_path = None

# pathlib.Path or None
thumbnail_cache_dir = None

# Do not change this value
ACLMMP_COMPATIBILITY_LEVEL = -1

derpibooru_dl_server = None
