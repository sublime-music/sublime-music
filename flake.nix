{
  description = "Sublime Music: a Subsonic client for Linux";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    templ = {
      url = "github:a-h/templ/v0.2.501";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, flake-utils, templ }:
    (flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        templ-pkg = templ.packages.${system}.templ;
      in {
        devShells = {
          default = pkgs.mkShell {
            packages = with pkgs; [
              dart-sass
              glib-networking
              go-tools
              gotools
              pre-commit
              templ-pkg
              wails
            ];
          };
        };
      }));
}
