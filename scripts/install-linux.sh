#!/bin/sh
# Install the latest Espanso GUI release on supported Linux distributions.
set -eu

repo="johannjdk/espanso-gui"
release_url="https://github.com/${repo}/releases/latest/download"

if [ -t 1 ]; then
  cyan="$(printf '\033[1;36m')"
  green="$(printf '\033[1;32m')"
  red="$(printf '\033[1;31m')"
  reset="$(printf '\033[0m')"
else
  cyan=''
  green=''
  red=''
  reset=''
fi

info() { printf '%s==>%s %s\n' "$cyan" "$reset" "$1"; }
success() { printf '%s==>%s %s\n' "$green" "$reset" "$1"; }
die() { printf '%sError:%s %s\n' "$red" "$reset" "$1" >&2; exit 1; }

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
  use_sudo=true
elif [ "$(id -u)" -eq 0 ]; then
  use_sudo=false
else
  die "Administrator access is required. Install sudo or run this script as root."
fi

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT HUP INT TERM

run_as_root() {
  if [ "$use_sudo" = true ]; then
    sudo "$@"
  else
    "$@"
  fi
}

download() {
  target="$1"
  source_url="$2"
  if command -v curl >/dev/null 2>&1; then
    curl --fail --location --show-error --progress-bar --output "$target" "$source_url"
  elif command -v wget >/dev/null 2>&1; then
    wget --show-progress --output-document="$target" "$source_url"
  else
    die "curl or wget is required to download the release."
  fi
}

info "Detected ${PRETTY_NAME:-$ID}"
case "$package_type" in
  deb)
    command -v dpkg >/dev/null 2>&1 || die "dpkg is required for Debian-based installations."
    command -v apt-get >/dev/null 2>&1 || die "apt-get is required for Debian-based installations."
    package="$tmp_dir/espanso-gui-all.deb"
    info "Downloading the latest Debian package…"
    download "$package" "$release_url/espanso-gui-all.deb"
    info "Installing Espanso GUI…"
    if ! run_as_root dpkg -i "$package"; then
      info "Installing required dependencies…"
      run_as_root apt-get update
      run_as_root apt-get install -f -y
    fi
    ;;
  arch)
    command -v pacman >/dev/null 2>&1 || die "pacman is required for Arch-based installations."
    package="$tmp_dir/espanso-gui-qt-any.pkg.tar.zst"
    info "Downloading the latest Arch package…"
    download "$package" "$release_url/espanso-gui-qt-any.pkg.tar.zst"
    info "Installing Espanso GUI…"
    if pacman -Q espanso-gui >/dev/null 2>&1; then
      info "The old espanso-gui package conflicts with espanso-gui-qt. Confirm its removal to continue."
      # Read the confirmation from the terminal even when this script is piped into sh.
      run_as_root pacman -U --needed "$package" < /dev/tty
    else
      run_as_root pacman -U --needed --noconfirm "$package"
    fi
    ;;
esac

success "Espanso GUI is installed. You can launch it from the application menu."
