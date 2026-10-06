{
  description = "WhatCable - GNOME/GTK4 USB-C cable and power diagnostic viewer for Linux";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs =
    { self, nixpkgs }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAllSystems = nixpkgs.lib.genAttrs systems;

      mkWhatCable =
        pkgs:
        let
          pythonEnv = pkgs.python3.withPackages (ps: [
            ps.pygobject3
            ps.pytest
          ]);
        in
        pkgs.stdenv.mkDerivation {
          pname = "whatcable-linux";
          version = "0.1.0";

          src = ./.;

          strictDeps = true;

          nativeBuildInputs = with pkgs; [
            meson
            ninja
            pkg-config
            desktop-file-utils
            appstream-glib
            wrapGAppsHook4
            gobject-introspection
            pythonEnv
          ];

          buildInputs = with pkgs; [
            gtk4
            libadwaita
            glib
            gobject-introspection
            adwaita-icon-theme
            hicolor-icon-theme
            pythonEnv
          ];

          doCheck = true;

          mesonFlags = [
            "--prefix=${placeholder "out"}"
          ];

          preFixup = ''
            gappsWrapperArgs+=(
              --prefix PYTHONPATH : "${pythonEnv}/${pythonEnv.sitePackages}"
              --prefix PYTHONPATH : "$out/${pkgs.python3.sitePackages}"
              --prefix XDG_DATA_DIRS : "${pkgs.adwaita-icon-theme}/share"
              --prefix XDG_DATA_DIRS : "${pkgs.hicolor-icon-theme}/share"
            )
          '';

          meta = with pkgs.lib; {
            description = "GNOME/GTK4 USB-C cable and power diagnostic viewer for Linux";
            homepage = "https://github.com/nedrichards/whatcable-linux";
            license = licenses.gpl3Plus;
            platforms = platforms.linux;
            mainProgram = "whatcable-linux";
          };
        };
    in
    {
      overlays.default = final: prev: {
        whatcable-linux = mkWhatCable final;
      };

      packages = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          whatcable-linux = mkWhatCable pkgs;
        in
        {
          inherit whatcable-linux;
          default = whatcable-linux;
        }
      );

      apps = forAllSystems (
        system:
        let
          whatcable = {
            type = "app";
            program = "${self.packages.${system}.default}/bin/whatcable-linux";
            meta.description = "Run WhatCable";
          };
        in
        {
          default = whatcable;
          whatcable-linux = whatcable;
        }
      );

      devShells = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        {
          default = pkgs.mkShell {
            inputsFrom = [ self.packages.${system}.whatcable-linux ];

            nativeBuildInputs = with pkgs; [
              meson
              ninja
              pkg-config
              python3Packages.pytest
              gtk4
              libadwaita
            ];

            shellHook = ''
              echo "WhatCable devShell — ${system}"
              echo "  nix build        # meson build via Nix"
              echo "  nix run          # run GUI (alias: whatcable-linux)"
            '';
          };
        }
      );
    };
}
