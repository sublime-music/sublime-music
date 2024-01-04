{
  description = "Sublime Music development environment";
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { nixpkgs, flake-utils, ... }:
    (flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { system = system; };
        nativeBuildInputs = with pkgs; [
          gobject-introspection
          python3Packages.setuptools
          wrapGAppsHook
        ];
      in {
        packages.sublime-music = pkgs.python3Packages.buildPythonApplication {
          pname = "sublime-music";
          version = "0.12.0";
          format = "flit";

          src = ./.;

          inherit nativeBuildInputs;

          buildInputs = with pkgs; [ gtk3 pango libnotify networkmanager ];

          propagatedBuildInputs = with pkgs.python3Packages; [
            bleach
            bottle
            dataclasses-json
            deepdiff
            keyring
            mpv
            peewee
            PyChromecast
            pygobject3
            python-dateutil
            python-Levenshtein
            requests
            semver
            thefuzz
          ];

          # hook for gobject-introspection doesn't like strictDeps
          # https://github.com/NixOS/nixpkgs/issues/56943
          strictDeps = false;

          # Skip checks
          doCheck = false;

          # Also run the python import check for sanity
          pythonImportsCheck = [ "sublime_music" ];

          postInstall = ''
            install -Dm444 sublime-music.desktop      -t $out/share/applications
            install -Dm444 sublime-music.metainfo.xml -t $out/share/metainfo

            for size in 16 22 32 48 64 72 96 128 192 512 1024; do
                install -Dm444 logo/rendered/"$size".png \
                  $out/share/icons/hicolor/"$size"x"$size"/apps/sublime-music.png
            done
          '';
        };

        devShells.default = pkgs.mkShell {
          inherit nativeBuildInputs;

          buildInputs = with pkgs; [
            bashInteractive
            gcc
            git
            glib
            gtk3
            libnotify
            pango
            pkg-config
            pre-commit
          ];

          propagatedBuildInputs = with pkgs; [ cairo mpv python310 rnix-lsp ];

          shellHook = ''
            set -x
            export LD_LIBRARY_PATH=${pkgs.mpv}/lib
            export XDG_DATA_DIRS="$GSETTINGS_SCHEMA_PATH:${pkgs.arc-theme}/share:${pkgs.arc-icon-theme}/share"
            export SOURCE_DATE_EPOCH=315532800
            set +x
          '';
        };
      }));
}
