#! /usr/bin/env bash

set -xe

pushd docs
pipenv run make html
popd

mv docs/_build/html public
mv htmlcov public
