#! /bin/sh

pushd docs
pipenv run make html
popd

mv docs/_build/html public
mv htmlcov public
