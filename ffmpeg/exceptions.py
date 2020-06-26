class InvalidFilename(Exception):
    def __init__(self, filename):
        self.filename = filename
