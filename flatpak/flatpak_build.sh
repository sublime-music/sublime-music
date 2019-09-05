#!/bin/bash

git clone https://github.com/flatpak/flatpak-builder-tools.git
sed -i "s/filename.endswith('gz')/filename.endswith('gz') or filename.endswith('zip')/g" flatpak-builder-tools/pip/flatpak-pip-generator

python3 ./flatpak-builder-tools/pip/flatpak-pip-generator --requirements-file=flatpak-requirements.txt --output pypi-dependencies

mkdir /repo

flatpak-builder --repo=/repo flatpak_build_dir com.sumnerevans.libremsonic.json

flatpak build-bundle /repo libremsonic.flatpak com.sumnerevans.libremsonic
