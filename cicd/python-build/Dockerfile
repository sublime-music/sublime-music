FROM ubuntu:20.04

LABEL maintainer sumner "https://gitlab.com/sumner"

RUN apt update && \
    export TZ=America/Denver DEBIAN_FRONTEND=noninteractive && \
    apt install -y \
        python3-pip \
        libcairo2-dev \
        pkg-config \
        libgtk-3-dev \
        libmpv-dev \
        libglib2.0-dev \
        gir1.2-notify-0.7 \
        make \
        build-essential \
        libssl-dev \
        zlib1g-dev \
        libbz2-dev \
        libreadline-dev \
        libsqlite3-dev \
        wget \
        curl \
        llvm \
        libncurses5-dev \
        libncursesw5-dev \
        xz-utils \
        tk-dev \
        libffi-dev \
        liblzma-dev \
        python-openssl \
        git \
        libgirepository1.0-dev \
        gir1.2-nm-1.0 \
        dbus

RUN cd /usr/local/src && \
    curl -L https://github.com/pyenv/pyenv-installer/raw/master/bin/pyenv-installer | bash

RUN pip3 install pipenv

# Install the correct Python version with pyenv
COPY install-python.sh /tmp/install-python.sh
RUN /tmp/install-python.sh
