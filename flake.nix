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

      # Package definition shared across systems
      mkWhatCable =
        pkgs:
        let
          pythonEnv = pkgs.python3.withPackages (ps: [
            ps.pygobject3
            ps.pytest
          ]);
        in
        pkgs.stdenv.mkDerivation (finalAttrs: {
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
            pythonEnv
          ];

          doCheck = true;

          mesonFlags = [
            "--prefix=${placeholder "out"}"
          ];

          # Ensure GApps wrapper also sees Python GI modules.
          # wrapGAppsHook4 already wraps binaries and sets GI_TYPELIB_PATH,
          # but we need to make pygobject available via PYTHONPATH.
          preFixup = ''
            gappsWrapperArgs+=(
              --prefix PYTHONPATH : "${pythonEnv}/${pythonEnv.sitePackages}"
              --prefix PYTHONPATH : "$out/${pkgs.python3.sitePackages}"
              --prefix PYTHONPATH : "$out/${pythonEnv.sitePackages}"
            )
          '';

          meta = with pkgs.lib; {
            description = "GNOME/GTK4 USB-C cable and power diagnostic viewer for Linux";
            longDescription = ''
              WhatCable reads kernel sysfs Type-C and USB Power Delivery classes
              (/sys/class/typec, /sys/class/usb_power_delivery, /sys/bus/usb/devices,
              Thunderbolt/USB4, and Framework Chrome EC via /dev/cros_ec) and
              presents a plain-English summary of each port. Provides a libadwaita
              GUI and a --json/--raw CLI without requiring root for read-only sysfs access.
            '';
            homepage = "https://github.com/nedrichards/whatcable-linux";
            license = licenses.gpl3Plus;
            maintainers = [ ];
            platforms = platforms.linux;
            mainProgram = "whatcable-linux";
          };
        });
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
          pkg = self.packages.${system}.default;
          whatcable = {
            type = "app";
            program = "${pkg}/bin/whatcable-linux";
            meta.description = "Run WhatCable";
          };
        in
        {
          default = whatcable;
          whatcable-linux = whatcable;
        }
      );

      checks = forAllSystems (system: {
        # Re-use the package's own meson test suite (pytest via meson)
        whatcable-linux = self.packages.${system}.whatcable-linux;
      });

      devShells = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        {
          default = pkgs.mkShell {
            inputsFrom = [ self.packages.${system}.whatcable-linux ];

            nativeBuildInputs = with pkgs; [
              # Build tooling (mirrors meson.build + Flatpak SDK)
              meson
              ninja
              pkg-config
              desktop-file-utils
              appstream-glib
              wrapGAppsHook4
              gobject-introspection

              # Python + GTK runtime for `python -m pytest` / running GUI outside Flatpak
              python3
              python3Packages.pygobject3
              python3Packages.pytest
              gtk4
              libadwaita
              glib

              # Lint / format (README: ruff check)
              ruff

              # AppStream / desktop validation
              appstream
              desktop-file-utils
            ];

            shellHook = ''
              echo "WhatCable devShell — ${system}"
              echo "  nix build        # meson build via Nix"
              echo "  nix run          # run GUI (alias: whatcable-linux)"
              echo "  meson setup build && meson test -C build --print-errorlogs"
              echo "  python -m pytest -q"
              echo "  ruff check src tests"
            '';
          };
        }
      );

      formatter = forAllSystems (system: nixpkgs.legacyPackages.${system}.nixfmt);
    };
}
