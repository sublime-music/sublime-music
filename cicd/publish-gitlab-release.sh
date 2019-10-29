#! /bin/bash

set -e

if [[ $(head -n 1 CHANGELOG) == "${CI_COMMIT_TAG}" ]]; then
    i=0
    first=1
    while read l; do
        i=$(( $i + 1 ))
        if [[ $l =~ ^=+$ ]]; then
            if [[ $first == 0 ]]; then
                break
            fi
            first=0
        fi
    done < CHANGELOG

    description=$(head -n $(( $i - 2 )) CHANGELOG)
fi

if [[ "${description}" == "" ]]; then
    description="No description provided for this release."
fi

description=$(echo "$description" | sed ':a;N;$!ba;s/\n/\\n/g')

data="
{
    \"name\": \"${CI_COMMIT_TAG}\",
    \"tag_name\": \"${CI_COMMIT_TAG}\",
    \"description\": \"${description}\",
    \"assets\": {
        \"links\": [
            {
                \"name\": \"sublime-music-${CI_COMMIT_TAG}.flatpak\",
                \"url\": \"${CI_PROJECT_URL}/-/jobs/artifacts/${CI_COMMIT_REF_SLUG}/raw/sublime-music.flatpak?job=build_flatpak\"
            }
        ]
    }
}
"

echo "DATA:"
echo "$data"

curl \
    --header 'Content-Type: application/json' \
    --header "PRIVATE-TOKEN: ${RELEASE_PUBLISH_TOKEN}" \
    --data "$data" \
    --request POST \
    ${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/releases
