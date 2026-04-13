#!/usr/bin/env bash
# Build fairyclaw and upload only the current pyproject.toml version to TestPyPI.
#
# Prerequisites:
#   pip install build twine
#   API token from https://test.pypi.org/manage/account/token/
#
# Auth (pick one):
#   export TWINE_USERNAME=__token__
#   export TWINE_PASSWORD=pypi-AgEIcHlwaS...   # TestPyPI token
#   # or ~/.pypirc with [testpypi] username=__token__ password=...
#
# Usage:
#   ./scripts/publish_testpypi.sh              # wheel/sdist only (uses existing web_dist if any)
#   ./scripts/publish_testpypi.sh --with-web # npm build + prepare_web_dist.py first
#   ./scripts/publish_testpypi.sh --dry-run    # build + check, no upload

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

WITH_WEB=0
DRY_RUN=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-web) WITH_WEB=1 ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help)
      cat <<'EOF'
Usage: publish_testpypi.sh [--with-web] [--dry-run]

  --with-web   Run npm ci/build in web/ and scripts/prepare_web_dist.py before packaging.
  --dry-run    Build and twine check only; do not upload.

Environment: TWINE_USERNAME, TWINE_PASSWORD (or ~/.pypirc [testpypi]).
EOF
      exit 0
      ;;
    *)
      echo "Unknown option: $1 (try --help)" >&2
      exit 1
      ;;
  esac
  shift
done

VERSION="$(grep -E '^version[[:space:]]*=' pyproject.toml | head -1 | sed -E 's/^version[[:space:]]*=[[:space:]]*"([^"]+)".*/\1/')"
if [[ -z "${VERSION}" ]]; then
  echo "Could not parse version from pyproject.toml" >&2
  exit 1
fi

echo "==> fairyclaw ${VERSION} -> TestPyPI"

if [[ "${WITH_WEB}" -eq 1 ]]; then
  echo "==> Web: npm ci + build + prepare_web_dist.py"
  (cd web && npm ci --no-progress --silent && npm run build --silent -- --logLevel warn)
  python3 scripts/prepare_web_dist.py
fi

echo "==> Clean dist/ and build/ (avoid uploading stale wheels/sdists)"
rm -rf dist build
mkdir -p dist

echo "==> python -m build"
python3 -m build

echo "==> twine check"
python3 -m twine check dist/*

shopt -s nullglob
ARTIFACTS=(dist/fairyclaw-"${VERSION}"*.whl dist/fairyclaw-"${VERSION}"*.tar.gz)
if [[ ${#ARTIFACTS[@]} -eq 0 ]]; then
  echo "No artifacts matching dist/fairyclaw-${VERSION}*" >&2
  ls -la dist/ >&2 || true
  exit 1
fi

echo "==> Upload targets (current version only):"
printf '    %s\n' "${ARTIFACTS[@]}"

if [[ "${DRY_RUN}" -eq 1 ]]; then
  echo "==> Dry run: skipping twine upload"
  exit 0
fi

echo "==> twine upload --repository testpypi"
python3 -m twine upload --repository testpypi "${ARTIFACTS[@]}"

echo "==> Done. Example install:"
echo "    pip install -i https://test.pypi.org/simple/ fairyclaw==${VERSION}"
