# patch_gc_credits

patch_gc_credits is a Python script that patches decompressed GameCube-edition Ocarina of Time ROMs (GC-EU, GC-EU-MQ, GC-US, GC-US-MQ) to fix a crash that occurs at the beginning of the credits when the ROM is run on real N64 hardware or an N64 emulator.

The script was written as part of a reverse engineering study of the credits routine in the GC editions of OoT, and the mechanism Nintendo used to trigger FMV playback from the GameCube disc.

## Background

On the GameCube, Ocarina of Time runs inside a built-in N64 emulator. The GC editions contain a routine in the credits sequence that, when a specific scene and scene-layer combination is reached, loads the address `0x81000000` into a register and jumps to it:

```mips
lw    $t2, 0x1360($s2)    ; load scene layer counter
li    $at, 6              ; credits scene layer value
lui   $t9, 0x8100         ; t9 = 0x81000000 (upper half)
bne   $t2, $at, +3        ; skip ahead if scene layer != 6
nop
jalr  $t9                 ; jump to 0x81000000
```

The GameCube emulator polls the program counter for the value `0x81000000`. When it detects this value, it intercepts execution and plays an FMV ending sequence from the disc rather than running any code at that address.

On real N64 hardware and N64 emulators, no such interception exists. `0x81000000` maps to physical address `0x01000000` (16 MB), which lies beyond the N64's 8 MB RAM ceiling. The CPU raises a bus error and the game crashes immediately.

The two `bne` instructions before the `jalr` already branch to the instruction immediately following it, which is the normal continuation of the credits routine. The patch replaces the `jalr` with a `nop`, causing execution to fall through and continue normally with the in-engine credits sequence instead of crashing.

## Patches

The ROM version is auto-detected by scanning for a build date string embedded in the ROM. The instruction window verified before patching is identical across all four versions.

| Version | ROM offset | Change |
|---------|------------|--------|
| GC-EU | `0x00B119E4` | Replace `jalr $t9` (call to `0x81000000`) with `nop` |
| GC-EU-MQ | `0x00B119C4` | Same |
| GC-US | `0x00B0F934` | Same |
| GC-US-MQ | `0x00B0F914` | Same |

## Usage

    python3 patch_gc_credits.py <decompressed.z64> <output.z64>

The input must be a decompressed ROM. GC-EU, GC-EU-MQ, GC-US, and GC-US-MQ are all supported and auto-detected.

Example:

    python3 patch_gc_credits.py input.z64 output.z64

## Requirements

Python 3. No external packages required.
