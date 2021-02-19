import tempfile
import subprocess
import PIL.Image


def is_avif(file):
    file = open(file, 'rb')
    file.seek(4)
    header = file.read(8)
    file.close()
    return header == b'ftypavif'


def decode(file):
    if not is_avif(file):
        raise Exception
    tmp_file = tempfile.NamedTemporaryFile(mode='rb', delete=True, suffix='.png')
    subprocess.call(['davif', '-i', str(file), '-o', tmp_file.name])
    return PIL.Image.open(tmp_file)