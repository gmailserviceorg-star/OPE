#!/usr/bin/env python3
"""Generate a bootable AetherOS graphical-kernel project without downloading files."""
from pathlib import Path
import shutil
import subprocess
import sys

PROJECT_NAME = "AetherOS"
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
KERNEL := build/aetheros.elf

.PHONY: all check iso run debug clean
all: iso

check:
	@command -v $(NASM) >/dev/null || { echo "Missing NASM. Install NASM and retry."; exit 1; }
	@command -v $(GRUB_MKRESCUE) >/dev/null || { echo "Missing grub-mkrescue. Install GRUB utilities and xorriso."; exit 1; }
	@command -v mformat >/dev/null || { echo "Missing mformat (mtools). Install mtools."; exit 1; }
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
	cp $(KERNEL) iso_root/boot/aetheros.elf
	cp grub.cfg iso_root/boot/grub/grub.cfg
	$(GRUB_MKRESCUE) -o build/AetherOS.iso iso_root
	@echo "Created build/AetherOS.iso"

run: iso
	qemu-system-i386 -m 128M -cdrom build/AetherOS.iso

debug: iso
	qemu-system-i386 -m 128M -cdrom build/AetherOS.iso -no-reboot -no-shutdown -d int,cpu_reset

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
menuentry "AetherOS" {
    multiboot /boot/aetheros.elf
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
char *strcpy(char *dst, const char *src) {
    char *out = dst;
    while ((*dst++ = *src++)) {}
    return out;
}
char *strncpy(char *dst, const char *src, size_t n) {
    char *out = dst;
    size_t i = 0;
    for (; i < n && src[i]; ++i) dst[i] = src[i];
    for (; i < n; ++i) dst[i] = 0;
    return out;
}
int strncmp(const char *a, const char *b, size_t n) {
    for (size_t i = 0; i < n; ++i) {
        unsigned char x = (unsigned char)a[i], y = (unsigned char)b[i];
        if (x != y) return (int)x - (int)y;
        if (!x) return 0;
    }
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
static int activeWindow=-1,dragWindow=-1,dragDX=0,dragDY=0,resizeWindow=-1,resizeDX=0,resizeDY=0,menuAnim=0;
static int paintColor=0x00E4A85B;
static int paintX[512],paintY[512],paintCount=0;
static char terminalInput[128],editorText[512],calcInput[64],browserAddress[96]="aether.local/welcome";
static int terminalLen=0,editorLen=0,calcLen=0,browserAddressLen=20,browserPage=0;
static bool browserInputFocus=false;
static bool keysDown[128];
static int playerX=8*256,playerY=8*256,playerYaw=0,playerHealth=100,dungeonTicks=0,dungeonScore=0;
static int ironX=12*256,ironY=3*256,ironHealth=60,ghostX=4*256,ghostY=1*256,ghostHealth=25;
static int attackCooldown=0,mouseTurn=0;
static bool attackFlash=false;
static char terminalOutput[4][72]={"AETHEROS TERMINAL","Type HELP for commands.","",""};
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
static void numberText(int x,int y,int value,u32 c,int scale=1){
 char digits[12];int n=0;
 if(value==0)digits[n++]='0';
 while(value>0&&n<10){digits[n++]=(char)('0'+value%10);value/=10;}
 for(int i=n-1;i>=0;--i)drawChar(x+(n-1-i)*4*scale,y,digits[i],c,scale);
}
enum App{BROWSER=0,FILES=1,TERMINAL=2,EDITOR=3,PAINT=4,CALCULATOR=5,SETTINGS=6,DUNGEONS=7};
struct Window{bool open;int x,y,w,h;};
static Window wins[8];
static const char*appNames[8]={"Browser","File Manager","Terminal","Text Editor","Paint","Calculator","Settings","Dungeons"};
static const int SIN16[16]={0,392,724,946,1024,946,724,392,0,-392,-724,-946,-1024,-946,-724,-392};
static const u32 DUNGEON_SKY=0x003E647D;
struct P2{int x,y,depth,valid;};
struct Cube3{int x,y,z,w,h,d,depth;u32 color;};
static Cube3 sceneCubes[768];
static int sceneCubeCount=0;
static int clipX=0,clipY=0,clipW=0,clipH=0;
static int cameraX=0,cameraY=0,cameraZ=0;

static int absval(int v){return v<0?-v:v;}
static int cosYaw(){return SIN16[(playerYaw+4)&15];}
static bool nearPlayer(int x,int y,int radius){return absval(x-playerX)<radius&&absval(y-playerY)<radius;}
static void openApp(int app){
 if(app<0||app>7)return;
 wins[app].open=true;
 wins[app].w=app==DUNGEONS?620:350;
 wins[app].h=app==DUNGEONS?420:240;
 if(wins[app].w>(int)screenW-20)wins[app].w=(int)screenW-20;
 if(wins[app].h>(int)screenH-60)wins[app].h=(int)screenH-60;
 wins[app].x=(int)screenW/2-wins[app].w/2+(app%3)*8;
 wins[app].y=(int)screenH/2-wins[app].h/2+(app%3)*8;
 if(wins[app].x<8)wins[app].x=8;
 if(wins[app].y<8)wins[app].y=8;
 if(wins[app].x+wins[app].w>(int)screenW-4)wins[app].x=(int)screenW-wins[app].w-4;
 if(wins[app].y+wins[app].h>(int)screenH-44)wins[app].y=(int)screenH-wins[app].h-44;
 activeWindow=app;menuOpen=false;
 if(app==DUNGEONS&&dungeonTicks==0){playerX=8*256;playerY=8*256;playerYaw=0;ironX=playerX+3*256;ironY=playerY-5*256;ironHealth=60;ghostX=playerX-4*256;ghostY=playerY-7*256;ghostHealth=25;}
}
static int windowAt(int x,int y){
 if(activeWindow>=0&&wins[activeWindow].open){Window a=wins[activeWindow];if(x>=a.x&&x<a.x+a.w&&y>=a.y&&y<a.y+a.h)return activeWindow;}
 for(int i=7;i>=0;--i)if(wins[i].open){Window a=wins[i];if(x>=a.x&&x<a.x+a.w&&y>=a.y&&y<a.y+a.h)return i;}
 return -1;
}
static u32 shade(u32 c,int factor){
 int r=(int)((c>>16)&255)*factor/100,g=(int)((c>>8)&255)*factor/100,b=(int)(c&255)*factor/100;
 return rgb(r>255?255:r,g>255?255:g,b>255?255:b);
}
static void addCube(int tx,int ty,int tz,u32 color,int w=256,int h=256,int d=256){
 if(sceneCubeCount>=768)return;
 Cube3 &c=sceneCubes[sceneCubeCount++];
 c.x=tx;c.y=ty;c.z=tz;c.w=w;c.h=h;c.d=d;c.color=color;c.depth=0;
}
static P2 project3(int x,int y,int z){
 int s=SIN16[playerYaw&15],co=cosYaw();
 int dx=x-cameraX,dy=y-cameraY,dz=z-cameraZ;
 int right=(dx*co+dy*s)/1024;
 int forward=(dx*s-dy*co)/1024;
 int depth=(forward*887-dz*462)/1024;
 int up=(dz*887+forward*462)/1024;
 P2 p;p.depth=depth;p.valid=depth>64;
 if(!p.valid){p.x=p.y=-10000;return p;}
 int focal=clipH*72/100;
 p.x=clipX+clipW/2+(right*focal)/depth;
 p.y=clipY+clipH*61/100-(up*focal)/depth;
 return p;
}
static long edge2(P2 a,P2 b,int x,int y){return (long)(x-a.x)*(b.y-a.y)-(long)(y-a.y)*(b.x-a.x);}
static void fillTri(P2 a,P2 b,P2 c,u32 color){
 if(!a.valid||!b.valid||!c.valid)return;
 int minx=a.x<b.x?a.x:b.x;if(c.x<minx)minx=c.x;
 int maxx=a.x>b.x?a.x:b.x;if(c.x>maxx)maxx=c.x;
 int miny=a.y<b.y?a.y:b.y;if(c.y<miny)miny=c.y;
 int maxy=a.y>b.y?a.y:b.y;if(c.y>maxy)maxy=c.y;
 if(minx<clipX)minx=clipX;if(miny<clipY)miny=clipY;
 if(maxx>=clipX+clipW)maxx=clipX+clipW-1;
 if(maxy>=clipY+clipH)maxy=clipY+clipH-1;
 long area=edge2(a,b,c.x,c.y);if(area==0)return;
 for(int py=miny;py<=maxy;++py)for(int px=minx;px<=maxx;++px){
  long e1=edge2(a,b,px,py),e2=edge2(b,c,px,py),e3=edge2(c,a,px,py);
  if((area>0&&e1>=0&&e2>=0&&e3>=0)||(area<0&&e1<=0&&e2<=0&&e3<=0))back[py*screenW+px]=color;
 }
}
static void quad3(P2 a,P2 b,P2 c,P2 d,u32 color){fillTri(a,b,c,color);fillTri(a,c,d,color);}
static void drawBox3(int x,int y,int z,int w,int h,int d,u32 color){
 P2 v[8];
 v[0]=project3(x,y,z);v[1]=project3(x+w,y,z);v[2]=project3(x+w,y+h,z);v[3]=project3(x,y+h,z);
 v[4]=project3(x,y,z+d);v[5]=project3(x+w,y,z+d);v[6]=project3(x+w,y+h,z+d);v[7]=project3(x,y+h,z+d);
 quad3(v[0],v[1],v[5],v[4],shade(color,72));
 quad3(v[1],v[2],v[6],v[5],shade(color,88));
 quad3(v[2],v[3],v[7],v[6],shade(color,65));
 quad3(v[3],v[0],v[4],v[7],shade(color,78));
 quad3(v[4],v[5],v[6],v[7],shade(color,125));
}
static int cubeDepth(int x,int y,int z){
 P2 p=project3(x+128,y+128,z+128);return p.depth;
}
static int tileHash(int x,int y){u32 h=(u32)x*374761393u+(u32)y*668265263u;h=(h^(h>>13))*1274126177u;return (int)(h^(h>>16));}
static void buildScene(){
 sceneCubeCount=0;int centerX=playerX/256,centerY=playerY/256;
 for(int ty=centerY-8;ty<=centerY+8;++ty)for(int tx=centerX-8;tx<=centerX+8;++tx){
  int h=tileHash(tx,ty);u32 floorColor=((h&7)==0)?0x00528C5F:((h&7)==1)?0x004A8056:0x00457850;
  if(((h>>3)&31)==3)floorColor=0x00618D62;
  addCube(tx*256,ty*256,-256,floorColor);
  if(((h>>5)&31)==4&&absval(tx-centerX)>2&&absval(ty-centerY)>2){
   addCube(tx*256+70,ty*256+70,0,0x007B5538,116,116,256);
   addCube(tx*256,ty*256,256,0x003F7650);
   addCube(tx*256,ty*256,512,0x00376B49);
   addCube(tx*256+256,ty*256,256,0x00447F52);
   addCube(tx*256-96,ty*256+160,256,0x003C7049);
  }
  if(((h>>10)&63)==9&&absval(tx-centerX)>3&&absval(ty-centerY)>3){
   addCube(tx*256,ty*256,0,0x0076818E);
   addCube(tx*256,ty*256,256,0x006C7785);
   if(h&1)addCube(tx*256,ty*256,512,0x00606D7C);
  }
 }
 for(int i=0;i<sceneCubeCount;++i)sceneCubes[i].depth=cubeDepth(sceneCubes[i].x,sceneCubes[i].y,sceneCubes[i].z);
 for(int i=1;i<sceneCubeCount;++i){
  Cube3 key=sceneCubes[i];int j=i-1;
  while(j>=0&&sceneCubes[j].depth<key.depth){sceneCubes[j+1]=sceneCubes[j];--j;}
  sceneCubes[j+1]=key;
 }
 for(int i=0;i<sceneCubeCount;++i){Cube3 c=sceneCubes[i];if(c.depth>64)drawBox3(c.x,c.y,c.z,c.w,c.h,c.d,c.color);}
}
static void drawHero(int x,int y){
 drawBox3(x-86,y-48,0,72,96,170,0x003B5B79);
 drawBox3(x+14,y-48,0,72,96,170,0x003B5B79);
 drawBox3(x-95,y-50,160,200,100,185,0x002C526F);
 drawBox3(x-68,y-43,345,146,86,142,0x00D4AD70);
 drawBox3(x-70,y-45,470,150,90,110,0x00513B2C);
 drawBox3(x+92,y-20,205,56,45,245,0x00B9C7CF);
 drawBox3(x+137,y-14,420,25,24,100,0x00E5D7A1);
}
static void drawIronGuard(int x,int y){
 drawBox3(x-90,y-72,0,72,72,190,0x00515F6E);
 drawBox3(x+18,y-72,0,72,72,190,0x00515F6E);
 drawBox3(x-106,y-78,180,220,156,240,0x008894A1);
 drawBox3(x-84,y-63,285,177,126,80,0x00B7A16B);
 drawBox3(x-75,y-68,414,160,136,150,0x006A7481);
 drawBox3(x-142,y-76,205,50,52,200,0x006C7887);
 drawBox3(x+92,y-76,205,50,52,200,0x006C7887);
 drawBox3(x+125,y-25,200,34,28,280,0x00C8D0D4);
}
static void drawGhostyFly(int x,int y,int z){
 drawBox3(x-62,y-62,z,124,124,122,0x0091D8D7);
 drawBox3(x-93,y-10,z+36,38,30,55,0x00B6EEEA);
 drawBox3(x+55,y-10,z+36,38,30,55,0x00B6EEEA);
 drawBox3(x-42,y-70,z+80,30,24,28,0x00243D51);
 drawBox3(x+16,y-70,z+80,30,24,28,0x00243D51);
 drawBox3(x-31,y-75,z+83,12,8,10,0x00FFFFFF);
 drawBox3(x+27,y-75,z+83,12,8,10,0x00FFFFFF);
}
static void attackDungeons(){
 if(attackCooldown>0)return;attackCooldown=14;attackFlash=true;
 if(nearPlayer(ironX,ironY,3*256)){ironHealth-=14;if(ironHealth<=0){ironHealth=60;ironX=playerX+((dungeonTicks%2)?5:-5)*256;ironY=playerY-5*256;dungeonScore+=100;}}
 else if(nearPlayer(ghostX,ghostY,4*256)){ghostHealth-=10;if(ghostHealth<=0){ghostHealth=25;ghostX=playerX+((dungeonTicks%2)?-6:6)*256;ghostY=playerY-7*256;dungeonScore+=50;}}
}
static void updateDungeons(){
 if(activeWindow!=DUNGEONS)return;
 ++dungeonTicks;if(attackCooldown>0)--attackCooldown;if(attackCooldown==0)attackFlash=false;
 int s=SIN16[playerYaw&15],co=cosYaw(),step=6;
 if(keysDown[0x11]){playerX+=s*step/1024;playerY-=co*step/1024;}
 if(keysDown[0x1F]){playerX-=s*step/1024;playerY+=co*step/1024;}
 if(keysDown[0x1E]){playerX-=co*step/1024;playerY-=s*step/1024;}
 if(keysDown[0x20]){playerX+=co*step/1024;playerY+=s*step/1024;}
 if(playerX < -120*256)playerX=-120*256;if(playerX>120*256)playerX=120*256;
 if(playerY < -120*256)playerY=-120*256;if(playerY>120*256)playerY=120*256;
 if(dungeonTicks%20==0){
  if(absval(ironX-playerX)>180)ironX+=(ironX<playerX?18:-18);
  if(absval(ironY-playerY)>180)ironY+=(ironY<playerY?18:-18);
  if(absval(ghostX-playerX)>150)ghostX+=(ghostX<playerX?24:-24);
  if(absval(ghostY-playerY)>150)ghostY+=(ghostY<playerY?24:-24);
  if(nearPlayer(ironX,ironY,2*256)||nearPlayer(ghostX,ghostY,2*256)){playerHealth-=2;if(playerHealth<0)playerHealth=0;}
 }
 if(playerHealth==0&&keysDown[0x13]){playerHealth=100;playerX=8*256;playerY=8*256;ironHealth=60;ghostHealth=25;}
}
static void drawDungeons(int x,int y,int w,int h){
 rect(x,y,w,h,0x0015222B);text(x+8,y+7,"DUNGEONS: THE FORGOTTEN REALM",0x00EED6A2,2);
 clipX=x+3;clipY=y+25;clipW=w-6;clipH=h-54;
 rect(clipX,clipY,clipW,clipH,DUNGEON_SKY);
 rect(clipX,clipY+clipH*61/100,clipW,clipH*39/100,0x00385442);
 for(int yy=clipY;yy<clipY+clipH*61/100;++yy){int tint=(yy-clipY)*12/(clipH?clipH:1);rect(clipX,yy,clipW,1,rgb(55+tint,92+tint,116+tint));}
 int s=SIN16[playerYaw&15],co=cosYaw();
 cameraX=playerX-s*5*256/1024;cameraY=playerY+co*5*256/1024;cameraZ=4*256;
 buildScene();drawIronGuard(ironX,ironY);drawGhostyFly(ghostX,ghostY,480+(dungeonTicks%40<20?20:0));drawHero(playerX,playerY);
 rect(x+8,y+29,190,19,0xB0182631);text(x+14,y+35,"HEALTH",0x00FFFFFF,1);
 rect(x+63,y+34,92,9,0x003B2525);rect(x+63,y+34,92*playerHealth/100,9,0x00D94E58);
 text(x+163,y+35,playerHealth>0?"ALIVE":"FALLEN",0x00FFE0B0,1);
 rect(x+w-187,y+29,178,48,0xB0182631);
 text(x+w-180,y+35,"IRON GUARD",0x00D4DCE3,1);rect(x+w-104,y+35,87,7,0x003B2525);rect(x+w-104,y+35,87*ironHealth/60,7,0x00D0A766);
 text(x+w-180,y+49,"GHOSTY FLY",0x00A6E8E8,1);rect(x+w-104,y+49,87,7,0x003B2525);rect(x+w-104,y+49,87*ghostHealth/25,7,0x0078D8D6);
 if(attackFlash){rect(x+w/2-48,y+h-76,96,18,0x00CDA96A);text(x+w/2-26,y+h-71,"STRIKE!",0x00222222,1);}
 if(playerHealth==0){rect(x+w/2-82,y+h/2-14,164,32,0x00A02F39);text(x+w/2-64,y+h/2-4,"YOU HAVE FALLEN",0x00FFFFFF,1);text(x+w/2-58,y+h/2+29,"PRESS R TO RETURN",0x00FFFFFF,1);}
 rect(x+5,y+h-24,w-10,20,0xD015202B);text(x+12,y+h-18,"WASD MOVE  |  MOUSE LOOK  |  SPACE/CLICK ATTACK",0x00E6E9E7,1);
 text(x+w-110,y+h-18,"RELICS",0x00EED6A2,1);numberText(x+w-56,y+h-18,dungeonScore,0x00EED6A2,1);
 clipX=0;clipY=0;clipW=(int)screenW;clipH=(int)screenH;
}
static void background(){
 for(u32 y=0;y<screenH;++y){
  int r=alternateWallpaper?26:21,g=alternateWallpaper?57:46,b=alternateWallpaper?67:71;
  u32 c=rgb(r+(int)(y*15/screenH),g+(int)(y*43/screenH),b+(int)(y*69/screenH));
  for(u32 x=0;x<screenW;++x)back[y*screenW+x]=c;
 }
 for(int i=0;i<7;++i){int x=(int)(screenW*56/100)+i*23,y=42+i*31;rect(x,y,220-i*16,2,0x00364D61);}
 rect(0,0,(int)screenW,64,0x20101822);
 text(26,17,"AETHEROS",0x00FFFFFF,3);text(28,43,"THE ADVENTURE DESKTOP",0x00C4D8E8,1);
 rect(24,62,1,(int)screenH-112,0x504F7085);
}
static void drawIcon(int x,int y,int app){
 u32 c=app==BROWSER?0x004BB6C9:app==FILES?0x00D8B65C:app==TERMINAL?0x00222A36:app==EDITOR?0x007F9DD0:app==PAINT?0x00D87D6C:app==CALCULATOR?0x0071B88B:app==DUNGEONS?0x00B38A50:0x009C8BD5;
 rect(x,y,42,36,0x00132230);rect(x+3,y+3,36,30,c);frame(x+3,y+3,36,30,0x00FFFFFF);
 if(app==BROWSER){rect(x+12,y+10,18,16,0x00FFFFFF);rect(x+14,y+12,14,12,c);rect(x+12,y+17,18,2,0x00FFFFFF);}
 else if(app==FILES){rect(x+9,y+11,25,17,0x00F2D27D);rect(x+9,y+8,12,5,0x00F2D27D);}
 else if(app==TERMINAL)text(x+9,y+11,">_",0x00FFFFFF,2);
 else if(app==EDITOR){rect(x+12,y+8,18,21,0x00FFFFFF);rect(x+16,y+13,11,2,c);rect(x+16,y+18,11,2,c);}
 else if(app==PAINT){rect(x+10,y+8,18,18,0x00F6C7A0);pixel(x+17,y+14,0x00CC3655);pixel(x+22,y+19,0x003C65D5);}
 else if(app==CALCULATOR){rect(x+11,y+7,20,23,0x00FFFFFF);rect(x+14,y+10,14,4,0x00B8C7D4);for(int k=0;k<3;++k)for(int j=0;j<2;++j)rect(x+14+j*7,y+17+k*4,4,2,c);}
 else if(app==DUNGEONS){rect(x+19,y+7,4,20,0x00E6D8B8);rect(x+11,y+9,20,5,0x00E6D8B8);rect(x+15,y+19,13,4,0x00572E2A);rect(x+24,y+21,8,4,0x00572E2A);}
 else{rect(x+12,y+8,18,18,0x00FFFFFF);for(int k=0;k<8;k+=2)rect(x+18,y+8+k,6,1,c);}
}
static void drawTaskbar(){
 rect(0,(int)screenH-42,(int)screenW,42,0xE0101822);rect(0,(int)screenH-42,(int)screenW,1,0x006F8293);
 rect(9,(int)screenH-35,74,28,C_ACCENT);text(19,(int)screenH-27,"AETHER",0x00FFFFFF,1);
 int x=92;for(int i=0;i<8;++i)if(wins[i].open&&x<(int)screenW-88){int ww=appNames[i][0]=='D'?84:78;rect(x,(int)screenH-34,ww,25,i==activeWindow?0x003D5265:0x00232F3D);text(x+5,(int)screenH-25,appNames[i],0x00FFFFFF,1);x+=ww+3;}
 text((int)screenW-78,(int)screenH-27,"AETHEROS",0x00D4E1EB,1);
}
static void drawWindow(int app){
 Window a=wins[app];if(!a.open)return;
 rect(a.x+5,a.y+7,a.w,a.h,0x00304050);rect(a.x,a.y,a.w,a.h,0x00E5EAF0);
 rect(a.x,a.y,a.w,30,app==activeWindow?C_ACCENT:0x005C6B7B);text(a.x+10,a.y+10,appNames[app],0x00FFFFFF,2);
 rect(a.x+a.w-25,a.y+5,18,19,0x00C95C57);text(a.x+a.w-20,a.y+11,"X",0x00FFFFFF,1);
 rect(a.x+1,a.y+31,a.w-2,a.h-32,0x00F4F6F8);int x=a.x+12,y=a.y+44;
 if(app==DUNGEONS){drawDungeons(a.x+8,a.y+36,a.w-16,a.h-44);}
 else if(app==BROWSER){
  rect(x,y,27,24,0x00DDE5EB);frame(x,y,27,24,0x00C3CED8);text(x+10,y+8,"<",0x003C596C,1);
  rect(x+30,y,27,24,0x00DDE5EB);frame(x+30,y,27,24,0x00C3CED8);text(x+40,y+8,">",0x003C596C,1);
  rect(x+60,y,27,24,0x00DDE5EB);frame(x+60,y,27,24,0x00C3CED8);text(x+69,y+8,"R",0x003C596C,1);
  rect(x+92,y,a.w-120,24,0x00FFFFFF);frame(x+92,y,a.w-120,24,browserInputFocus?C_ACCENT:0x00C7D0D8);
  char shown[49];int n=browserAddressLen<45?browserAddressLen:45;for(int i=0;i<n;++i)shown[i]=browserAddress[i];shown[n]=0;text(x+98,y+8,shown,0x004B657A,1);
  if(browserInputFocus)text(x+98+n*4,y+8,"_",C_ACCENT,1);
  if(browserPage==0){text(x,y+39,"WELCOME TO AETHEROS",0x002A537A,2);multiline(x,y+62,"A quiet landing page built into the operating system.\\nExplore the local guide, launch Dungeons, or use the\\naddress bar to inspect the bundled pages.",0x00334657,a.w-30,1);}
  else if(browserPage==1){text(x,y+39,"AETHEROS FIELD GUIDE",0x002A537A,2);multiline(x,y+62,"The desktop is rendered by the kernel into a framebuffer.\\nOpen Dungeons from Start or the desktop icon. WASD moves,\\nthe mouse turns the camera, and Space or click attacks.\\nThis browser currently displays local pages only.",0x00334657,a.w-30,1);}
  else if(browserPage==2){text(x,y+39,"DUNGEONS - GAME GUIDE",0x002A537A,2);multiline(x,y+62,"The Forgotten Realm is a third-person block adventure.\\nIron Guard is a heavily armored melee enemy. Ghosty Fly\\nis a hovering spirit that drifts toward the player. Defeat\\nenemies to gain relic score and explore the voxel ruins.",0x00334657,a.w-30,1);}
  else{text(x,y+39,"NO NETWORK CONNECTION",0x00A43C42,2);multiline(x,y+62,"This build has no TCP/IP, DNS, TLS, or HTTP stack yet.\\nLocal pages are available, but public websites cannot be\\nfetched from this kernel build.",0x00334657,a.w-30,1);}
  rect(x,y+a.h-94,a.w-28,1,0x00D6DDE3);text(x,y+a.h-81,"LOCAL BROWSER",0x00717E8A,1);
 }
 else if(app==FILES){text(x,y,"AETHER DRIVE",0x002A537A,2);text(x+5,y+32,"[DIR]  /",0x004B657A,1);text(x+15,y+52,"WELCOME.TXT",0x00334657,1);text(x+15,y+70,"FIELD_GUIDE.TXT",0x00334657,1);text(x+15,y+88,"DUNGEONS.SAV",0x00334657,1);text(x,y+124,"RAM demo entries; persistence is not installed.",0x0061707C,1);}
 else if(app==TERMINAL){rect(x-4,y-5,a.w-16,a.h-49,0x00121A22);for(int i=0;i<4;++i)text(x,y+i*17,terminalOutput[i],0x007DE0A3,1);text(x,y+78,"AETHER:/ >",0x007DE0A3,1);text(x+68,y+78,terminalInput,0x00FFFFFF,1);}
 else if(app==EDITOR){text(x,y,"UNTITLED.TXT | RAM",0x003E5E77,1);rect(x-3,y+19,a.w-20,a.h-74,0x00FFFFFF);frame(x-3,y+19,a.w-20,a.h-74,0x00D3DCE4);multiline(x,y+27,editorText,0x002E4050,a.w-38,1);text(x,y+a.h-31,"TYPE TO EDIT - ENTER NEW LINE",0x0061707C,1);}
 else if(app==PAINT){text(x,y,"PALETTE",0x003E5E77,1);for(int i=0;i<4;++i)rect(x+58+i*24,y-2,18,15,i==0?0x00E4A85B:i==1?0x00D75E67:i==2?0x004E96D8:0x00369B79);rect(x-4,y+21,a.w-20,a.h-75,0x00FFFFFF);frame(x-4,y+21,a.w-20,a.h-75,0x00CAD4DE);for(int i=0;i<paintCount;++i)for(int q=0;q<4;++q)pixel(paintX[i]+q%2,paintY[i]+q/2,paintColor);text(x,y+a.h-31,"DRAG THE MOUSE TO DRAW",0x0061707C,1);}
 else if(app==CALCULATOR){rect(x,y,a.w-24,27,0x00FFFFFF);frame(x,y,a.w-24,27,0x00C7D0D8);text(x+6,y+8,calcLen?calcInput:"0",0x00334657,2);const char*keys="789/456*123-0.=+";for(int i=0;i<16;++i){int bx=x+(i%4)*46,by=y+38+(i/4)*29;rect(bx,by,40,24,(keys[i]=='/'||keys[i]=='*'||keys[i]=='-'||keys[i]=='+')?0x00DCE8F2:0x00FFFFFF);frame(bx,by,40,24,0x00C7D0D8);char label[2]={keys[i],0};text(bx+14,by+8,label,0x00334657,1);}}
 else{text(x,y,"AETHEROS SETTINGS",0x003E5E77,1);text(x,y+28,"VIDEO: GRUB LINEAR FRAMEBUFFER",0x00334657,1);text(x,y+49,"INPUT: PS/2 KEYBOARD + MOUSE",0x00334657,1);text(x,y+70,animations?"ANIMATIONS: ON":"ANIMATIONS: OFF",0x00334657,1);rect(x,y+96,150,27,C_ACCENT);text(x+10,y+105,"CHANGE WALLPAPER",0x00FFFFFF,1);text(x,y+139,"CLICK TO TOGGLE THE DESKTOP THEME",0x0061707C,1);}
 rect(a.x+a.w-9,a.y+a.h-8,2,6,0x007B8D9F);rect(a.x+a.w-7,a.y+a.h-6,5,2,0x007B8D9F);
}
static void drawStartMenu(){
 if(!menuOpen){menuAnim=0;return;}
 if(animations&&menuAnim<6)++menuAnim;
 int x=10,y=(int)screenH-42-294+(animations?(6-menuAnim)*6:0);
 rect(x+4,y+5,232,294,0x00304050);rect(x,y,232,294,0x00F0F3F6);frame(x,y,232,294,0x00AAB7C2);
 rect(x,y,232,37,0x002D4E6A);text(x+12,y+13,"AETHEROS APPS",0x00FFFFFF,2);
 for(int i=0;i<8;++i){drawIcon(x+10,y+43+i*30,i);text(x+63,y+56+i*30,appNames[i],0x002A3F51,1);}
}
static void drawCursor(){for(int i=0;i<14;++i)for(int j=0;j<=i/2;++j)pixel(mouseX+j,mouseY+i,0x00FFFFFF);for(int i=1;i<12;++i)pixel(mouseX+i/2,mouseY+i,0x00101822);}
static void render(){
 background();for(int i=0;i<8;++i){int x=25,y=74+i*76;drawIcon(x,y,i);text(x-2,y+42,appNames[i],0x00FFFFFF,1);}
 for(int i=0;i<8;++i)if(i!=activeWindow)drawWindow(i);
 if(activeWindow>=0)drawWindow(activeWindow);
 drawTaskbar();drawStartMenu();drawCursor();present();
}
static void terminalCommand(){
 for(int i=0;i<4;++i)terminalOutput[i][0]=0;
 if(!terminalLen)return;terminalInput[terminalLen]=0;
 if(!__builtin_strcmp(terminalInput,"help"))__builtin_strcpy(terminalOutput[0],"HELP LS CLEAR ABOUT ECHO DUNGEONS REBOOT");
 else if(!__builtin_strcmp(terminalInput,"ls"))__builtin_strcpy(terminalOutput[0],"/ WELCOME.TXT FIELD_GUIDE.TXT DUNGEONS.SAV");
 else if(!__builtin_strcmp(terminalInput,"about"))__builtin_strcpy(terminalOutput[0],"AETHEROS X86 GRAPHICAL KERNEL");
 else if(!__builtin_strncmp(terminalInput,"echo ",5)){__builtin_strncpy(terminalOutput[0],terminalInput+5,70);terminalOutput[0][70]=0;}
 else if(!__builtin_strcmp(terminalInput,"dungeons"))openApp(DUNGEONS);
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
static bool hasText(const char *s,const char *needle){
 if(!*needle)return true;
 for(int i=0;s[i];++i){int j=0;while(needle[j]&&s[i+j]==needle[j])++j;if(!needle[j])return true;}
 return false;
}
static void browserNavigate(){
 browserInputFocus=false;browserPage=3;
 if(hasText(browserAddress,"guide")||hasText(browserAddress,"help"))browserPage=1;
 else if(hasText(browserAddress,"dungeons"))browserPage=2;
 else if(hasText(browserAddress,"aether.local")||hasText(browserAddress,"home"))browserPage=0;
}
static void browserInput(char c){
 if(c=='\n'){browserNavigate();return;}
 if(c=='\b'){if(browserAddressLen){browserAddress[--browserAddressLen]=0;}return;}
 if(c>=32&&browserAddressLen<94){browserAddress[browserAddressLen++]=c;browserAddress[browserAddressLen]=0;}
}
static void calcKey(char c){
 if(c=='\b'){if(calcLen)calcInput[--calcLen]=0;return;}
 if(c=='='){int i=0;long a=0,b=0;while(calcInput[i]>='0'&&calcInput[i]<='9'){a=a*10+calcInput[i]-'0';++i;}char op=calcInput[i++];while(calcInput[i]>='0'&&calcInput[i]<='9'){b=b*10+calcInput[i]-'0';++i;}long r=0;if(op=='+')r=a+b;else if(op=='-')r=a-b;else if(op=='*')r=a*b;else if(op=='/'&&b)r=a/b;calcLen=0;if(r<0){calcInput[calcLen++]='-';r=-r;}char rev[24];int n=0;do{rev[n++]=(char)('0'+r%10);r/=10;}while(r&&n<22);while(n)calcInput[calcLen++]=rev[--n];calcInput[calcLen]=0;return;}
 if((c>='0'&&c<='9')||c=='+'||c=='-'||c=='*'||c=='/')if(calcLen<60){calcInput[calcLen++]=c;calcInput[calcLen]=0;}
}
static void keyboard(u8 sc){
 u8 code=sc&0x7F;
 if(sc&0x80){keysDown[code]=false;return;}
 keysDown[code]=true;
 if(code==0x01){if(activeWindow>=0)wins[activeWindow].open=false;activeWindow=-1;browserInputFocus=false;return;}
 char c=keyChar(sc);if(!c)return;
 if(activeWindow==DUNGEONS){
  if(c==' ')attackDungeons();
  if(c=='r'&&playerHealth==0){playerHealth=100;playerX=8*256;playerY=8*256;ironHealth=60;ghostHealth=25;}
  return;
 }
 if(activeWindow==BROWSER&&browserInputFocus){browserInput(c);return;}
 if(activeWindow<0)return;
 if(activeWindow==TERMINAL){if(c=='\n')terminalCommand();else if(c=='\b'){if(terminalLen)terminalInput[--terminalLen]=0;}else if(c>=32&&terminalLen<120){terminalInput[terminalLen++]=c;terminalInput[terminalLen]=0;}}
 else if(activeWindow==EDITOR){if(c=='\b'){if(editorLen)editorText[--editorLen]=0;}else if((c=='\n'||c>=32)&&editorLen<500){editorText[editorLen++]=c;editorText[editorLen]=0;}}
 else if(activeWindow==CALCULATOR)calcKey(c);
}
static void waitInputClear(){for(int i=0;i<100000&&(inb(0x64)&2);++i){}}
static bool waitOutputFull(){for(int i=0;i<100000;++i)if(inb(0x64)&1)return true;return false;}
static void mouseWrite(u8 value){
 waitInputClear();outb(0x64,0xD4);waitInputClear();outb(0x60,value);
 if(waitOutputFull())(void)inb(0x60);
}
static void mouseInit(){
 waitInputClear();outb(0x64,0xA8);
 waitInputClear();outb(0x64,0x20);
 u8 config=0;if(waitOutputFull())config=inb(0x60);
 config=(u8)((config|2)&~0x20);
 waitInputClear();outb(0x64,0x60);waitInputClear();outb(0x60,config);
 mouseWrite(0xF6);mouseWrite(0xF4);
 // Enable the auxiliary port and read it through the polling loop; no IRQ dependency.
 for(int i=0;i<10000&&(inb(0x64)&1);++i)(void)inb(0x60);
}
static void handleClick(int x,int y){
 if(y>(int)screenH-42){
  if(x<88){menuOpen=!menuOpen;return;}
  int taskX=92;
  for(int i=0;i<8;++i)if(wins[i].open){int taskW=appNames[i][0]=='D'?84:78;if(x>=taskX&&x<taskX+taskW){activeWindow=i;menuOpen=false;return;}taskX+=taskW+3;}
  return;
 }
 if(menuOpen){
  int top=(int)screenH-42-294;
  if(x>=10&&x<242&&y>=top+39&&y<top+290){int app=(y-(top+40))/30;if(app>=0&&app<8)openApp(app);menuOpen=false;return;}
  menuOpen=false;
 }
 int hit=windowAt(x,y);
 if(hit>=0){
  activeWindow=hit;Window&a=wins[hit];
  if(y<a.y+30){browserInputFocus=false;if(x>a.x+a.w-28){a.open=false;activeWindow=-1;resizeWindow=-1;return;}dragWindow=hit;dragDX=x-a.x;dragDY=y-a.y;return;}
  if(x>=a.x+a.w-12&&y>=a.y+a.h-12){resizeWindow=hit;resizeDX=mouseX-(a.x+a.w);resizeDY=mouseY-(a.y+a.h);return;}
  if(hit==BROWSER){
   int bx=a.x+12,by=a.y+44;
   if(y>=by&&y<by+24){
    if(x>=bx&&x<bx+29){browserPage=0;__builtin_strcpy(browserAddress,"aether.local/welcome");browserAddressLen=20;browserInputFocus=false;}
    else if(x>=bx+30&&x<bx+59){browserPage=1;__builtin_strcpy(browserAddress,"aether.local/guide");browserAddressLen=18;browserInputFocus=false;}
    else if(x>=bx+60&&x<bx+89){browserNavigate();}
    else{browserInputFocus=true;}
   }else browserInputFocus=false;
  }
  if(hit==DUNGEONS){int gy=a.y+61;if(y>=gy&&y<a.y+a.h-42){attackDungeons();}return;}
  if(hit==PAINT){if(y<a.y+69){if(x<a.x+75)paintColor=0x00E4A85B;else if(x<a.x+99)paintColor=0x00D75E67;else if(x<a.x+123)paintColor=0x004E96D8;else paintColor=0x00369B79;}else if(paintCount<512){paintX[paintCount]=x;paintY[paintCount++]=y;}}
  else if(hit==SETTINGS){if(y>=a.y+130&&y<a.y+165)alternateWallpaper=!alternateWallpaper;else animations=!animations;}
  else if(hit==CALCULATOR){int kx=a.x+12,ky=a.y+44+38;int col=(x-kx)/46,row=(y-ky)/29;const char*keys="789/456*123-0.=+";if(col>=0&&col<4&&row>=0&&row<4)calcKey(keys[row*4+col]);}
  return;
 }
 browserInputFocus=false;
 if(y<(int)screenH-55&&x<112){int app=(y-74)/76;if(app>=0&&app<8)openApp(app);}
}
static void pollInput(){
 for(int n=0;n<32;++n){
  u8 st=inb(0x64);if(!(st&1))break;u8 v=inb(0x60);
  if(st&0x20){
   static int phase=0;static u8 packet[3];
   if(phase==0&&!(v&0x08))continue;
   packet[phase++]=v;
   if(phase==3){
    phase=0;oldButtons=mouseButtons;mouseButtons=packet[0]&7;
    int dx=(signed char)packet[1],dy=(signed char)packet[2];
    mouseX+=dx;mouseY-=dy;
    if(mouseX<0)mouseX=0;if(mouseY<0)mouseY=0;
    if(mouseX>=(int)screenW)mouseX=(int)screenW-1;if(mouseY>=(int)screenH)mouseY=(int)screenH-1;
    if(activeWindow==DUNGEONS&&mouseX>wins[DUNGEONS].x+8&&mouseX<wins[DUNGEONS].x+wins[DUNGEONS].w-8&&mouseY>wins[DUNGEONS].y+60&&mouseY<wins[DUNGEONS].y+wins[DUNGEONS].h-38){
     mouseTurn+=dx;
     if(mouseTurn>=5){playerYaw=(playerYaw+1)&15;mouseTurn=0;}
     else if(mouseTurn<=-5){playerYaw=(playerYaw+15)&15;mouseTurn=0;}
    }
    if(mouseButtons&1){
    if(resizeWindow>=0){
     Window &rw=wins[resizeWindow];int minW=resizeWindow==DUNGEONS?480:250,minH=resizeWindow==DUNGEONS?330:150;
     int nw=mouseX-rw.x-resizeDX,nh=mouseY-rw.y-resizeDY;
     if(nw<minW)nw=minW;if(nh<minH)nh=minH;
     if(nw>(int)screenW-rw.x)nw=(int)screenW-rw.x;
     if(nh>(int)screenH-42-rw.y)nh=(int)screenH-42-rw.y;
     rw.w=nw;rw.h=nh;
    }else if(dragWindow>=0){wins[dragWindow].x=mouseX-dragDX;wins[dragWindow].y=mouseY-dragDY;}
   }else{dragWindow=-1;resizeWindow=-1;}
    if((mouseButtons&1)&&!(oldButtons&1))handleClick(mouseX,mouseY);
    else if((mouseButtons&1)&&activeWindow==PAINT&&paintCount<512){Window a=wins[PAINT];if(mouseX>a.x+8&&mouseX<a.x+a.w-8&&mouseY>a.y+65&&mouseY<a.y+a.h-15){paintX[paintCount]=mouseX;paintY[paintCount++]=mouseY;}}
   }
  }else keyboard(v);
 }
}
extern "C" void kernel_main(u32 magic,u32 infoAddr){
 __asm__ volatile("cli");if(magic!=0x2BADB002||!infoAddr)for(;;)__asm__ volatile("hlt");
 MultibootInfo*mb=(MultibootInfo*)infoAddr;
 if(!(mb->flags&(1u<<12))||mb->framebuffer_type!=1||mb->framebuffer_bpp!=32)for(;;)__asm__ volatile("hlt");
 framebuffer=(u32*)(u32)mb->framebuffer_addr;fbPitch=mb->framebuffer_pitch;screenW=mb->framebuffer_width;screenH=mb->framebuffer_height;
 if(!framebuffer||screenW<640||screenH<480||screenW>1280||screenH>800)for(;;)__asm__ volatile("hlt");
 mouseX=(int)screenW/2;mouseY=(int)screenH/2;mouseInit();render();
 for(;;){pollInput();updateDungeons();render();pauseTiny();}
}
""",
"DUNGEONS.md": r"""
# Dungeons: The Forgotten Realm

Dungeons is a built-in, third-person voxel RPG prototype inside AetherOS. The kernel software-renders a block landscape, a back-facing player avatar, ruins, trees, and two moving enemies.

## Controls
- **W / A / S / D** — move relative to the camera
- **Mouse movement** — turn the camera while the pointer is inside the game viewport
- **Space or click in the scene** — attack enemies
- **R** — return after being defeated

## Creatures
- **Iron Guard** — armored melee sentinel with a large health bar; defeating it awards 100 relic points.
- **Ghosty Fly** — hovering spirit with pale wings and bright eyes; defeating it awards 50 relic points.

The world is procedurally assembled from block coordinates. This is an early kernel-level gameplay prototype: movement, pursuit, health, attacks, and score work locally, while saved worlds, sound, procedural quests, inventory, multiplayer, and a richer physics system are not implemented yet.
""",
"docs/ARCHITECTURE.md": r"""
# AetherOS Architecture

AetherOS currently starts through GRUB Multiboot 1 in 32-bit protected mode. GRUB is asked for a linear 32-bit framebuffer. The kernel owns a back buffer and copies each rendered frame into the framebuffer.

- `src/boot/boot.asm` sets a stack and calls `kernel_main`.
- `src/kernel/kernel.cpp` contains the desktop compositor, polled PS/2 keyboard and mouse input, simple window manager, local browser pages, and the Dungeons software renderer.
- `src/lib/memory.c` supplies the freestanding memory/string routines used by the kernel.
- `Makefile`, `linker.ld`, and `grub.cfg` build the kernel ELF and bootable ISO.

## Current limitations

The browser is a local-page viewer, not a public-web browser. There is no TCP/IP, DNS, TLS/HTTPS, real HTTP client, persistent filesystem, user mode, paging, or IRQ-based input yet. The prototype targets QEMU and compatible legacy-BIOS systems. A full 3D GPU pipeline is not present; Dungeons uses software-projected voxel-style boxes drawn by the kernel.
""",
"README.md": r"""
# AetherOS

AetherOS is an experimental 32-bit x86 desktop kernel with a software-rendered GUI, movable application windows, a polled PS/2 mouse and keyboard, a local-only browser, and the built-in **Dungeons: The Forgotten Realm** third-person voxel RPG prototype.

## Build and run

Install NASM, GRUB utilities (`grub-mkrescue` and `grub-file`), xorriso, mtools, QEMU, and preferably an `i686-elf` cross-compiler. From this generated folder:

    make check
    make iso
    make run

The ISO is created at `build/AetherOS.iso`. On Windows, use a Linux environment such as WSL with the packages installed.

## Desktop and applications

The desktop includes a start menu, draggable windows, wallpaper settings, file-list demo, terminal, text editor, paint surface, calculator, browser, and Dungeons. The terminal supports `help`, `ls`, `clear`, `about`, `echo`, `dungeons`, `reboot`, and `shutdown`.

## Dungeons controls

- **W / A / S / D** move relative to the camera.
- **Mouse movement** turns the camera when the cursor is over the game.
- **Space or click in the scene** attacks.
- **R** returns after defeat.

Enemies include the **Iron Guard** and **Ghosty Fly**. The game features a software-rendered voxel landscape, a third-person avatar, enemy pursuit, health bars, and relic points.

## Scope and honesty

This is a bootable starter kernel, not a production operating system. The browser shows embedded local pages only; it cannot yet access public websites. TCP/IP, DNS, TLS/HTTPS, real HTTP, a complete HTML engine, persistent filesystem, user mode, virtual-memory paging, IRQ-based input, audio, save files, and advanced game physics are future work. The game is a kernel-level prototype and currently has no Minecraft assets or code.
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
    print(f"Generated AetherOS project at: {project}")
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
