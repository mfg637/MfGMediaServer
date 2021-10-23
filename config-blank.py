import shared_code.enums as shared_enums
import pyimglib

host_name = 'localhost'
port = 5000
certificate_file = ''
private_key_file = ''

valid_login = ""
valid_password_hash_hex = ''

load_acceleration_method = shared_enums.LoadAcceleration.NONE
items_per_page = 1

pyimglib.config.jpeg_xl_tools_path = None

# Do not change this value
ACLMMP_COMPATIBILITY_LEVEL = -1
