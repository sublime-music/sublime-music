#!/usr/bin/env bash

set -xe

ARCH=${ARCH:""}
REPO=${REPO:-/repo}
APPID=app.sublimemusic.SublimeMusic

if [ -z "$ARCH" ]; then
    ARCH_ARG=""
else
    ARCH_ARG="--arch=$ARCH"
fi

pip3 install toml
flatpak install -y org.gnome.Platform/$ARCH/3.38
flatpak install -y org.gnome.Sdk/$ARCH/3.38

rm -rf flatpak-builder-tools
git clone https://github.com/flatpak/flatpak-builder-tools.git

python3 ./flatpak-builder-tools/poetry/flatpak-poetry-generator.py \
    ../poetry.lock \
    --production \
    -o pypi-dependencies.json

mkdir -p $REPO

flatpak-builder --force-clean $ARCH_ARG --repo=$REPO flatpak_build_dir ${APPID}.json

flatpak build-bundle $ARCH_ARG $REPO sublime-music.flatpak $APPID
