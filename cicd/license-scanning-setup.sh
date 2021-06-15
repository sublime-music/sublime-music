./cicd/install-project-deps.sh
poetry export -E chromecast -E keyring -E server --without-hashes > requirements.txt
