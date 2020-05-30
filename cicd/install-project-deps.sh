#! /bin/sh
export PYENV_ROOT="${HOME}/.pyenv"
export PATH="${PYENV_ROOT}/bin:$PATH"
eval "$(pyenv init -)"

export PIPENV_VENV_IN_PROJECT=1
pipenv install --dev
