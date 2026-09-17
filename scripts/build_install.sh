#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd -- "${script_dir}/.." && pwd)"

cd "${repository_root}"

python3 -m pip install build
python3 -m build

wheel_path="$(find "${repository_root}/dist" -maxdepth 1 -type f -name '*.whl' -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n 1 | cut -d' ' -f2-)"

if [[ -z "${wheel_path}" ]]; then
    echo "No wheel was generated in ${repository_root}/dist" >&2
    exit 1
fi

echo "Installing $(basename "${wheel_path}")"
python3 -m pip install --force-reinstall "${wheel_path}"
