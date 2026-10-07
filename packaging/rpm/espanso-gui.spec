Name:           espanso-gui
Version:        @VERSION@
Release:        1%{?dist}
Summary:        Desktop editor for Espanso configuration files
License:        GPL-3.0-only
URL:            https://github.com/johannjdk/espanso-gui
BuildArch:      noarch

Requires:       python3
Requires:       python3-pyside6
Requires:       python3-pyyaml
Requires:       hicolor-icon-theme

%description
Espanso GUI provides a native Qt interface for managing Espanso matches,
forms, variables, and YAML configuration files.

%install
mkdir -p %{buildroot}%{_bindir}
mkdir -p %{buildroot}%{python3_sitelib}
mkdir -p %{buildroot}%{_datadir}/applications
mkdir -p %{buildroot}%{_datadir}/icons/hicolor/256x256/apps
mkdir -p %{buildroot}%{_datadir}/pixmaps

install -Dm755 %{_sourcedir}/scripts/launcher.py %{buildroot}%{_bindir}/espanso-gui
install -Dm644 %{_sourcedir}/assets/io.github.johannjdk.EspansoGui.desktop \
    %{buildroot}%{_datadir}/applications/io.github.johannjdk.EspansoGui.desktop
install -Dm644 %{_sourcedir}/assets/espanso-gui.png \
    %{buildroot}%{_datadir}/icons/hicolor/256x256/apps/io.github.johannjdk.EspansoGui.png
install -Dm644 %{_sourcedir}/assets/espanso-gui.png \
    %{buildroot}%{_datadir}/pixmaps/io.github.johannjdk.EspansoGui.png

cp -a %{_sourcedir}/espanso_gui %{buildroot}%{python3_sitelib}/
find %{buildroot}%{python3_sitelib}/espanso_gui -type d -name __pycache__ -prune -exec rm -rf {} +
find %{buildroot}%{python3_sitelib}/espanso_gui -type f -name '*.pyc' -delete

%files
%{_bindir}/espanso-gui
%{python3_sitelib}/espanso_gui
%{_datadir}/applications/io.github.johannjdk.EspansoGui.desktop
%{_datadir}/icons/hicolor/256x256/apps/io.github.johannjdk.EspansoGui.png
%{_datadir}/pixmaps/io.github.johannjdk.EspansoGui.png
