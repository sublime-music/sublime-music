#!/bin/bash

set -xe

rm -rf flatpak-builder-tools
git clone https://github.com/flatpak/flatpak-builder-tools.git

python3 ./flatpak-builder-tools/pip/flatpak-pip-generator --requirements-file=flatpak-requirements.txt --output pypi-dependencies

mkdir -p /repo

flatpak-builder --force-clean --repo=/repo flatpak_build_dir com.sumnerevans.SublimeMusic.json

flatpak build-bundle /repo sublime-music.flatpak com.sumnerevans.SublimeMusic
