#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
package_name="espanso-gui-qt"
version="$(sed -n 's/^version = "\(.*\)"$/\1/p' "$project_root/pyproject.toml")"
build_dir="$project_root/build/arch"
source_dir="$build_dir/${package_name}-${version}"
output_dir="$project_root/dist"
artifact="$output_dir/${package_name}-${version}-linux-arch.pkg.tar.zst"

command -v makepkg >/dev/null || {
    echo "makepkg is required to build an Arch Linux package." >&2
    exit 1
}

rm -rf "$build_dir"
mkdir -p "$source_dir" "$output_dir"
cp -a "$project_root/espanso_gui" "$project_root/assets" "$project_root/scripts" "$source_dir/"
cp "$project_root/pyproject.toml" "$project_root/README.md" "$source_dir/"
find "$source_dir" -type d -name __pycache__ -prune -exec rm -rf {} +
find "$source_dir" -type f -name '*.pyc' -delete
tar -C "$build_dir" -czf "$build_dir/${package_name}-${version}.tar.gz" "${package_name}-${version}"
cp "$project_root/PKGBUILD" "$build_dir/"

(
    cd "$build_dir"
    makepkg --cleanbuild --nodeps --noconfirm
)

package_file="$(find "$build_dir" -maxdepth 1 -type f \
    -name "${package_name}-${version}-*.pkg.tar.zst" -print -quit)"
if [[ -z "$package_file" ]]; then
    echo "Arch package was not created." >&2
    exit 1
fi

cp -f "$package_file" "$artifact"
echo "Built $artifact"
