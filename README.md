# MyOS

MyOS is an independent hobby operating-system project based on the bootable x86 GUI specification supplied for this repository. It is separate from any other operating-system projects in the account.

## Generate the project

Run the single-file Python generator:

```bash
python build_myos.py
```

It writes a `MyOS_Project` directory on your Desktop (or in the current directory if no Desktop directory exists), including x86 boot assembly, a freestanding C/C++ kernel, framebuffer GUI, GRUB configuration, linker script, and Makefile. No source dependencies are downloaded by the generator.

Install NASM, GRUB utilities (`grub-mkrescue`), xorriso, mtools, QEMU, and preferably an `i686-elf` cross-toolchain. Then run in the generated folder:

```bash
make check
make iso
make run
```

## Status and limitations

This is an experimental 32-bit x86 graphical-kernel starter, not a production OS. The current browser window shows embedded local content; TCP/IP, DNS/HTTP, a full HTML engine, a persistent filesystem, user mode, virtual-memory paging, and interrupt-driven input remain future work. It targets legacy BIOS and GRUB under emulators first.
