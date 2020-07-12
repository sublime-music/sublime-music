#!/bin/bash

set -xe

REPO=${REPO:-/repo}
APPID=app.sublimemusic.SublimeMusic

pip install requirements-parser

rm -rf flatpak-builder-tools
git clone https://github.com/flatpak/flatpak-builder-tools.git

python3 ./flatpak-builder-tools/pip/flatpak-pip-generator \
    --requirements-file=flatpak-requirements.txt \
    --output pypi-dependencies

mkdir -p $REPO

flatpak-builder --force-clean --repo=$REPO flatpak_build_dir ${APPID}.json

flatpak build-bundle $REPO sublime-music.flatpak $APPID
