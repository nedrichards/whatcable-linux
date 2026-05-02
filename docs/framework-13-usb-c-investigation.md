# Framework 13 USB-C and USB PD Data Investigation

Date: 2026-05-02

This note records the investigation into whether WhatCable can obtain richer USB-C,
USB Power Delivery, cable identity, and e-marker information on a Framework 13
running Linux. It is intended as implementation context for future work and as
source material for a possible blog post.

## Goal

The original goal was to understand whether a Linux/GNOME version of WhatCable
could show information similar to macOS tooling, especially USB-C cable identity
and e-marker details.

The app already has useful Linux sources:

- USB device sysfs: `/sys/bus/usb/devices`
- Type-C sysfs: `/sys/class/typec`
- USB Power Delivery sysfs: `/sys/class/usb_power_delivery`
- Thunderbolt/USB4 sysfs: `/sys/bus/thunderbolt/devices`
- Chrome EC sysfs metadata: `/sys/class/chromeos/cros_ec`

The open question was whether the Framework 13 exposes deeper USB-C/PD data
through UCSI, Chrome EC host commands, Cypress CCG PD controllers, or another
Linux interface.

## Relevant Hardware And Firmware

The machine under test is a Framework 13, 11th Gen Intel style platform.

Observed DMI/sysfs identity:

```text
product_name=Laptop
board_name=FRANBMCP0A
board_vendor=Framework
sys_vendor=Framework
product_version=AA
bios_version=03.24
```

Chrome EC version information from `/sys/class/chromeos/cros_ec/version`:

```text
RO version: hx20_v0.0.1-a3deac9
Firmware copy: RO
Build info: hx20_v0.0.1-a3deac9 2025-09-01 14:53:16 runner@pkrvmccyg1gnepe
Chip vendor: mchp
Board version: 12
```

The relevant Framework EC board appears to be `hx20`.

## Public Source Repositories Consulted

Framework EC firmware:

```text
https://github.com/FrameworkComputer/EmbeddedController
```

Framework system tooling:

```text
https://github.com/FrameworkComputer/framework-system
```

Useful Framework community thread:

```text
https://community.frame.work/t/what-pd-controllers-and-can-discover-identity-usb-power-delivery-commands-be-used/79489/11
```

The community thread was useful because it points at the intended architecture:
Framework exposes UCSI, and the EC tunnels commands to the CCG PD controllers.
That means the hardware and firmware know some useful USB-C/PD state, but it
does not guarantee that every detail is surfaced to Linux userspace.

## Kernel And Sysfs Findings

The normal Linux Type-C and USB PD class interfaces were present but empty:

```text
/sys/class/typec
/sys/class/usb_power_delivery
```

No `port*` entries were present under `/sys/class/typec`, and no USB PD entries
were present under `/sys/class/usb_power_delivery`.

Relevant modules were loaded:

```text
ucsi_acpi
typec_ucsi
typec
thunderbolt
cros_usbpd_charger
cros_usbpd_logger
cros_usbpd_notify
cros_ec_chardev
cros_ec_dev
cros_ec_sysfs
cros_ec_lpcs
```

Notably, `cros_ec_typec` was not observed.

The UCSI ACPI device exists:

```text
/sys/bus/acpi/devices/USBC000:00
```

The platform driver exists:

```text
/sys/bus/platform/drivers/ucsi_acpi
```

However, `ucsi_acpi` did not appear to be bound to the `USBC000:00` device.
That explains why Type-C sysfs is empty despite UCSI-related modules being
loaded.

Thunderbolt/USB4 sysfs did expose controller/domain information:

```text
/sys/bus/thunderbolt/devices/0-0
/sys/bus/thunderbolt/devices/1-0
/sys/bus/thunderbolt/devices/domain0
/sys/bus/thunderbolt/devices/domain1
```

This is useful for the app, but it is not a substitute for cable identity.

## Chrome EC Device Access

Inside the development environment, `/dev/cros_ec` was not visible, although
`/sys/class/misc/cros_ec/dev` reported:

```text
10:262
```

On the actual host, `/dev/cros_ec` does exist:

```text
crw-------. 1 root root 10, 262 /dev/cros_ec
```

That means Chrome EC ioctl access is available to privileged host processes, but
not to a normal unprivileged Flatpak app.

Non-root access to `/dev/cros_ec` fails with permission denied. This is expected.

## Framework Tooling Results

`framework_tool` from `FrameworkComputer/framework-system` was built locally:

```sh
cd /tmp/framework-system
cargo build -p framework_tool
```

Some dependencies were needed on Fedora:

```sh
sudo dnf install -y cargo rust libusb1-devel systemd-devel
```

The useful read-only host commands were:

```sh
sudo /tmp/framework-system/target/debug/framework_tool --driver cros-ec --pdports
sudo /tmp/framework-system/target/debug/framework_tool --driver cros-ec --pd-info
sudo /tmp/framework-system/target/debug/framework_tool --driver cros-ec --pdports-chromebook
```

### `--pdports`

Result:

```text
USB-C Port 0:
[ERROR] EC Response Code: InvalidCommand
USB-C Port 1:
[ERROR] EC Response Code: InvalidCommand
USB-C Port 2:
[ERROR] EC Response Code: InvalidCommand
USB-C Port 3:
[ERROR] EC Response Code: InvalidCommand
```

In `framework-system`, `--pdports` uses Framework-specific command
`GetPdPortState`, command ID `0x3E23`.

On this firmware, that command is not implemented.

### `--pd-info`

Result:

```text
Right / Ports 01
  Silicon ID:     0x2100
  Mode:           MainFw
  Flash Row Size: 256 B
  Ports Enabled:  0, 1
  Bootloader Version:   Base: 3.1.0.388,  App: 0.0.01
  FW1 (Backup) Version: Base: 3.4.0.A10,  App: 3.8.00
  FW2 (Main)   Version: Base: 3.4.0.A10,  App: 3.8.00
Left / Ports 23
  Silicon ID:     0x2100
  Mode:           MainFw
  Flash Row Size: 256 B
  Ports Enabled:  0, 1
  Bootloader Version:   Base: 3.1.0.388,  App: 0.0.01
  FW1 (Backup) Version: Base: 3.4.0.A10,  App: 3.8.00
  FW2 (Main)   Version: Base: 3.4.0.A10,  App: 3.8.00
Back
  Failed to read Silicon ID/Family
```

This confirms that the EC can communicate with the Cypress CCG PD controllers
through I2C passthrough. The "Back" controller failure is expected on this
Framework 13 generation; there are two PD controllers, each handling two ports.

This path provides PD controller firmware and port enablement information. It
does not provide cable identity.

### `--pdports-chromebook`

Result:

```text
USB-C Port 0 (Right Back):
  Role:          Sink
  Charging Type: PD
  Voltage Now:   19.776 V, Max: 20.0 V
  Current Lim:   2250 mA, Max: 2250 mA
  Dual Role:     Charger
  Max Power:     45.0 W
USB-C Port 1 (Right Front):
  Role:          Disconnected
  Charging Type: None
  Voltage Now:   0.0 V, Max: 0.0 V
  Current Lim:   0 mA, Max: 1500 mA
  Dual Role:     Charger
  Max Power:     0.0 W
USB-C Port 2 (Left Front):
  Role:          Source
  Charging Type: None
  Voltage Now:   5.0 V, Max: 0.0 V
  Current Lim:   0 mA, Max: 1500 mA
  Dual Role:     Charger
  Max Power:     0.0 W
USB-C Port 3 (Left Back):
  Role:          Disconnected
  Charging Type: None
  Voltage Now:   0.0 V, Max: 0.0 V
  Current Lim:   0 mA, Max: 1500 mA
  Dual Role:     Charger
  Max Power:     0.0 W
```

In `framework-system`, this path uses standard Chrome EC command
`EC_CMD_USB_PD_POWER_INFO`, command ID `0x0103`.

This is the most useful currently working per-port USB-C data source. It
provides role, charging type, voltage, current, dual-role state, and max power.
It still does not provide cable identity.

## Direct Type-C Host Command Probe

A temporary read-only probe binary was added to the local `/tmp/framework-system`
checkout to test the commands that would be interesting for cable identity:

- `EC_CMD_GET_FEATURES`, command ID `0x000D`
- `EC_CMD_TYPEC_STATUS`, command ID `0x0133`
- `EC_CMD_TYPEC_DISCOVERY`, command ID `0x0131`

The probe was built with:

```sh
cd /tmp/framework-system
cargo build -p framework_tool --bin framework_typec_probe
```

It was run on the host with:

```sh
sudo /tmp/framework-system/target/debug/framework_typec_probe
```

Result:

```text
GET_FEATURES
    0000: ae e6 47 02 17 00 00 00
  UsbPd feature bit 22: true
  TypecCmd feature bit 41: false
  TypeCApVdmSend feature bit 46: false

Port 0 TYPEC_STATUS
  command 0x0133 failed: Response(InvalidCommand)
Port 0 TYPEC_DISCOVERY SOP
  command 0x0131 failed: Response(InvalidCommand)
Port 0 TYPEC_DISCOVERY SOP'
  command 0x0131 failed: Response(InvalidCommand)

Port 1 TYPEC_STATUS
  command 0x0133 failed: Response(InvalidCommand)
Port 1 TYPEC_DISCOVERY SOP
  command 0x0131 failed: Response(InvalidCommand)
Port 1 TYPEC_DISCOVERY SOP'
  command 0x0131 failed: Response(InvalidCommand)

Port 2 TYPEC_STATUS
  command 0x0133 failed: Response(InvalidCommand)
Port 2 TYPEC_DISCOVERY SOP
  command 0x0131 failed: Response(InvalidCommand)
Port 2 TYPEC_DISCOVERY SOP'
  command 0x0131 failed: Response(InvalidCommand)

Port 3 TYPEC_STATUS
  command 0x0133 failed: Response(InvalidCommand)
Port 3 TYPEC_DISCOVERY SOP
  command 0x0131 failed: Response(InvalidCommand)
Port 3 TYPEC_DISCOVERY SOP'
  command 0x0131 failed: Response(InvalidCommand)
```

This is the decisive result for cable identity on this machine. The EC advertises
USB PD support, but it does not advertise the newer Type-C command set, and it
rejects both `TYPEC_STATUS` and `TYPEC_DISCOVERY`.

That means cable identity VDOs, SOP/SOP' discovery results, SVIDs, modes, and
e-marker details are not available through these Chrome EC host commands on this
firmware.

## EC Firmware Source Findings

Relevant files in `FrameworkComputer/EmbeddedController`:

```text
board/hx20/board.h
board/hx20/ucsi.c
board/hx20/cypress5525.c
board/hx20/cypress5525.h
include/ec_commands.h
common/charge_manager.c
common/usbc/usb_pd_host.c
```

`board/hx20/board.h` defines:

```c
#define CONFIG_USB_PD_PORT_MAX_COUNT 4
```

But it also shows:

```c
/* #define CONFIG_HOSTCMD_PD */
/* #define CONFIG_HOSTCMD_PD_PANIC */
```

The newer Type-C commands are implemented in common EC code:

```c
EC_CMD_TYPEC_DISCOVERY 0x0131
EC_CMD_TYPEC_STATUS    0x0133
```

However, the host probe proves they are not enabled or exposed by this firmware
build.

The firmware does include UCSI tunnel handling in `board/hx20/ucsi.c`, including
handling for commands such as:

```text
UCSI_CMD_GET_CONNECTOR_STATUS
UCSI_CMD_GET_PDOS
UCSI_CMD_GET_CABLE_PROPERTY
UCSI_CMD_GET_ALTERNATE_MODES
```

This suggests the EC/PD-controller side has UCSI handling, but on this Linux
installation it is not becoming useful Type-C sysfs data. The `ucsi_acpi` driver
exists but does not appear to bind and create Type-C class ports.

## What We Can Reliably Show In WhatCable

For this Framework 13 setup, the app can realistically show:

- USB topology and devices from `/sys/bus/usb/devices`
- Thunderbolt and USB4 domains/controllers from `/sys/bus/thunderbolt/devices`
- Chrome EC firmware identity from `/sys/class/chromeos/cros_ec`
- Per-port USB-C power state from `EC_CMD_USB_PD_POWER_INFO`
- Cypress CCG PD controller details from EC I2C passthrough:
  - silicon ID
  - firmware mode
  - flash row size
  - enabled ports
  - bootloader, backup, and main firmware versions

These are all valuable, even though they are not e-marker details.

## What We Should Not Promise On This Machine

On this Framework 13 firmware, we should not promise:

- Cable identity VDOs
- Cable e-marker details
- Discover Identity results
- SOP/SOP' discovery data
- SVID and mode lists from Chrome EC Type-C discovery
- Rich Type-C status from `EC_CMD_TYPEC_STATUS`

The correct UI language is "unavailable on this firmware/path", not "no cable
identity exists".

## Flatpak And Permission Implications

The app can read ordinary sysfs paths as a Flatpak with suitable filesystem
permissions, but it cannot directly use `/dev/cros_ec` in the normal Flatpak
security model.

The Chrome EC device node is:

```text
/dev/cros_ec
```

and on the host it is:

```text
crw------- root root
```

Therefore, a Flatpak app cannot directly call Chrome EC ioctls unless the user
weakens permissions substantially. That is not a good default design.

If WhatCable includes Framework EC data, the likely architecture is:

1. GTK/libadwaita Flatpak app for the UI.
2. Normal unprivileged sysfs backends inside the app.
3. Optional privileged host helper for `/dev/cros_ec`.
4. Helper exposes a narrow, read-only API for specific known-safe queries.
5. UI clearly labels the source and permission state.

The helper should not expose arbitrary EC command execution.

## Recommendations

### Short Term

Build the app around data sources that already work without privileged access:

- USB sysfs
- Thunderbolt/USB4 sysfs
- Type-C and USB PD sysfs when present
- Chrome EC sysfs metadata when readable

Add a diagnostic section that explains why a source is unavailable:

- `/sys/class/typec` exists but has no ports
- `/sys/class/usb_power_delivery` exists but is empty
- `/dev/cros_ec` exists but is root-only
- EC supports `UsbPd` but not `TypecCmd`
- `TYPEC_DISCOVERY` returned `InvalidCommand`

This will make the app useful on many machines without over-promising.

### Medium Term

Prototype a read-only Framework EC helper that queries:

- `EC_CMD_USB_PD_POWER_INFO`
- PD controller firmware info through the same safe paths used by
  `framework_tool --pd-info`

This would allow WhatCable to show meaningful Framework-specific USB-C data:

- port connected/disconnected state
- sink/source role
- charging type
- negotiated voltage/current
- max power
- PD controller firmware versions

The helper should return structured data, not terminal text.

### Long Term

Investigate why `ucsi_acpi` does not bind to `USBC000:00` on this installation.
If that can be fixed at the kernel/firmware/ACPI level, the app may get richer
data through standard Linux Type-C sysfs without needing a Framework-specific
helper.

Also test newer Framework models and firmware revisions. Some may expose:

- Type-C command feature bit 41
- `EC_CMD_TYPEC_STATUS`
- `EC_CMD_TYPEC_DISCOVERY`
- `/sys/class/typec/port*`
- `/sys/class/usb_power_delivery/*`

Those machines could support cable identity or at least richer Type-C state.

## Blog Post Angle

A useful blog post could be structured around the idea that "USB-C cable
inspection on Linux is not one API".

Possible outline:

1. Start with the goal: showing USB-C cable and port details in a GNOME app.
2. Explain Linux's standard interfaces: USB sysfs, Type-C sysfs, USB PD sysfs,
   Thunderbolt sysfs.
3. Show the surprise: Framework 13 has UCSI and Chrome EC modules loaded, but
   Type-C sysfs is empty.
4. Follow the firmware trail into Framework EC and `framework_tool`.
5. Show what works:
   - Chrome EC USB PD power info
   - Cypress PD controller firmware info
6. Show what does not work:
   - Type-C discovery host commands return `InvalidCommand`
   - cable identity is not exposed on this firmware path
7. Discuss app design:
   - source confidence
   - capability detection
   - optional privileged helper
   - honest UI labels

The main lesson is that the hardware may know more than Linux userspace can
currently access through stable, unprivileged interfaces.

