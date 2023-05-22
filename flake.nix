{
  description = "Sublime Music development environment";
  inputs = {
    nixpkgs-unstable.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = inputs@{ nixpkgs-unstable, flake-utils, ... }:
    (flake-utils.lib.eachDefaultSystem
      (system:
        let
          pkgs = import nixpkgs-unstable { system = system; };
        in
        {
          devShells.default = pkgs.mkShell {
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
              pre-commit
            ];

            propagatedBuildInputs = with pkgs; [
              cairo
              mpv
              python310
              rnix-lsp
            ];

            shellHook = ''
              set -x
              export LD_LIBRARY_PATH=${pkgs.mpv}/lib
              export XDG_DATA_DIRS="$GSETTINGS_SCHEMA_PATH:${pkgs.arc-theme}/share:${pkgs.arc-icon-theme}/share"
              export SOURCE_DATE_EPOCH=315532800
              set +x
            '';
          };
        }
      ));
}
