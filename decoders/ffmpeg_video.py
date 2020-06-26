from PIL import Image, ImageFile
import ffmpeg
import subprocess
import io
import abc


class Video(ImageFile.ImageFile, metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def ffmpeg_format_name(self):
        pass

    _close_exclusive_fp_after_loading = False

    def _open(self):
        self._exclusive_fp = None
        ImageFile._exclusive_fp = None
        self._current_frame = 0

        data = ffmpeg.probe(self.filename)

        if data['format']['format_name'] != self.ffmpeg_format_name():
            raise SyntaxError("not a {} file".format(self.format))

        video = None
        for stream in data['streams']:
            if stream['codec_type'] == "video":
                video = stream
        print(video)
        print('avg_frame_rate', video['avg_frame_rate'])
        fps=None
        if video['avg_frame_rate'] == "0/0":
            fps = eval(video['r_frame_rate'])
        else:
            fps = eval(video['avg_frame_rate'])
        self.info['duration'] = int(round(1 / fps * 1000))
        self._size = (video["width"], video["height"])
        self.mode = "RGB"
        try:
            self.size = self._size
        except AttributeError:
            size = self._size
            self.tile = [
                ("raw", (0, 0) + self._size, 0, (self.mode, 0, 1))
            ]
        else:
            size =  self.size
            self.tile = [
                ("raw", (0, 0) + self.size, 0, (self.mode, 0, 1))
            ]

        commandline = ['ffmpeg',
                       '-i', self.filename,
                       '-f', 'image2pipe',
                       '-pix_fmt', 'rgb24',
                       '-an',
                       '-r', str(fps),
                       '-vcodec', 'rawvideo', '-']
        self.process = subprocess.Popen(commandline, stdout=subprocess.PIPE)
        self._frame_size = size[0]*size[1]*3
        self.loaded_frames = 0
        self.info['duration_of_video'] = float(data['format']['duration'])

        if 30 >= self.info['duration_of_video']:
            self._exclusive_fp = None
            self.info['loop'] = 0
            self.raw_data_len = self._frame_size*2
            buffer = self.process.stdout.read(self.raw_data_len)
            self.fp = io.BytesIO(buffer)
            self.loaded_frames += 2
        else:
            self.info['loop'] = 1
            self.raw_data_len = self._frame_size
            self.fp = io.BytesIO(self.process.stdout.read(self.raw_data_len))
            self.process.stdout.close()
        self._n_frames = self.raw_data_len // self._frame_size

    @property
    def n_frames(self):
        return self._n_frames

    @property
    def is_animated(self):
        return self._n_frames > 1

    def seek(self, frame):
        if self.process.poll() is not None and frame >= self._n_frames or frame < 0:
            raise EOFError
        elif self.process.poll() is None:
            while (self.loaded_frames <= frame):
                buffer = self.process.stdout.read(self._frame_size)
                if len(buffer)>0:
                    self.fp.write(buffer)
                    self.loaded_frames += 1
                    self.raw_data_len += self._frame_size
                else:
                    self.process.terminate()
                    self.process.stdout.close()
                    raise EOFError

        self.tile = [
            ("raw", (0, 0) + self.size, self._frame_size * frame, (self.mode, 0, 1))
        ]
        self.load()

        self._current_frame = frame

    def tell(self):
        return self._current_frame

    def load(self):
        "Same as ImageFile. Just remove self.fp = None command"

        pixel = Image.Image.load(self)

        if self.tile is None:
            raise IOError("cannot load this image")
        if not self.tile:
            return pixel

        readonly = 0

        read = self.fp.read

        seek = self.fp.seek

        self.load_prepare()
        err_code = -3  # initialize to unknown error

        # sort tiles in file order
        self.tile.sort(key=ImageFile._tilesort)

        for decoder_name, extents, offset, args in self.tile:
            decoder = Image._getdecoder(self.mode, decoder_name,
                                        args, self.decoderconfig)
            try:
                seek(offset)
                decoder.setimage(self.im, extents)
                if decoder.pulls_fd:
                    decoder.setfd(self.fp)
                    status, err_code = decoder.decode(b"")
                else:
                    b = b""
                    while True:
                        s = read(self.decodermaxblock)

                        b = b + s
                        n, err_code = decoder.decode(b)
                        if n < 0:
                            break
                        b = b[n:]
            finally:
                # Need to cleanup here to prevent leaks
                decoder.cleanup()

        self.tile = []
        self.readonly = readonly


        if not ImageFile.LOAD_TRUNCATED_IMAGES and err_code < 0:
            # still raised if decoder fails to return anything
            ImageFile.raise_ioerror(err_code)

        return Image.Image.load(self)