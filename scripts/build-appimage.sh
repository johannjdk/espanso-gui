#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
package_name="espanso-gui"
version="$(sed -n 's/^version = "\(.*\)"$/\1/p' "$project_root/pyproject.toml")"

case "$(uname -m)" in
    x86_64) app_arch="x86_64" ;;
    aarch64) app_arch="aarch64" ;;
    *) app_arch="$(uname -m)" ;;
esac

ARCH="${ARCH:-$app_arch}"
bundle_dir="$project_root/build/linux-standalone/app"
build_dir="$project_root/build/appimage"
appdir="$build_dir/AppDir"
output_dir="$project_root/dist"
artifact="$output_dir/${package_name}-${version}-linux-${ARCH}.AppImage"

mkdir -p "$output_dir" "$build_dir"

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

echo "==> Preparing AppDir"
rm -rf "$appdir"
mkdir -p "$appdir/usr/bin" \
    "$appdir/usr/lib/$package_name" \
    "$appdir/usr/share/applications" \
    "$appdir/usr/share/icons/hicolor/256x256/apps"

cp -a "$bundle_dir"/* "$appdir/usr/lib/$package_name/"
chmod 755 "$appdir/usr/lib/$package_name/$package_name"

ln -s "../lib/$package_name/$package_name" "$appdir/usr/bin/$package_name"

cp -f "$project_root/assets/io.github.johannjdk.EspansoGui.desktop" "$appdir/"
cp -f "$project_root/assets/io.github.johannjdk.EspansoGui.desktop" "$appdir/usr/share/applications/"

cp -f "$project_root/assets/espanso-gui.png" "$appdir/io.github.johannjdk.EspansoGui.png"
cp -f "$project_root/assets/espanso-gui.png" "$appdir/.DirIcon"
cp -f "$project_root/assets/espanso-gui.png" "$appdir/usr/share/icons/hicolor/256x256/apps/io.github.johannjdk.EspansoGui.png"

cat > "$appdir/AppRun" <<'EOF'
#!/bin/sh
set -e
HERE="$(dirname "$(readlink -f "${0}")")"
export PATH="${HERE}/usr/bin:${PATH}"
export LD_LIBRARY_PATH="${HERE}/usr/lib:${HERE}/usr/lib/espanso-gui/_internal:${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export XDG_DATA_DIRS="${HERE}/usr/share:${XDG_DATA_DIRS:+:$XDG_DATA_DIRS}"
exec "${HERE}/usr/lib/espanso-gui/espanso-gui" "$@"
EOF
chmod 755 "$appdir/AppRun"

echo "==> Locating or downloading appimagetool"
if command -v appimagetool >/dev/null 2>&1; then
    tool_exec="appimagetool"
else
    tool_binary="$build_dir/appimagetool-${ARCH}.AppImage"
    extracted_dir="$build_dir/appimagetool-extracted"

    if [[ ! -f "$tool_binary" ]]; then
        echo "Downloading appimagetool..."
        tool_url="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-${ARCH}.AppImage"
        if command -v curl >/dev/null 2>&1; then
            curl -fsSL --progress-bar -o "$tool_binary" "$tool_url"
        elif command -v wget >/dev/null 2>&1; then
            wget -q -O "$tool_binary" "$tool_url"
        else
            echo "curl or wget is required to download appimagetool." >&2
            exit 1
        fi
        chmod +x "$tool_binary"
    fi

    # Extract to prevent FUSE requirements in CI / container environments
    if [[ ! -x "$extracted_dir/AppRun" ]]; then
        echo "Extracting appimagetool..."
        (
            cd "$build_dir"
            rm -rf squashfs-root
            "$tool_binary" --appimage-extract >/dev/null
            rm -rf "$extracted_dir"
            mv squashfs-root "$extracted_dir"
        )
    fi
    tool_exec="$extracted_dir/AppRun"
fi

echo "==> Building AppImage"
ARCH="$ARCH" "$tool_exec" --no-appstream "$appdir" "$artifact"
chmod +x "$artifact"
echo "Built $artifact"

