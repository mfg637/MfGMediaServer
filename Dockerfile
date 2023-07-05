FROM node:20 AS frontend-build
WORKDIR /app
COPY package.json yarn.lock ./
RUN yarn install
COPY frontend-src ./frontend-src
COPY webpack.config.js ./webpack.config.js
COPY babel.config.js ./babel.config.js
#RUN yarn run build
RUN yarn webpack --mode production


FROM python:3.11-bookworm
WORKDIR /app
LABEL authors="mfg637"


RUN apt-get update && apt-get install -y \
    ffmpeg dav1d libavif-bin libjpeg-tools libjxl-tools librsvg2-bin \
    && rm -rf /var/lib/apt/lists/*

COPY python-dependencies.txt .
RUN pip install --no-cache-dir -r python-dependencies.txt

COPY --from=frontend-build /app/static/dist /app/static/dist
COPY config-blank.py /app/config.py
COPY medialib_db/config-example.py /app/medialib-db/config.py
COPY . /app

RUN mkdir "/app/logs"

CMD ["python", "./server.py", "/mnt"]
