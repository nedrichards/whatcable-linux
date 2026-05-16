{
  description = "WhatCable — GNOME/GTK4 USB-C cable and power diagnostic viewer for Linux";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachSystem [ "x86_64-linux" "aarch64-linux" ] (system:
      let
        pkgs = import nixpkgs { inherit system; };
        python = pkgs.python3.withPackages (ps: [ ps.pytest ps.pygobject3 ]);

        # Extract version from src/whatcable_linux/__init__.py
        initFile = builtins.readFile ./src/whatcable_linux/__init__.py;
        versionMatch = builtins.match ''.*__version__ = "([^"]+)".*'' initFile;
        version = if versionMatch != null then builtins.head versionMatch else "0.1.0";

        whatcable = pkgs.stdenv.mkDerivation (finalAttrs: {
          pname = "whatcable-linux";
          inherit version;

          src = ./.;

          strictDeps = true;

          nativeBuildInputs = with pkgs; [
            meson
            ninja
            pkg-config
            wrapGAppsHook4
            gobject-introspection
            desktop-file-utils
            python
          ];

          buildInputs = with pkgs; [
            gtk4
            libadwaita
          ];

          doCheck = true;

          # wrapGAppsHook4 wires GI typelibs + GSettings; we add PYTHONPATH
          # so the installed launcher finds whatcable_linux module.
          preFixup = ''
            gappsWrapperArgs+=(
              --prefix PYTHONPATH : "$out/${python.sitePackages}"
            )
          '';

          meta = with pkgs.lib; {
            description = "GNOME/GTK4 USB-C cable and power diagnostic viewer";
            homepage = "https://github.com/nedrichards/whatcable-linux";
            license = licenses.gpl3Plus;
            platforms = platforms.linux;
            mainProgram = "whatcable-linux";
          };
        });
      in
      {
        packages = {
          default = whatcable;
          whatcable-linux = whatcable;
        };

        apps.default = {
          type = "app";
          program = "${whatcable}/bin/whatcable-linux";
        };

        devShells.default = pkgs.mkShell {
          name = "whatcable-linux-dev";
          inputsFrom = [ whatcable ];
          packages = with pkgs; [
            flatpak
            flatpak-builder
          ];
          shellHook = ''
            export PYTHONPATH="$PWD/src''${PYTHONPATH:+:$PYTHONPATH}"
          '';
        };

        formatter = pkgs.nixpkgs-fmt;
      });
}
