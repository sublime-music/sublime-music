#! /usr/bin/env sh

echo "[distutils]" >> ~/.pypirc
echo "index-servers =" >> ~/.pypirc
echo "    pypi" >> ~/.pypirc
echo "    pypi_test" >> ~/.pypirc
echo "[pypi]" >> ~/.pypirc
echo "username = __token__" >> ~/.pypirc
echo "password = ${PYPI_TOKEN}" >> ~/.pypirc
echo "[pypi_test]" >> ~/.pypirc
echo "repository = https://test.pypi.org/legacy/" >> ~/.pypirc
echo "username = __token__" >> ~/.pypirc
echo "password = ${PYPI_TEST_TOKEN}" >> ~/.pypirc

