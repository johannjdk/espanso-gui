#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
package_name="espanso-gui"
version="$(sed -n 's/^version = "\(.*\)"$/\1/p' "$project_root/pyproject.toml")"
build_dir="$project_root/build/rpm"
output_dir="$project_root/dist"

command -v rpmbuild >/dev/null || {
    echo "rpmbuild is required to build an RPM package." >&2
    echo "On Fedora / RHEL install it with: sudo dnf install rpm-build" >&2
    exit 1
}

rm -rf "$build_dir"
mkdir -p "$build_dir/SPECS" "$build_dir/SOURCES" "$build_dir/BUILD" \
    "$build_dir/RPMS" "$build_dir/SRPMS" "$output_dir"

spec_file="$build_dir/SPECS/${package_name}.spec"
sed "s/@VERSION@/$version/" "$project_root/packaging/rpm/${package_name}.spec" > "$spec_file"

rpmbuild -bb \
    --define "_topdir $build_dir" \
    --define "_sourcedir $project_root" \
    "$spec_file"

rpm_file="$(find "$build_dir/RPMS" -type f -name "${package_name}-${version}-*.rpm" -print -quit)"
if [[ -z "$rpm_file" ]]; then
    echo "RPM package was not created." >&2
    exit 1
fi

artifact="$output_dir/${package_name}-${version}-linux-fedora-rhel.noarch.rpm"
cp -f "$rpm_file" "$artifact"

echo "Built $artifact"
