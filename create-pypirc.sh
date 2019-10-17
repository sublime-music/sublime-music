#! /bin/sh

echo "[distutils]" >> ~/.pypirc
echo "index-servers =" >> ~/.pypirc
echo "    pypi" >> ~/.pypirc
echo "    pypi_test" >> ~/.pypirc
echo "[pypi]" >> ~/.pypirc
echo "username: ${PYPI_USER}" >> ~/.pypirc
echo "password: ${PYPI_PASSWORD}" >> ~/.pypirc
echo "[pypi_test]" >> ~/.pypirc
echo "repository: https://test.pypi.org/legacy/" >> ~/.pypirc
echo "username: ${PYPI_USER}" >> ~/.pypirc
echo "password: ${PYPI_TEST_PASSWORD}" >> ~/.pypirc

