#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
package_name="espanso-gui-qt"
version="$(sed -n 's/^version = "\(.*\)"$/\1/p' "$project_root/pyproject.toml")"
build_dir="$project_root/build/macos"
output_dir="$project_root/dist"

case "$(uname -m)" in
    arm64)
        package_arch="arm64"
        ;;
    x86_64)
        package_arch="x64"
        ;;
    *)
        echo "Unsupported macOS architecture: $(uname -m)" >&2
        exit 1
        ;;
esac

artifact="$output_dir/${package_name}-macos-${package_arch}.dmg"
iconset="$build_dir/EspansoGUI.iconset"
icon="$build_dir/EspansoGUI.icns"

command -v hdiutil >/dev/null || {
    echo "hdiutil is required to build a macOS disk image." >&2
    exit 1
}

rm -rf "$build_dir"
mkdir -p "$build_dir/work" "$build_dir/spec" "$output_dir" "$iconset"

for size in 16 32 128 256 512; do
    sips -z "$size" "$size" "$project_root/assets/espanso-gui-qt.png" \
        --out "$iconset/icon_${size}x${size}.png" >/dev/null
    doubled_size=$((size * 2))
    sips -z "$doubled_size" "$doubled_size" "$project_root/assets/espanso-gui-qt.png" \
        --out "$iconset/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "$iconset" -o "$icon"

python3 -m pip install --upgrade pip
python3 -m pip install "$project_root" pyinstaller

python3 -m PyInstaller \
    --noconfirm \
    --clean \
    --windowed \
    --name "Espanso GUI" \
    --icon "$icon" \
    --osx-bundle-identifier "io.github.johannjdk.EspansoGuiQt" \
    --add-data "$project_root/assets:assets" \
    --distpath "$build_dir/dist" \
    --workpath "$build_dir/work" \
    --specpath "$build_dir/spec" \
    "$project_root/run_editor.py"

app_bundle="$build_dir/dist/Espanso GUI.app"
plist="$app_bundle/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $version" "$plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleVersion $version" "$plist"
hdiutil create -volname "Espanso GUI" -srcfolder "$app_bundle" -ov -format UDZO "$artifact"
echo "Built $artifact"
