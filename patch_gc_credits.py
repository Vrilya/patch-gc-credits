"""
Patch GC OoT ROMs to fix the ending credits crash on N64.

Supported ROMs (auto-detected by build_data_signature):
  gc-eu, gc-eu-mq, gc-us, gc-us-mq

Background:
  During the credits sequence, a specific scene and scene-layer combination
  triggers a routine that loads the address 0x81000000 into a register and
  jumps to it.  The relevant MIPS instructions at the patch site are:

    lw    $t2, 0x1360($s2)    ; load scene layer counter
    li    $at, 6              ; credits scene layer value
    lui   $t9, 0x8100         ; t9 = 0x81000000 (upper half)
    bne   $t2, $at, +3        ; skip ahead if scene layer != 6
    nop                       ; branch delay slot
    jalr  $t9                 ; jump to 0x81000000  <-- crash

  On the GameCube, the game runs inside a built-in N64 emulator.  That
  emulator polls the program counter for the value 0x81000000 and, when
  detected, intercepts execution to play an FMV from the disc instead of
  running any code at that address.

  On real N64 hardware (and N64 emulators), the jump is executed literally.
  0x81000000 maps to physical address 0x01000000 (16 MB), which lies beyond
  the N64 8 MB RAM ceiling.  The CPU raises a bus error and the game crashes.

  Both bne instructions before the jalr already branch to the instruction
  immediately following it (the normal continuation of the credits routine).
  The patch replaces the jalr with a nop.  When the credits reach this point,
  execution falls through the nop and continues normally with the in-engine
  credits sequence.

  ROM size is NOT changed.

Usage:
  python3 patch_gc_credits.py <input.z64> <output.z64>
"""

import struct
import sys


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _u32be(data, offset):
    return struct.unpack_from('>I', data, offset)[0]


def _check_window(rom, off, expected, label):
    for i, exp in enumerate(expected):
        got = _u32be(rom, off + i * 4)
        if got != exp:
            sys.exit(
                "ERROR: %s word[%d] at ROM 0x%08X: "
                "got 0x%08X, expected 0x%08X\n"
                "Wrong ROM version or already patched?" %
                (label, i, off + i * 4, got, exp)
            )


def _write_window(rom, off, words):
    for i, w in enumerate(words):
        struct.pack_into('>I', rom, off + i * 4, w)


# ---------------------------------------------------------------------------
# Instruction window (identical across all four versions)
#
#   lw    $t2, 0x1360($s2)    ; load scene layer counter
#   li    $at, 6              ; credits scene layer value
#   lui   $t9, 0x8100         ; t9 = 0x81000000 (upper half)
#   bne   $t2, $at, +3        ; skip ahead if scene layer != 6
#   nop                       ; branch delay slot
#   jalr  $t9                 ; jump to 0x81000000  <-- patched to nop
# ---------------------------------------------------------------------------

_ORIG = (
    0x8E4A1360,  # lw    $t2, 0x1360($s2)
    0x24010006,  # li    $at, 6
    0x3C198100,  # lui   $t9, 0x8100
    0x15410003,  # bne   $t2, $at, +3
    0x00000000,  # nop
    0x0320F809,  # jalr  $t9                 ; call 0x81000000 -> crash on N64
)

_PATCHED = (
    0x8E4A1360,  # lw    $t2, 0x1360($s2)    (unchanged)
    0x24010006,  # li    $at, 6              (unchanged)
    0x3C198100,  # lui   $t9, 0x8100         (unchanged)
    0x15410003,  # bne   $t2, $at, +3        (unchanged)
    0x00000000,  # nop                       (unchanged)
    0x00000000,  # nop                       ; was jalr $t9 -- patched
)


# ---------------------------------------------------------------------------
# ROM profiles
# ---------------------------------------------------------------------------

PROFILES = [
    ('gc-eu', dict(
        build_data_signature=bytes.fromhex(
            '7A656C6461407372643032326A00000030332D30322D32312032303A31323A3233'
        ),
        patch_rom_off=0x00B119D0,
    )),
    ('gc-eu-mq', dict(
        build_data_signature=bytes.fromhex(
            '7A656C6461407372643032326A00000030332D30322D32312032303A33373A3139'
        ),
        patch_rom_off=0x00B119B0,
    )),
    ('gc-us', dict(
        build_data_signature=bytes.fromhex(
            '7A656C6461407372643032326A00000030322D31322D31392031333A32383A3039'
        ),
        patch_rom_off=0x00B0F920,
    )),
    ('gc-us-mq', dict(
        build_data_signature=bytes.fromhex(
            '7A656C6461407372643032326A00000030322D31322D31392031343A30353A3432'
        ),
        patch_rom_off=0x00B0F900,
    )),
]


# ---------------------------------------------------------------------------
# ROM detection
# ---------------------------------------------------------------------------

def detect_version(rom):
    for name, p in PROFILES:
        if p['build_data_signature'] in rom:
            return name, p
    sys.exit(
        "Could not auto-detect ROM version.\n"
        "Known versions: %s\n"
        "Is this a supported GC OoT ROM?" % ', '.join(n for n, _ in PROFILES)
    )


# ---------------------------------------------------------------------------
# Patch
# ---------------------------------------------------------------------------

def patch_rom(input_path, output_path):
    print("Reading %s ..." % input_path)
    with open(input_path, 'rb') as f:
        rom = bytearray(f.read())

    version, p = detect_version(bytes(rom))
    off = p['patch_rom_off']
    jalr_off = off + 5 * 4
    print("Detected ROM version: %s" % version)

    if _u32be(rom, jalr_off) == _PATCHED[5]:
        sys.exit("ROM appears already patched.")

    _check_window(rom, off, _ORIG, 'ending credits trigger')
    print("  ROM 0x%08X: original instructions verified [OK]" % off)

    _write_window(rom, off, _PATCHED)

    with open(output_path, 'wb') as f:
        f.write(rom)

    print("")
    print("Patched ROM written to: %s" % output_path)
    print("ROM size unchanged: 0x%X bytes" % len(rom))
    print("")
    print("Patch -- ending credits trigger at ROM 0x%08X:" % off)
    print("  jalr $t9  at ROM 0x%08X  0320F809 -> 00000000" % jalr_off)
    print("")
    print("Result:")
    print("  Credits play normally via the in-engine sequence.")
    print("  The jump to 0x81000000 (GC FMV trigger) is suppressed.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python3 %s <input.z64> <output.z64>" % sys.argv[0])
        sys.exit(0)
    patch_rom(sys.argv[1], sys.argv[2])
