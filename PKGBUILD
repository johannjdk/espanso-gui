pkgname=espanso-gui-qt
pkgver=1.3.3
pkgrel=1
pkgdesc='Desktop editor for Espanso configuration files'
arch=('any')
url='https://github.com/johannjdk/espanso-gui'
license=('GPL-3.0-only')
depends=('python' 'pyside6' 'python-yaml')
conflicts=('espanso-gui')
source=("${pkgname}-${pkgver}.tar.gz")
sha256sums=('SKIP')

package() {
    local source_dir="${srcdir}/${pkgname}-${pkgver}"

    install -Dm755 "${source_dir}/scripts/launcher.py" "${pkgdir}/usr/bin/espanso-gui"
    install -Dm644 "${source_dir}/assets/io.github.johannjdk.EspansoGui.desktop" \
        "${pkgdir}/usr/share/applications/io.github.johannjdk.EspansoGui.desktop"
    install -Dm644 "${source_dir}/assets/espanso-gui.png" \
        "${pkgdir}/usr/share/icons/hicolor/256x256/apps/io.github.johannjdk.EspansoGui.png"
    install -Dm644 "${source_dir}/assets/espanso-gui.png" \
        "${pkgdir}/usr/share/pixmaps/io.github.johannjdk.EspansoGui.png"
    local site_packages
    site_packages="$(/usr/bin/python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
    mkdir -p "${pkgdir}${site_packages}"
    cp -r --no-preserve=ownership "${source_dir}/espanso_gui" "${pkgdir}${site_packages}/"
    find "${pkgdir}${site_packages}/espanso_gui" -type d -name __pycache__ -prune -exec rm -rf {} +
    find "${pkgdir}${site_packages}/espanso_gui" -type f -name '*.pyc' -delete
}
