import shared_enums
import pyimglib_decoders

host_name = 'localhost'
port = 5000
certificate_file = ''
private_key_file = ''

valid_login = ""
valid_password_hash_hex = ''

load_acceleration_method = shared_enums.LoadAcceleration.NONE
items_per_page = 1

pyimglib_decoders.jpeg_xl.PATH_TO_REFERENCE_DECODER = None
