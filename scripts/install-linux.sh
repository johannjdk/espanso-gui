#!/bin/sh
set -eu

repo="johannjdk/espanso-gui-qt"
release_url="https://github.com/${repo}/releases/latest/download"

info() { printf '\033[1;36m==>\033[0m %s\n' "$1"; }
success() { printf '\033[1;32m==>\033[0m %s\n' "$1"; }
die() { printf '\033[1;31mError:\033[0m %s\n' "$1" >&2; exit 1; }

[ "$(uname -s)" = "Linux" ] || die "This installer supports Linux only."
[ -r /etc/os-release ] || die "Could not identify your Linux distribution."

# shellcheck disable=SC1091
. /etc/os-release
distribution="${ID:-} ${ID_LIKE:-}"

case " $distribution " in
  *" debian "*|*" ubuntu "*) package_type="deb" ;;
  *" arch "*|*" manjaro "*|*" endeavouros "*) package_type="arch" ;;
  *) die "Unsupported distribution: ${PRETTY_NAME:-unknown}. Use Debian, Ubuntu, Arch, or a compatible distribution." ;;
esac

if command -v sudo >/dev/null 2>&1; then
  sudo_cmd="sudo"
elif [ "$(id -u)" -eq 0 ]; then
  sudo_cmd=""
else
  die "Administrator access is required. Install sudo or run this script as root."
fi

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT HUP INT TERM

download() {
  destination="$1"
  url="$2"
  if command -v curl >/dev/null 2>&1; then
    curl --fail --location --progress-bar --output "$destination" "$url"
  elif command -v wget >/dev/null 2>&1; then
    wget --show-progress --output-document="$destination" "$url"
  else
    die "curl or wget is required to download the release."
  fi
}

info "Detected ${PRETTY_NAME:-$ID}"
case "$package_type" in
  deb)
    command -v dpkg >/dev/null 2>&1 || die "dpkg is required for Debian-based installations."
    command -v apt-get >/dev/null 2>&1 || die "apt-get is required for Debian-based installations."
    package="$tmp_dir/espanso-gui-qt-all.deb"
    info "Downloading the latest Debian package"
    download "$package" "$release_url/espanso-gui-qt-all.deb"
    info "Installing Espanso GUI"
    if ! $sudo_cmd dpkg -i "$package"; then
      info "Installing required dependencies"
      $sudo_cmd apt-get update
      $sudo_cmd apt-get install -f -y
    fi
    ;;
  arch)
    command -v pacman >/dev/null 2>&1 || die "pacman is required for Arch-based installations."
    package="$tmp_dir/espanso-gui-qt-any.pkg.tar.zst"
    info "Downloading the latest Arch package"
    download "$package" "$release_url/espanso-gui-qt-any.pkg.tar.zst"
    info "Installing Espanso GUI"
    $sudo_cmd pacman -U --needed --noconfirm "$package"
    ;;
esac

success "Espanso GUI is installed. You can now launch it from your application menu."
