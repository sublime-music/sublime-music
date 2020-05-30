FROM ubuntu:20.04

LABEL maintainer sumner "https://gitlab.com/sumner"

ARG DEBIAN_FRONTEND=noninteractive
RUN apt update && \
    export TZ=America/Denver DEBIAN_FRONTEND=noninteractive && \
    apt install -y \
        build-essential \
        curl \
        dbus \
        gir1.2-nm-1.0 \
        gir1.2-notify-0.7 \
        git \
        libbz2-dev \
        libcairo2-dev \
        libffi-dev \
        libgirepository1.0-dev \
        libglib2.0-dev \
        libgtk-3-dev \
        liblzma-dev \
        libmpv-dev \
        libncurses5-dev \
        libncursesw5-dev \
        libreadline-dev \
        libsqlite3-dev \
        libssl-dev \
        libyaml-dev \
        llvm \
        make \
        pkg-config \
        python-openssl \
        python3-pip \
        tk-dev \
        wget \
        xvfb \
        xz-utils \
        zlib1g-dev

RUN cd /usr/local/src && \
    curl -L https://github.com/pyenv/pyenv-installer/raw/master/bin/pyenv-installer | bash

RUN pip3 install pipenv

# Install the correct Python version with pyenv
COPY install-python.sh /tmp/install-python.sh
RUN /tmp/install-python.sh
