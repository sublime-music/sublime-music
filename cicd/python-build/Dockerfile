FROM ubuntu:18.04

MAINTAINER sumner "https://gitlab.com/sumner"

RUN apt update && \
    apt install -y python3-pip libcairo2-dev pkg-config libgtk-3-dev libmpv-dev libglib2.0-dev gir1.2-notify-0.7

RUN pip3 install -r dev-requirements.txt && \
    pip3 install -e .
