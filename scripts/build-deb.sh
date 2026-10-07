#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
package_name="espanso-gui"
version="$(sed -n 's/^version = "\(.*\)"$/\1/p' "$project_root/pyproject.toml")"
build_dir="$project_root/build/debian"
staging_dir="$build_dir/$package_name"
output_dir="$project_root/dist"
artifact="$output_dir/${package_name}-${version}-linux-debian-ubuntu.deb"

command -v dpkg-deb >/dev/null || {
    echo "dpkg-deb is required to build a Debian package." >&2
    exit 1
}

rm -rf "$build_dir"
mkdir -p "$staging_dir/DEBIAN" "$staging_dir/usr/bin" \
    "$staging_dir/usr/lib/python3/dist-packages" \
    "$staging_dir/usr/share/applications" \
    "$staging_dir/usr/share/icons/hicolor/256x256/apps" \
    "$staging_dir/usr/share/pixmaps" "$output_dir"

cp -a "$project_root/espanso_gui" "$staging_dir/usr/lib/python3/dist-packages/"
find "$staging_dir" -type d -name __pycache__ -prune -exec rm -rf {} +
find "$staging_dir" -type f -name '*.pyc' -delete

install -Dm755 "$project_root/packaging/debian/postinst" "$staging_dir/DEBIAN/postinst"
install -Dm755 "$project_root/packaging/debian/postrm" "$staging_dir/DEBIAN/postrm"
sed "s/@VERSION@/$version/" "$project_root/packaging/debian/control" > "$staging_dir/DEBIAN/control"
install -Dm644 "$project_root/assets/io.github.johannjdk.EspansoGui.desktop" \
    "$staging_dir/usr/share/applications/io.github.johannjdk.EspansoGui.desktop"
install -Dm644 "$project_root/assets/espanso-gui.png" \
    "$staging_dir/usr/share/icons/hicolor/256x256/apps/io.github.johannjdk.EspansoGui.png"
install -Dm644 "$project_root/assets/espanso-gui.png" \
    "$staging_dir/usr/share/pixmaps/io.github.johannjdk.EspansoGui.png"

cat > "$staging_dir/usr/bin/$package_name" <<'EOF'
#!/usr/bin/python3
from espanso_gui.app import main

raise SystemExit(main())
EOF
chmod 755 "$staging_dir/usr/bin/$package_name"

dpkg-deb --build --root-owner-group "$staging_dir" "$artifact"
echo "Built $artifact"
