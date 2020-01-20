#! /bin/bash

grep -Inre "print(" sublime | while read line; do
    if [[ $line =~ "# allowprint" ]]; then
        continue
    fi
    echo "Found instance of print statement:"
    echo $line
    echo "Use logging instead or add '# allowprint' to the end of the line."
    exit 1
done
