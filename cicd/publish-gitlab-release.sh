#! /bin/sh

data="
{
    \"name\": \"${CI_COMMIT_TAG}\",
    \"tag_name\": \"${CI_COMMIT_TAG}\",
    \"description\": \"Test release from the GitLab CI/CD\",
    \"milestones\": []
}
"

echo $data

cat CHANGELOG

curl \
    --header 'Content-Type: application/json' \
    --header "PRIVATE-TOKEN: ${CI_JOB_TOKEN}" \
    ${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/releases
