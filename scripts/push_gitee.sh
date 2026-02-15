#!/usr/bin/env bash
set -euo pipefail

REMOTE_NAME="${REMOTE_NAME:-gitee}"
REMOTE_URL="${REMOTE_URL:-git@gitee.com:BitterVan/InkCrop.git}"
BRANCH="${1:-main}"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "错误：请在 git 仓库目录内执行。"
  exit 1
fi

if git remote get-url "${REMOTE_NAME}" >/dev/null 2>&1; then
  git remote set-url "${REMOTE_NAME}" "${REMOTE_URL}"
else
  git remote add "${REMOTE_NAME}" "${REMOTE_URL}"
fi

echo "同步到 ${REMOTE_NAME} (${REMOTE_URL})"
git push "${REMOTE_NAME}" "refs/heads/${BRANCH}:refs/heads/${BRANCH}"
git push "${REMOTE_NAME}" --tags
echo "完成：分支 ${BRANCH} + 全部 tags 已推送到 ${REMOTE_NAME}"
