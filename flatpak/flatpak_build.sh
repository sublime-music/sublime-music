#!/usr/bin/env bash

set -xe

REPO=${REPO:-/repo}
APPID=app.sublimemusic.SublimeMusic

# TODO move these to the Docker container
pip3 install requirements-parser
flatpak install -y org.gnome.Platform//3.38
flatpak install -y org.gnome.Sdk//3.38

rm -rf flatpak-builder-tools
git clone https://github.com/flatpak/flatpak-builder-tools.git

python3 ./flatpak-builder-tools/pip/flatpak-pip-generator \
    --requirements-file=flatpak-requirements.txt \
    --output pypi-dependencies

mkdir -p $REPO

flatpak-builder --force-clean --repo=$REPO flatpak_build_dir ${APPID}.json

flatpak build-bundle $REPO sublime-music.flatpak $APPID
