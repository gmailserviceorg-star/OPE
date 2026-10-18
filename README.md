# AetherOS

AetherOS is a bootable 32-bit x86 graphical-kernel experiment with a software-rendered desktop, mouse and keyboard input, an embedded local-page browser, and the built-in **Dungeons: The Forgotten Realm** third-person voxel RPG.

## Generate the OS source tree

Run the standalone Python generator:

```bash
python forge_aetheros.py
```

It creates a folder named **AetherOS** on your Desktop (or in the current directory if no Desktop folder exists). The generator writes all project source inline; it does not download OS source dependencies.

## Build and run

Install NASM, GRUB utilities (`grub-mkrescue` and `grub-file`), xorriso, mtools, QEMU, and preferably an `i686-elf` cross-compiler. Then enter the generated folder and run:

```bash
cd AetherOS
make check
make iso
make run
```

The ISO is built at `build/AetherOS.iso`.

## Dungeons

Dungeons is an original, in-kernel voxel-style RPG prototype with a third-person avatar, camera movement, health, enemy pursuit, attacks, and relic score. Its current mobs are **Iron Guard** and **Ghosty Fly**.

Controls: **W/A/S/D** to move, **mouse movement** to look, **Space or click** to attack, and **R** to restart after defeat.

## Important limitations

The kernel renders its own GUI to the framebuffer; it is not a webpage disguised as an OS. The browser currently supports embedded local pages only and cannot browse the public internet. Networking (TCP/IP, DNS, TLS/HTTPS, real HTTP), persistent storage, user mode, paging, IRQ-driven input, audio, saved game worlds, and advanced game physics are not implemented yet. The target is legacy BIOS/GRUB under QEMU and compatible hardware.
