FROM pytorch/pytorch:latest
ARG DEBIAN_FRONTEND=noninteractive

WORKDIR /

RUN apt update && apt install -y git make
RUN apt-get update && apt-get install ffmpeg libsm6 libxext6  -y
RUN git clone https://github.com/Mangio621/Mangio-RVC-Fork rvc_repo

WORKDIR /rvc_repo

RUN make install && make basev1

WORKDIR /

RUN apt install -y wget curl unzip
RUN pip install --upgrade runpod python-magic gradio

COPY swap/infer-web.py /rvc_repo/infer-web.py

RUN mkdir /rvc_serverless
COPY main.py /rvc_serverless/main.py
COPY test.py /rvc_serverless/test.py
COPY test_config.json /rvc_serverless/test_config.json
COPY modelmanager.py /rvc_serverless/modelmanager.py