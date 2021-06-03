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
    gobjectIntrospection
    gtk3
    libnotify
    pango
    pkgconfig
  ];

  propagatedBuildInputs = with pkgs; [
    cairo
    mpv
    poetry
    (
      python38.withPackages (
        ps: with ps; [
          jedi
          neovim
        ]
      )
    )
    rnix-lsp
  ];

  shellHook = ''
    set -x
    export LD_LIBRARY_PATH=${pkgs.mpv}/lib
    export XDG_DATA_DIRS="$GSETTINGS_SCHEMA_PATH:${pkgs.arc-theme}/share:${pkgs.arc-icon-theme}/share"
    export SOURCE_DATE_EPOCH=315532800

    # An update happened to the shell.nix, so remove and reinstall everything in the virtualenv
    rm -rf .venv
    poetry install -E chromecast -E keyring -E server
    set +x
  '';
}
