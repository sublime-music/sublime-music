#! /usr/bin/env bash

set -xe

pushd docs
poetry run make html
popd

mv docs/_build/html public
mv htmlcov public
