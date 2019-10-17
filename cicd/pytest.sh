#! /bin/sh

pytest
ec=$?

echo "pytest exited with exit code $ec"

case $ec in
    0) exit 0 ;;
    5) exit 0 ;;
    *) exit 1 ;;
esac
