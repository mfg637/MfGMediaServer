import shared_code.enums as shared_enums
import pyimglib
import pathlib

host_name = '0.0.0.0'
port = 3709
certificate_file = ''
private_key_file = ''

allow_anonymous = False
valid_login = "admin"
# sha3-512
# default password is admin. You should change it.
valid_password_hash_hex = '5a38afb1a18d408e6cd367f9db91e2ab9bce834cdad3da24183cc174956c20ce35dd39c2bd36aae907111ae3d6ada353f7697a5f1a8fc567aae9e4ca41a9d19d'

items_per_page = 15

pyimglib.config.jpeg_xl_tools_path = None

# pathlib.Path or None
thumbnail_cache_dir = None

# Do not change this value
ACLMMP_COMPATIBILITY_LEVEL = -1

derpibooru_dl_server = None
