FROM python:3.11-bookworm
LABEL authors="mfg637"

WORKDIR /app

RUN curl -sS https://dl.yarnpkg.com/debian/pubkey.gpg | apt-key add -
RUN echo "deb https://dl.yarnpkg.com/debian/ stable main" | tee /etc/apt/sources.list.d/yarn.list

RUN apt-get update && apt-get install -y \
    curl ffmpeg dav1d libavif-bin yarn libjpeg-tools libjxl-tools librsvg2-bin \
    && rm -rf /var/lib/apt/lists/*

COPY python-dependencies.txt .
RUN pip install --no-cache-dir -r python-dependencies.txt

COPY config-blank.py /app/config.py
COPY . /app

RUN bash ./init-create-react-babel-project.sh

RUN yarn webpack --mode production

CMD ["python", "./server.py"]