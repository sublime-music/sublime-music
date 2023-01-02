let
  pkgs = import <nixpkgs> {};
in
pkgs.mkShell {
  nativeBuildInputs = with pkgs; [
    gobject-introspection
    python3Packages.setuptools
    wrapGAppsHook
  ];

  buildInputs = with pkgs; [
    bashInteractive
    gcc
    git
    glib
    gtk3
    libnotify
    pango
    pkgconfig
  ];

  propagatedBuildInputs = with pkgs; [
    cairo
    mpv
    python38
    rnix-lsp
  ];

  shellHook = ''
    set -x
    export LD_LIBRARY_PATH=${pkgs.mpv}/lib
    export XDG_DATA_DIRS="$GSETTINGS_SCHEMA_PATH:${pkgs.arc-theme}/share:${pkgs.arc-icon-theme}/share"
    export SOURCE_DATE_EPOCH=315532800
    set +x
  '';
}
