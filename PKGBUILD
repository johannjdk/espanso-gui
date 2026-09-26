pkgname=espanso-gui-qt
pkgver=1.0.0
pkgrel=1
pkgdesc='Qt editor for Espanso configuration files'
arch=('any')
url='https://github.com/johannjdk/espanso-gui-qt'
license=('custom')
depends=('python' 'pyside6' 'python-yaml')
source=("${pkgname}-${pkgver}.tar.gz")
sha256sums=('SKIP')

package() {
    local source_dir="${srcdir}/${pkgname}-${pkgver}"

    install -Dm755 "${source_dir}/scripts/launcher.py" "${pkgdir}/usr/bin/${pkgname}"
    install -Dm644 "${source_dir}/assets/io.github.johannjdk.EspansoGuiQt.desktop" \
        "${pkgdir}/usr/share/applications/io.github.johannjdk.EspansoGuiQt.desktop"
    install -Dm644 "${source_dir}/assets/espanso-gui-qt.png" \
        "${pkgdir}/usr/share/icons/hicolor/160x160/apps/io.github.johannjdk.EspansoGuiQt.png"
    local site_packages
    site_packages="$(/usr/bin/python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
    mkdir -p "${pkgdir}${site_packages}"
    cp -r --no-preserve=ownership "${source_dir}/espanso_gui" "${pkgdir}${site_packages}/"
    find "${pkgdir}${site_packages}/espanso_gui" -type d -name __pycache__ -prune -exec rm -rf {} +
    find "${pkgdir}${site_packages}/espanso_gui" -type f -name '*.pyc' -delete
}
