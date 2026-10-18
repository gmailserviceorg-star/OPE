#!/usr/bin/env python3
"""Generate a bootable CandyOS graphical-kernel project without downloading files."""
from pathlib import Path
import shutil
import subprocess
import sys

PROJECT_NAME = "CandyOS_Project"
FILES = {
"Makefile": r"""
CROSS := $(shell command -v i686-elf-g++ 2>/dev/null)
ifeq ($(CROSS),)
  CXX := g++
  CC := gcc
  LD := ld
  TARGET_FLAGS := -m32
  $(warning i686-elf toolchain not found; trying host GCC/G++ with -m32)
else
  CXX := i686-elf-g++
  CC := i686-elf-gcc
  LD := i686-elf-ld
  TARGET_FLAGS :=
endif
NASM := nasm
GRUB_MKRESCUE := grub-mkrescue
CXXFLAGS := $(TARGET_FLAGS) -std=c++17 -ffreestanding -fno-pie -fno-stack-protector -fno-exceptions -fno-rtti -fno-use-cxa-atexit -fno-builtin -nostdlib -O2 -Wall -Wextra
CFLAGS := $(TARGET_FLAGS) -ffreestanding -fno-pie -fno-stack-protector -fno-builtin -nostdlib -O2 -Wall -Wextra
LDFLAGS := -m elf_i386 -T linker.ld -nostdlib
CPP_SOURCES := $(shell find src -name '*.cpp')
C_SOURCES := $(shell find src -name '*.c')
CPP_OBJECTS := $(patsubst src/%.cpp,build/%.o,$(CPP_SOURCES))
C_OBJECTS := $(patsubst src/%.c,build/%.o,$(C_SOURCES))
OBJECTS := build/boot/boot.o $(CPP_OBJECTS) $(C_OBJECTS)
KERNEL := build/candyos.elf

.PHONY: all check iso run debug clean
all: iso

check:
	@command -v $(NASM) >/dev/null || { echo "Missing NASM. Install NASM and retry."; exit 1; }
	@command -v $(GRUB_MKRESCUE) >/dev/null || { echo "Missing grub-mkrescue. Install GRUB utilities and xorriso."; exit 1; }
	@command -v $(CXX) >/dev/null || { echo "Missing C++ compiler: $(CXX)"; exit 1; }
	@command -v $(LD) >/dev/null || { echo "Missing linker: $(LD)"; exit 1; }
	@command -v qemu-system-i386 >/dev/null || echo "Note: QEMU is not installed; ISO can still be built."
	@echo "Toolchain commands found."

build/boot/boot.o: src/boot/boot.asm
	@mkdir -p $(@D)
	$(NASM) -f elf32 $< -o $@

build/%.o: src/%.cpp
	@mkdir -p $(@D)
	$(CXX) $(CXXFLAGS) -c $< -o $@

build/%.o: src/%.c
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) -c $< -o $@

$(KERNEL): $(OBJECTS) linker.ld
	@mkdir -p build
	$(LD) $(LDFLAGS) -o $@ $(OBJECTS)
	@grub-file --is-x86-multiboot $@ 2>/dev/null && echo "Multiboot header verified." || echo "Warning: grub-file unavailable or header check failed."

iso: check $(KERNEL)
	@mkdir -p iso_root/boot/grub
	cp $(KERNEL) iso_root/boot/candyos.elf
	cp grub.cfg iso_root/boot/grub/grub.cfg
	$(GRUB_MKRESCUE) -o build/CandyOS.iso iso_root
	@echo "Created build/CandyOS.iso"

run: iso
	qemu-system-i386 -m 128M -cdrom build/CandyOS.iso

debug: iso
	qemu-system-i386 -m 128M -cdrom build/CandyOS.iso -no-reboot -no-shutdown -d int,cpu_reset

clean:
	rm -rf build iso_root
""",
"linker.ld": r"""
ENTRY(_start)
SECTIONS
{
    . = 1M;
    .multiboot ALIGN(4) : { KEEP(*(.multiboot)) }
    .text ALIGN(16) : { *(.text*) }
    .rodata ALIGN(16) : { *(.rodata*) }
    .data ALIGN(16) : { *(.data*) }
    .bss ALIGN(16) : { *(COMMON) *(.bss*) }
}
""",
"grub.cfg": r"""
set timeout=0
set default=0
menuentry "CandyOS" {
    multiboot /boot/candyos.elf
    boot
}
""",
"src/boot/boot.asm": r"""
BITS 32
section .multiboot
align 4
MB_MAGIC equ 0x1BADB002
MB_FLAGS equ 0x00000007
dd MB_MAGIC
dd MB_FLAGS
dd -(MB_MAGIC + MB_FLAGS)
dd 0
dd 1024
dd 768
dd 32

section .bss
align 16
stack_bottom:
    resb 16384
stack_top:

section .text
global _start
extern kernel_main
_start:
    cli
    mov esp, stack_top
    xor ebp, ebp
    push ebx
    push eax
    call kernel_main
.hang:
    cli
    hlt
    jmp .hang
""",
"src/lib/memory.c": r"""
#include <stddef.h>
void *memset(void *dst, int value, size_t n) {
    unsigned char *p = (unsigned char *)dst;
    for (size_t i = 0; i < n; ++i) p[i] = (unsigned char)value;
    return dst;
}
void *memcpy(void *dst, const void *src, size_t n) {
    unsigned char *d = (unsigned char *)dst;
    const unsigned char *s = (const unsigned char *)src;
    for (size_t i = 0; i < n; ++i) d[i] = s[i];
    return dst;
}
void *memmove(void *dst, const void *src, size_t n) {
    unsigned char *d = (unsigned char *)dst;
    const unsigned char *s = (const unsigned char *)src;
    if (d < s) for (size_t i = 0; i < n; ++i) d[i] = s[i];
    else if (d > s) for (size_t i = n; i; --i) d[i - 1] = s[i - 1];
    return dst;
}
int memcmp(const void *a, const void *b, size_t n) {
    const unsigned char *x = (const unsigned char *)a, *y = (const unsigned char *)b;
    for (size_t i = 0; i < n; ++i) if (x[i] != y[i]) return x[i] < y[i] ? -1 : 1;
    return 0;
}
size_t strlen(const char *s) { size_t n = 0; while (s[n]) ++n; return n; }
int strcmp(const char *a, const char *b) {
    while (*a && *a == *b) { ++a; ++b; }
    return (unsigned char)*a - (unsigned char)*b;
}
""",
"src/kernel/kernel.cpp": r"""
#include <stdint.h>
#include <stddef.h>
typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;
typedef unsigned long long u64;

struct __attribute__((packed)) MultibootInfo {
    u32 flags, mem_lower, mem_upper, boot_device, cmdline, mods_count, mods_addr;
    u32 syms[4];
    u32 mmap_length, mmap_addr, drives_length, drives_addr, config_table;
    u32 boot_loader_name, apm_table, vbe_control_info, vbe_mode_info;
    u16 vbe_mode, vbe_interface_seg, vbe_interface_off, vbe_interface_len;
    u64 framebuffer_addr;
    u32 framebuffer_pitch, framebuffer_width, framebuffer_height;
    u8 framebuffer_bpp, framebuffer_type;
};
static u32 *framebuffer=0, fbPitch=0, screenW=1024, screenH=768;
static u32 back[1280*800];
static int mouseX=300,mouseY=220,mouseButtons=0,oldButtons=0;
static bool menuOpen=false,alternateWallpaper=false,animations=true;
static int activeWindow=-1,dragWindow=-1,dragDX=0,dragDY=0;
static int paintColor=0x00E4A85B;
static int paintX[512],paintY[512],paintCount=0;
static char terminalInput[128],editorText[512],calcInput[64];
static int terminalLen=0,editorLen=0,calcLen=0;
static char terminalOutput[4][72]={"CANDYOS TERMINAL","Type HELP for commands.","",""};
static const u32 C_ACCENT=0x004E96D8, C_DARK=0x00101822;
static const char FONTCHARS[]="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-.:/!?()[]";
static const char FONTDATA[]=
"25755" "65656" "34443" "65556" "74647" "74644" "34553" "55755"
"72227" "11152" "55655" "44447" "57755" "57775" "25552" "65644"
"25573" "65655" "34216" "72222" "55557" "55552" "55775" "55255"
"55222" "71247" "75557" "26227" "61247" "61216" "55711" "74616"
"34652" "71222" "25252" "25316" "00700" "00002" "02020" "11244"
"22202" "61002" "14441" "41114" "14441" "42224";

static inline u8 inb(u16 p){u8 v;__asm__ volatile("inb %1, %0":"=a"(v):"Nd"(p));return v;}
static inline void outb(u16 p,u8 v){__asm__ volatile("outb %0, %1"::"a"(v),"Nd"(p));}
static void pauseTiny(){for(volatile int i=0;i<1800;++i)__asm__ volatile("pause");}
static u32 rgb(int r,int g,int b){return ((u32)(r&255)<<16)|((u32)(g&255)<<8)|(u32)(b&255);}
static void pixel(int x,int y,u32 c){if(x>=0&&y>=0&&x<(int)screenW&&y<(int)screenH)back[y*screenW+x]=c;}
static void rect(int x,int y,int w,int h,u32 c){
 if(w<=0||h<=0)return;int x0=x<0?0:x,y0=y<0?0:y,x1=x+w>(int)screenW?(int)screenW:x+w,y1=y+h>(int)screenH?(int)screenH:y+h;
 for(int yy=y0;yy<y1;++yy)for(int xx=x0;xx<x1;++xx)back[yy*screenW+xx]=c;
}
static void frame(int x,int y,int w,int h,u32 c){rect(x,y,w,1,c);rect(x,y+h-1,w,1,c);rect(x,y,1,h,c);rect(x+w-1,y,1,h,c);}
static void drawChar(int x,int y,char ch,u32 color,int scale=2){
 if(ch>='a'&&ch<='z')ch=(char)(ch-'a'+'A');if(ch==' ')return;int ix=-1;
 for(int i=0;FONTCHARS[i];++i)if(FONTCHARS[i]==ch){ix=i;break;}if(ix<0)return;
 for(int row=0;row<5;++row){int bits=FONTDATA[ix*5+row]-'0';for(int col=0;col<3;++col)if(bits&(4>>col))rect(x+col*scale,y+row*scale,scale,scale,color);}
}
static void text(int x,int y,const char*s,u32 c,int scale=2){
 int start=x;while(*s){if(*s=='\n'){y+=13*scale/2;x=start;++s;continue;}drawChar(x,y,*s,c,scale);x+=4*scale;if(x>(int)screenW-8)break;++s;}
}
static void multiline(int x,int y,const char*s,u32 c,int width,int scale=2){
 int ox=x;while(*s){if(*s=='\n'||x>ox+width-8){y+=14;x=ox;if(*s=='\n'){++s;continue;}}drawChar(x,y,*s,c,scale);x+=4*scale;++s;if(y>(int)screenH-65)break;}
}
static void present(){
 if(!framebuffer)return;
 for(u32 y=0;y<screenH;++y){volatile u32*dst=(volatile u32*)((u8*)framebuffer+y*fbPitch);for(u32 x=0;x<screenW;++x)dst[x]=back[y*screenW+x];}
}
enum App{BROWSER=0,FILES=1,TERMINAL=2,EDITOR=3,PAINT=4,CALCULATOR=5,SETTINGS=6};
struct Window{bool open;int x,y,w,h;};
static Window wins[7];
static const char*appNames[7]={"Browser","File Manager","Terminal","Text Editor","Paint","Calculator","Settings"};
static void openApp(int app){
 if(app<0||app>6)return;wins[app].open=true;wins[app].x=(int)screenW/2-175+(app%3)*12;wins[app].y=(int)screenH/2-120+(app%3)*10;wins[app].w=350;wins[app].h=240;
 if(wins[app].x<12)wins[app].x=12;if(wins[app].y<20)wins[app].y=20;activeWindow=app;menuOpen=false;
}
static int windowAt(int x,int y){
 if(activeWindow>=0&&wins[activeWindow].open){Window a=wins[activeWindow];if(x>=a.x&&x<a.x+a.w&&y>=a.y&&y<a.y+a.h)return activeWindow;}
 for(int i=6;i>=0;--i)if(wins[i].open){Window a=wins[i];if(x>=a.x&&x<a.x+a.w&&y>=a.y&&y<a.y+a.h)return i;}return -1;
}
static void background(){
 for(u32 y=0;y<screenH;++y){int r=alternateWallpaper?19:22,g=alternateWallpaper?59:51,b=alternateWallpaper?69:72;u32 c=rgb(r+(int)(y*18/screenH),g+(int)(y*39/screenH),b+(int)(y*58/screenH));for(u32 x=0;x<screenW;++x)back[y*screenW+x]=c;}
 for(int i=0;i<5;++i)rect((int)(screenW*.54)+i*24,40+i*27,260-i*22,2,0x00364D61);
 text(28,22,"CANDYOS",0x00FFFFFF,3);text(29,45,"A SMALL X86 DESKTOP",0x00C4D8E8,1);
}
static void drawIcon(int x,int y,int app){
 u32 c=app==BROWSER?0x004BB6C9:app==FILES?0x00D8B65C:app==TERMINAL?0x00222A36:app==EDITOR?0x007F9DD0:app==PAINT?0x00D87D6C:app==CALCULATOR?0x0071B88B:0x009C8BD5;
 rect(x,y,42,36,0x00132230);rect(x+3,y+3,36,30,c);frame(x+3,y+3,36,30,0x00FFFFFF);
 if(app==BROWSER){rect(x+12,y+10,18,16,0x00FFFFFF);rect(x+14,y+12,14,12,c);rect(x+12,y+17,18,2,0x00FFFFFF);}
 else if(app==FILES){rect(x+9,y+11,25,17,0x00F2D27D);rect(x+9,y+8,12,5,0x00F2D27D);}
 else if(app==TERMINAL)text(x+9,y+11,">_",0x00FFFFFF,2);
 else if(app==EDITOR){rect(x+12,y+8,18,21,0x00FFFFFF);rect(x+16,y+13,11,2,c);rect(x+16,y+18,11,2,c);}
 else if(app==PAINT){rect(x+10,y+8,18,18,0x00F6C7A0);pixel(x+17,y+14,0x00CC3655);pixel(x+22,y+19,0x003C65D5);}
 else if(app==CALCULATOR){rect(x+11,y+7,20,23,0x00FFFFFF);rect(x+14,y+10,14,4,0x00B8C7D4);for(int k=0;k<3;++k)for(int j=0;j<2;++j)rect(x+14+j*7,y+17+k*4,4,2,c);}
 else{rect(x+12,y+8,18,18,0x00FFFFFF);for(int k=0;k<8;k+=2)rect(x+18,y+8+k,6,1,c);}
}
static void drawTaskbar(){
 rect(0,(int)screenH-42,(int)screenW,42,C_DARK);rect(0,(int)screenH-42,(int)screenW,1,0x004F6475);
 rect(9,(int)screenH-35,72,28,C_ACCENT);text(20,(int)screenH-27,"START",0x00FFFFFF,2);
 int x=92;for(int i=0;i<7;++i)if(wins[i].open&&x<(int)screenW-100){rect(x,(int)screenH-34,82,25,i==activeWindow?0x003D5265:0x00232F3D);text(x+6,(int)screenH-25,appNames[i],0x00FFFFFF,1);x+=86;}
 text((int)screenW-82,(int)screenH-27,"CANDY",0x00D4E1EB,1);
}
static void drawWindow(int app){
 Window a=wins[app];if(!a.open)return;rect(a.x+5,a.y+7,a.w,a.h,0x00304050);rect(a.x,a.y,a.w,a.h,0x00E5EAF0);
 rect(a.x,a.y,a.w,30,app==activeWindow?C_ACCENT:0x005C6B7B);text(a.x+10,a.y+10,appNames[app],0x00FFFFFF,2);
 rect(a.x+a.w-25,a.y+5,18,19,0x00C95C57);text(a.x+a.w-20,a.y+11,"X",0x00FFFFFF,1);
 rect(a.x+1,a.y+31,a.w-2,a.h-32,0x00F4F6F8);int x=a.x+12,y=a.y+44;
 if(app==BROWSER){rect(x,y,a.w-24,25,0x00FFFFFF);frame(x,y,a.w-24,25,0x00C7D0D8);text(x+6,y+8,"candy.local/welcome",0x004B657A,1);text(x,y+40,"WELCOME TO CANDYOS",0x002A537A,2);multiline(x,y+61,"This page is stored inside the kernel.\nThe next milestone is a real network\nstack and a fuller HTML renderer.",0x00334657,a.w-28,1);}
 else if(app==FILES){text(x,y,"RAM DISK",0x002A537A,2);text(x+5,y+32,"[DIR]  /",0x004B657A,1);text(x+15,y+52,"README.TXT",0x00334657,1);text(x+15,y+70,"ABOUT.TXT",0x00334657,1);text(x+15,y+88,"NOTES.TXT",0x00334657,1);text(x,y+124,"Files are demo entries in RAM.",0x0061707C,1);}
 else if(app==TERMINAL){rect(x-4,y-5,a.w-16,a.h-49,0x00121A22);for(int i=0;i<4;++i)text(x,y+i*17,terminalOutput[i],0x007DE0A3,1);text(x,y+78,"CANDY:/ >",0x007DE0A3,1);text(x+68,y+78,terminalInput,0x00FFFFFF,1);}
 else if(app==EDITOR){text(x,y,"UNTITLED.TXT | RAM",0x003E5E77,1);rect(x-3,y+19,a.w-20,a.h-74,0x00FFFFFF);frame(x-3,y+19,a.w-20,a.h-74,0x00D3DCE4);multiline(x,y+27,editorText,0x002E4050,a.w-38,1);text(x,y+a.h-31,"TYPE TO EDIT - ENTER NEW LINE",0x0061707C,1);}
 else if(app==PAINT){text(x,y,"PALETTE",0x003E5E77,1);for(int i=0;i<4;++i)rect(x+58+i*24,y-2,18,15,i==0?0x00E4A85B:i==1?0x00D75E67:i==2?0x004E96D8:0x00369B79);rect(x-4,y+21,a.w-20,a.h-75,0x00FFFFFF);frame(x-4,y+21,a.w-20,a.h-75,0x00CAD4DE);for(int i=0;i<paintCount;++i)for(int q=0;q<4;++q)pixel(paintX[i]+q%2,paintY[i]+q/2,paintColor);text(x,y+a.h-31,"DRAG THE MOUSE TO DRAW",0x0061707C,1);}
 else if(app==CALCULATOR){rect(x,y,a.w-24,27,0x00FFFFFF);frame(x,y,a.w-24,27,0x00C7D0D8);text(x+6,y+8,calcLen?calcInput:"0",0x00334657,2);const char*keys="789/456*123-0.=+";for(int i=0;i<16;++i){int bx=x+(i%4)*46,by=y+38+(i/4)*29;rect(bx,by,40,24,(keys[i]=='/'||keys[i]=='*'||keys[i]=='-'||keys[i]=='+')?0x00DCE8F2:0x00FFFFFF);frame(bx,by,40,24,0x00C7D0D8);char label[2]={keys[i],0};text(bx+14,by+8,label,0x00334657,1);}}
 else{text(x,y,"SYSTEM SETTINGS",0x003E5E77,1);text(x,y+28,"RESOLUTION: FRAMEBUFFER",0x00334657,1);text(x,y+49,"MODE: 32-BIT PROTECTED",0x00334657,1);text(x,y+70,animations?"ANIMATIONS: ON":"ANIMATIONS: OFF",0x00334657,1);rect(x,y+96,150,27,C_ACCENT);text(x+10,y+105,"CHANGE WALLPAPER",0x00FFFFFF,1);text(x,y+139,"CLICK BUTTON TO CHANGE COLOR",0x0061707C,1);}
}
static void drawStartMenu(){
 if(!menuOpen)return;int x=10,y=(int)screenH-42-264;rect(x+4,y+5,220,264,0x00304050);rect(x,y,220,264,0x00F0F3F6);frame(x,y,220,264,0x00AAB7C2);rect(x,y,220,37,0x002D4E6A);text(x+12,y+13,"CANDYOS APPS",0x00FFFFFF,2);
 for(int i=0;i<7;++i){drawIcon(x+10,y+45+i*30,i);text(x+63,y+58+i*30,appNames[i],0x002A3F51,1);}
}
static void drawCursor(){for(int i=0;i<13;++i)for(int j=0;j<=i/2;++j)pixel(mouseX+j,mouseY+i,0x00FFFFFF);for(int i=1;i<12;++i)pixel(mouseX+i/2,mouseY+i,0x00101822);}
static void render(){
 background();for(int i=0;i<7;++i){int x=25,y=83+i*78;drawIcon(x,y,i);text(x-2,y+43,appNames[i],0x00FFFFFF,1);}
 for(int i=0;i<7;++i)if(i!=activeWindow)drawWindow(i);if(activeWindow>=0)drawWindow(activeWindow);drawTaskbar();drawStartMenu();drawCursor();present();
}
static void terminalCommand(){
 for(int i=0;i<4;++i)terminalOutput[i][0]=0;
 if(!terminalLen)return;terminalInput[terminalLen]=0;
 if(!__builtin_strcmp(terminalInput,"help"))__builtin_strcpy(terminalOutput[0],"HELP LS CLEAR ABOUT ECHO REBOOT");
 else if(!__builtin_strcmp(terminalInput,"ls"))__builtin_strcpy(terminalOutput[0],"/ README.TXT ABOUT.TXT NOTES.TXT");
 else if(!__builtin_strcmp(terminalInput,"about"))__builtin_strcpy(terminalOutput[0],"CANDYOS X86 GUI KERNEL");
 else if(!__builtin_strncmp(terminalInput,"echo ",5)){__builtin_strncpy(terminalOutput[0],terminalInput+5,70);terminalOutput[0][70]=0;}
 else if(!__builtin_strcmp(terminalInput,"clear"))terminalOutput[0][0]=0;
 else if(!__builtin_strcmp(terminalInput,"reboot")||!__builtin_strcmp(terminalInput,"shutdown")){__asm__ volatile("cli");for(;;)__asm__ volatile("hlt");}
 else __builtin_strcpy(terminalOutput[0],"UNKNOWN COMMAND - TYPE HELP");
 terminalLen=0;terminalInput[0]=0;
}
static char keyChar(u8 sc){
 switch(sc){
 case 0x02:return '1';case 0x03:return '2';case 0x04:return '3';case 0x05:return '4';case 0x06:return '5';case 0x07:return '6';case 0x08:return '7';case 0x09:return '8';case 0x0A:return '9';case 0x0B:return '0';case 0x0C:return '-';case 0x0D:return '=';
 case 0x10:return 'q';case 0x11:return 'w';case 0x12:return 'e';case 0x13:return 'r';case 0x14:return 't';case 0x15:return 'y';case 0x16:return 'u';case 0x17:return 'i';case 0x18:return 'o';case 0x19:return 'p';case 0x1A:return '[';case 0x1B:return ']';
 case 0x1E:return 'a';case 0x1F:return 's';case 0x20:return 'd';case 0x21:return 'f';case 0x22:return 'g';case 0x23:return 'h';case 0x24:return 'j';case 0x25:return 'k';case 0x26:return 'l';case 0x27:return ';';case 0x28:return '\'';case 0x2C:return 'z';case 0x2D:return 'x';case 0x2E:return 'c';case 0x2F:return 'v';case 0x30:return 'b';case 0x31:return 'n';case 0x32:return 'm';case 0x33:return ',';case 0x34:return '.';case 0x35:return '/';case 0x39:return ' ';case 0x0E:return '\b';case 0x1C:return '\n';default:return 0;
 }
}
static void calcKey(char c){
 if(c=='\b'){if(calcLen)calcInput[--calcLen]=0;return;}
 if(c=='='){int i=0;long a=0,b=0;while(calcInput[i]>='0'&&calcInput[i]<='9'){a=a*10+calcInput[i]-'0';++i;}char op=calcInput[i++];while(calcInput[i]>='0'&&calcInput[i]<='9'){b=b*10+calcInput[i]-'0';++i;}long r=0;if(op=='+')r=a+b;else if(op=='-')r=a-b;else if(op=='*')r=a*b;else if(op=='/'&&b)r=a/b;calcLen=0;if(r<0){calcInput[calcLen++]='-';r=-r;}char rev[24];int n=0;do{rev[n++]=(char)('0'+r%10);r/=10;}while(r&&n<22);while(n)calcInput[calcLen++]=rev[--n];calcInput[calcLen]=0;return;}
 if((c>='0'&&c<='9')||c=='+'||c=='-'||c=='*'||c=='/')if(calcLen<60){calcInput[calcLen++]=c;calcInput[calcLen]=0;}
}
static void keyboard(u8 sc){
 if(sc&0x80)return;if(sc==0x01){if(activeWindow>=0)wins[activeWindow].open=false;activeWindow=-1;return;}char c=keyChar(sc);if(!c||activeWindow<0)return;
 if(activeWindow==TERMINAL){if(c=='\n')terminalCommand();else if(c=='\b'){if(terminalLen)terminalInput[--terminalLen]=0;}else if(c>=32&&terminalLen<120){terminalInput[terminalLen++]=c;terminalInput[terminalLen]=0;}}
 else if(activeWindow==EDITOR){if(c=='\b'){if(editorLen)editorText[--editorLen]=0;}else if((c=='\n'||c>=32)&&editorLen<500){editorText[editorLen++]=c;editorText[editorLen]=0;}}
 else if(activeWindow==CALCULATOR)calcKey(c);
}
static void mouseInit(){outb(0x64,0xA8);for(volatile int i=0;i<10000;++i){}outb(0x64,0xD4);outb(0x60,0xF4);for(volatile int i=0;i<40000;++i){}while(inb(0x64)&1)(void)inb(0x60);}
static void handleClick(int x,int y){
 if(y>(int)screenH-42&&x<86){menuOpen=!menuOpen;return;}
 if(menuOpen){int top=(int)screenH-42-264;if(x>=10&&x<230&&y>=top+40&&y<top+258){int app=(y-(top+40))/30;if(app>=0&&app<7)openApp(app);menuOpen=false;return;}menuOpen=false;}
 int hit=windowAt(x,y);
 if(hit>=0){activeWindow=hit;Window&a=wins[hit];if(y<a.y+30){if(x>a.x+a.w-28){a.open=false;activeWindow=-1;return;}dragWindow=hit;dragDX=x-a.x;dragDY=y-a.y;return;}
  if(hit==PAINT){if(y<a.y+69){if(x<a.x+75)paintColor=0x00E4A85B;else if(x<a.x+99)paintColor=0x00D75E67;else if(x<a.x+123)paintColor=0x004E96D8;else paintColor=0x00369B79;}else if(paintCount<512){paintX[paintCount]=x;paintY[paintCount++]=y;}}
  else if(hit==SETTINGS)alternateWallpaper=!alternateWallpaper;
  else if(hit==CALCULATOR){int bx=a.x+12,by=a.y+44+38;int col=(x-bx)/46,row=(y-by)/29;if(col>=0&&col<4&&row>=0&&row<4)calcKey("789/456*123-0.=+"[row*4+col]);}
  return;
 }
 if(y<(int)screenH-55&&x<108){int app=(y-83)/78;if(app>=0&&app<7)openApp(app);}
}
static void pollInput(){
 for(int n=0;n<16;++n){u8 st=inb(0x64);if(!(st&1))break;u8 v=inb(0x60);
  if(st&0x20){static int phase=0;static u8 packet[3];packet[phase++]=v;if(phase==3){phase=0;oldButtons=mouseButtons;mouseButtons=packet[0]&7;mouseX+=(signed char)packet[1];mouseY-=(signed char)packet[2];if(mouseX<0)mouseX=0;if(mouseY<0)mouseY=0;if(mouseX>=(int)screenW)mouseX=(int)screenW-1;if(mouseY>=(int)screenH)mouseY=(int)screenH-1;
   if((mouseButtons&1)&&dragWindow>=0){wins[dragWindow].x=mouseX-dragDX;wins[dragWindow].y=mouseY-dragDY;}else if(!(mouseButtons&1))dragWindow=-1;
   if((mouseButtons&1)&&!(oldButtons&1))handleClick(mouseX,mouseY);else if((mouseButtons&1)&&activeWindow==PAINT&&paintCount<512){Window a=wins[PAINT];if(mouseX>a.x+8&&mouseX<a.x+a.w-8&&mouseY>a.y+65&&mouseY<a.y+a.h-15){paintX[paintCount]=mouseX;paintY[paintCount++]=mouseY;}}
  }}else keyboard(v);
 }
}
extern "C" void kernel_main(u32 magic,u32 infoAddr){
 __asm__ volatile("cli");if(magic!=0x2BADB002||!infoAddr)for(;;)__asm__ volatile("hlt");
 MultibootInfo*mb=(MultibootInfo*)infoAddr;if(!(mb->flags&(1u<<12))||mb->framebuffer_type!=1||mb->framebuffer_bpp!=32)for(;;)__asm__ volatile("hlt");
 framebuffer=(u32*)(u32)mb->framebuffer_addr;fbPitch=mb->framebuffer_pitch;screenW=mb->framebuffer_width;screenH=mb->framebuffer_height;
 if(!framebuffer||screenW<640||screenH<480||screenW>1280||screenH>800)for(;;)__asm__ volatile("hlt");
 mouseX=(int)screenW/2;mouseY=(int)screenH/2;mouseInit();render();for(;;){pollInput();render();pauseTiny();}
}
""",
"README.md": r"""
# CandyOS Project

CandyOS is an experimental 32-bit x86 graphical-kernel starter. It boots through GRUB Multiboot, requests a 1024x768x32 framebuffer, draws a software-composited desktop, and polls PS/2 input.

## Build and run

Install NASM, GRUB utilities (grub-mkrescue and grub-file), xorriso, QEMU, and preferably an i686-elf cross-compiler. Then run these commands in this folder:

    make check
    make iso
    make run

A host GCC/G++ -m32 fallback is attempted, but a cross-toolchain is more reliable. On Windows, use a Linux environment such as WSL with the required packages installed.

## Current scope

The GUI has desktop icons, a start menu, movable windows, a local welcome page in the browser window, RAM-style demo file listings, a simple terminal (help, ls, clear, about, echo, reboot, shutdown), an in-memory text editor, paint surface, calculator, and a wallpaper setting.

This is a starter kernel, not a finished general-purpose OS. The browser is local-only; TCP/IP, DNS, real HTTP, full HTML/CSS, a real filesystem, user mode, virtual-memory paging, IRQ-driven input, and robust device discovery are not implemented yet. It targets legacy-BIOS x86/GRUB under emulators first. Hardware behavior can differ by machine.
"""
}

def choose_output() -> Path:
    desktop = Path.home() / "Desktop"
    return (desktop if desktop.exists() else Path.cwd()) / PROJECT_NAME

def main() -> int:
    project = choose_output()
    for relative, content in FILES.items():
        target = project / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content.lstrip("\n"), encoding="utf-8", newline="\n")
    print(f"Generated CandyOS project at: {project}")
    print(f"Next: cd \"{project}\" && make check && make run")
    print("Expected: GRUB boots a framebuffer desktop with clickable app windows.")
    print("If make check fails, install NASM, GRUB utilities, xorriso, QEMU, and an i686-elf cross-toolchain.")
    print("The browser uses an embedded page; network stack and advanced kernel subsystems remain future work.")
    if "--build" in sys.argv:
        if not shutil.which("make"):
            print("Cannot auto-build: make is not installed.")
            return 2
        return subprocess.run(["make", "iso"], cwd=project, check=False).returncode
    print("To build automatically, rerun with --build.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
