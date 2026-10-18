# CandyOS

CandyOS is a hobby operating-system project targeting legacy BIOS x86 PCs and QEMU. This repository includes the single-file Python project generator `build_candyos.py`.

## Generate the project

Run with Python 3:

```bash
python build_candyos.py
```

The generator creates `CandyOS_Project` on your Desktop (or in the current directory if no Desktop directory exists). It writes NASM boot code, a freestanding C/C++ kernel, framebuffer GUI, GRUB configuration, linker script, and Makefile.

Install NASM, GRUB utilities (`grub-mkrescue`), QEMU, and preferably an `i686-elf` cross-toolchain. In the generated directory, run:

```bash
make check
make iso
make run
```

## Scope and limitations

This is a bootable graphical-kernel starter, not a production operating system. The initial browser displays an embedded welcome page; a real TCP/IP stack, DNS/HTTP, full HTML engine, protected user mode, paging, persistent filesystem, and interrupt-driven input remain future work. Framebuffer modes and input behavior depend on firmware/emulator support. The primary target is 32-bit x86 under legacy BIOS/GRUB.
