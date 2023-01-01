#! /usr/bin/env bash

set -xe

export TZ=America/Denver DEBIAN_FRONTEND=noninteractive

sudo apt update
sudo apt install -y \
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
    python3-openssl \
    python3-pip \
    python3-venv \
    tk-dev \
    wget \
    xvfb \
    xz-utils \
    zlib1g-dev

# Install pyenv
pushd /usr/local/src
curl -L https://github.com/pyenv/pyenv-installer/raw/master/bin/pyenv-installer | bash
popd

export PYENV_ROOT="${HOME}/.pyenv"
export PATH="${PYENV_ROOT}/bin:$PATH"
eval "$(pyenv init -)"
