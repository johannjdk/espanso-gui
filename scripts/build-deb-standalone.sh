#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
package_name="espanso-gui"
version="$(sed -n 's/^version = "\(.*\)"$/\1/p' "$project_root/pyproject.toml")"

case "$(uname -m)" in
    x86_64) deb_arch="amd64" ;;
    aarch64) deb_arch="arm64" ;;
    *) deb_arch="amd64" ;;
esac

bundle_dir="$project_root/build/linux-standalone/app"
build_dir="$project_root/build/debian-standalone"
staging_dir="$build_dir/$package_name"
output_dir="$project_root/dist"
artifact="$output_dir/${package_name}-${version}-linux-debian-ubuntu-standalone.deb"

command -v dpkg-deb >/dev/null || {
    echo "dpkg-deb is required to build a Debian package." >&2
    exit 1
}

# Build the PyInstaller standalone bundle if it has not been created yet or rebuild requested
if [[ ! -x "$bundle_dir/$package_name" || "${FORCE_REBUILD:-0}" == "1" ]]; then
    echo "==> Building standalone application with PyInstaller"
    python3 -m pip install --upgrade pip
    python3 -m pip install "$project_root" pyinstaller

    rm -rf "$project_root/build/linux-standalone"
    mkdir -p "$project_root/build/linux-standalone"

    python3 -m PyInstaller \
        --noconfirm \
        --clean \
        --windowed \
        --name "$package_name" \
        --add-data "$project_root/assets:assets" \
        --distpath "$project_root/build/linux-standalone/dist" \
        --workpath "$project_root/build/linux-standalone/work" \
        --specpath "$project_root/build/linux-standalone/spec" \
        "$project_root/run_editor.py"

    mkdir -p "$bundle_dir"
    cp -a "$project_root/build/linux-standalone/dist/$package_name"/* "$bundle_dir/"
fi

echo "==> Creating standalone Debian package staging directory"
rm -rf "$build_dir"
mkdir -p "$staging_dir/DEBIAN" \
    "$staging_dir/opt/$package_name" \
    "$staging_dir/usr/bin" \
    "$staging_dir/usr/share/applications" \
    "$staging_dir/usr/share/icons/hicolor/256x256/apps" \
    "$staging_dir/usr/share/pixmaps" \
    "$output_dir"

cp -a "$bundle_dir"/* "$staging_dir/opt/$package_name/"
chmod 755 "$staging_dir/opt/$package_name/$package_name"

ln -s "/opt/$package_name/$package_name" "$staging_dir/usr/bin/$package_name"

install -Dm755 "$project_root/packaging/debian/postinst" "$staging_dir/DEBIAN/postinst"
install -Dm755 "$project_root/packaging/debian/postrm" "$staging_dir/DEBIAN/postrm"

sed -e "s/@VERSION@/$version/" -e "s/@ARCH@/$deb_arch/" \
    "$project_root/packaging/debian/control-standalone" > "$staging_dir/DEBIAN/control"

install -Dm644 "$project_root/assets/io.github.johannjdk.EspansoGui.desktop" \
    "$staging_dir/usr/share/applications/io.github.johannjdk.EspansoGui.desktop"
install -Dm644 "$project_root/assets/espanso-gui.png" \
    "$staging_dir/usr/share/icons/hicolor/256x256/apps/io.github.johannjdk.EspansoGui.png"
install -Dm644 "$project_root/assets/espanso-gui.png" \
    "$staging_dir/usr/share/pixmaps/io.github.johannjdk.EspansoGui.png"

dpkg-deb --build --root-owner-group "$staging_dir" "$artifact"
echo "Built $artifact"

