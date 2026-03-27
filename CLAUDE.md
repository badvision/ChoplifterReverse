# ChoplifterReverse — DHGR Conversion Project

## Project Goal

Convert ChoplifterReverse from Apple II single hi-res (HGR, 280×192 1bpp) to double hi-res
(DHGR, 560×192 4bpp 16-color). The original game was written for 48K Apple II/II+. This
conversion targets Apple IIe with 64K main + 64K aux (128K total).

**See PLAN.md** for the 9-story milestone plan, current story status, and session kickoff
instructions. Start every session by reading PLAN.md first.

---

## Invariants — What Must NOT Change

- **Jump table entry points** at ~$1000 must remain callable with identical ZP register conventions:
  - `blitImage`, `blitImageFlip`, `blitAlignedImage`
  - `renderTiltedSpriteLeft`, `renderTiltedSpriteRight`
  - `renderSpriteLeft`, `renderSpriteRight`, `renderSpriteFlip`
  - `flipPageMask`, `pageFlip`, `screenFill`, `initRendering`
- **ZP_PAGEMASK ($8D) XOR trick** — the $60 XOR to flip between $2000/$4000 DHGR pages
  works identically in DHGR. Preserved unchanged.
- **All game logic** — physics, input ($C060/$C062), sound ($C030/$C020), entity system,
  scroll physics, game state machine: completely unchanged.
- **All code in main memory** — aux memory holds sprite data only. 65C02 cannot execute
  from aux memory (code fetch always reads main).

---

## Memory Layout

```
MAIN MEMORY
$0800–$1FFF  LOCODE: core game code, init, jump table
$2000–$3FFF  DHGR page 1 (render/display buffer 0) — unchanged address
$4000–$5FFF  DHGR page 2 (render/display buffer 1) — unchanged address
$6000–$8DFF  HICODE: entity logic
$8E01–$8FFF  511 bytes slack — available for loop unrolling
$9000–$9F78  Rendering subsystem (renderMoon, terrain, background)
$9F79–$9FFF  135 bytes slack
$A000–$A0FF  Sprite pointer tables (animation frame sequences) — UNCHANGED
$A100–$A3FF  DHGR row address tables (768 bytes, 4 tables × 192 entries)
$A400–$BEFF  DHGR sprite pixel data — main bank nibbles
$BF00+       ProDOS boundary — do not touch

AUX MEMORY (not executable — data only)
AUX $6100–$BEFF  DHGR sprite pixel data — aux bank nibbles (~22KB)
```

---

## Zero Page Layout (DHGR additions)

```
; Existing — unchanged
ZP_SCREEN_X        = $82
ZP_SCREEN_Y        = $83
ZP_BUFFER          = $84  ; DHGR row base pointer (lo)
ZP_BUFFER+1        = $85  ; (hi)
ZP_PAGEMASK        = $8D  ; $00=page1, $60=page2 (XOR with row hi byte)
ZP_SCROLLPOS       = $8E

; Repurposed
ZP_PALETTE         = $8C  ; → ZP_BLIT_FLAGS: bit0=flip-H, bit1=flip-V, bit2=use-aux

; NEW — confirmed unused in original
ZP_AUXPTR_L        = $B4  ; aux memory sprite data pointer (lo)
ZP_AUXPTR_H        = $B5  ; (hi)
ZP_TMPBYTE         = $B6  ; single-byte temp for read-then-write sequence
ZP_BLIT_WIDTH      = $B7  ; sprite width in DHGR columns
ZP_BLIT_HEIGHT     = $B8  ; sprite height in rows
```

---

## DHGR Init Sequence (order-dependent)

```asm
; In enableHiResGraphics replacement:
    STA   $C00D         ; 80COL ON (must precede AN3)
    STA   $C05E         ; AN3 OFF = DHGR color mode ($C05F = mono DHGR — avoid)
    STA   $C050         ; GRAPHICS ON
    STA   $C052         ; FULLSCREEN
    STA   $C057         ; HIRES ON
    STA   $C054         ; PAGE 1 (or $C055 for page 2)
    STA   $C004         ; RAMWRMAIN (writes → main)
    STA   $C002         ; RAMRDMAIN (reads ← main)
```

**Risk**: $C05E vs $C07E for AN3 — verify on real IIe hardware or cycle-accurate emulator
in Story 1. $C05E is the IIe standard; $C07E appears in some references.

---

## Dual-Bank Write Pattern (blitter inner loop)

Every DHGR screen write touches the same address twice — once in aux bank, once in main bank.
Bit 7 of EVERY byte written to DHGR screen MUST be 0 (always AND with $7F before write).

```asm
; Per DHGR column — must NEVER have RAMRDAUX + RAMWRAUX simultaneously active
; (code fetch would read from aux, causing crash)

    ; STEP 1: Read aux sprite byte
    STA   $C003         ; RAMRDAUX
    LDA   (ZP_AUXPTR_L),Y
    TAX                 ; stash in X (or ZP_TMPBYTE)
    STA   $C002         ; RAMRDMAIN — restore before any write

    ; STEP 2: Write aux nibble to DHGR aux screen bank
    STA   $C005         ; RAMWRAUX
    STX   (ZP_BUFFER),Y
    STA   $C004         ; RAMWRMAIN — restore

    ; STEP 3: Write main nibble to DHGR main screen bank
    LDA   main_sprite_byte
    STA   (ZP_BUFFER),Y
    INY
```

---

## DHGR Color Encoding

- 1bpp black (0) → DHGR index 0 (Black)
- 1bpp white (1) → DHGR index 15 (White) — configurable per sprite via header byte
- DHGR 16-color palette: 0=Black, 1=Magenta, 2=DarkBlue, 3=Purple, 4=DarkGreen,
  5=Gray1, 6=MedBlue, 7=LtBlue, 8=Brown, 9=Orange, 10=Gray2, 11=Pink,
  12=Green, 13=Yellow, 14=Aqua, 15=White

---

## Sprite Data Format (DHGR)

Main bank block (at $A400+):
```
Byte 0:  width in DHGR columns (7 pixels per column)
Byte 1:  height in rows
Byte 2:  foreground color index (0–15)
Byte 3:  reserved (0)
Bytes 4+: main-bank pixel bytes, row-major (1 byte per column per row)
```

Aux bank block (at AUX $6100+ — parallel offset to main block):
```
Byte 0:  width (same)
Byte 1:  height (same)
Byte 2:  color index (same, for validation)
Byte 3:  reserved (0)
Bytes 4+: aux-bank pixel bytes, row-major
```

Conversion tool: `tools/convert_sprites.py` — converts 1bpp sprites to DHGR 4bpp.
Run via `make sprites`. Also produces PNG preview for visual validation.

---

## Jace Emulator — Visual Validation

**This is your primary validation tool. Every story requires visual validation via Jace.**

### Two modes:

**GUI (visual validation + screenshots)**:
```bash
open "/Users/brobert/Downloads/Jace"
# Then load disk: drag .po file onto window or use File menu
# Screenshot: screencapture -x /tmp/jace_frame.png
# Then use Read tool to view the PNG for multimodal review
```

**Maven terminal (automated checks, memory inspection)**:
```bash
cd ~/Documents/code/jace
mvn -q exec:java \
  -Dexec.mainClass="jace.JaceLauncher" \
  -Dexec.args="--terminal" <<'EOF'
bootdisk d1 /Users/brobert/Documents/code/ChoplifterReverse/CHOPLIFTER.po
run 5000000
m
C07F
b
qq
EOF
```

### Key Maven terminal commands:
- `bootdisk d1 <path>` — load disk image
- `run <cycles>` — execute N cycles (1,021,875 cycles ≈ 1 second)
- `m` — enter memory monitor
- `<addr>` — show byte at address
- `<addr>.<addr>` — show range
- `b` — back from monitor
- `savebin <file> <addr> <len>` — save memory region to file (hex length)
- `showtext` — show text screen
- `qq` — quit

### FPS measurement (Story 6+):
```
run 5000000
m
7000.7001
b
```
FPS = 1,021,875 / [16-bit value at $7000]

### Why Jace is essential:
Jace is a cycle-accurate Apple IIe emulator in Java. It correctly emulates DHGR color mode,
aux memory bank switching, and the 80-column card — the three hardware features this
conversion depends on. Without cycle-accurate DHGR emulation, visual validation of color
correctness is impossible without real hardware. Jace provides deterministic results
(same disk image = same output) enabling regression testing. The Maven terminal mode
enables scripted memory inspection for byte-level validation without manual interaction.

---

## Conversion Roadmap

9 sequential stories. No parallelism — each story produces a runnable binary that is
the prerequisite for the next. See PLAN.md for full acceptance criteria per story.

```
Story 0  Repo setup, reference build, CLAUDE.md + PLAN.md ← YOU ARE HERE
Story 1  DHGR mode init (blank screen, correct soft switches)
Story 2  Row tables + dual-bank write infrastructure (12-stripe test)
Story 3  Static background: sky, stars, terrain, moon, houses
Story 4  blitImage ported — single sprite (helicopter head-on only)
Story 5  All 9 blit functions + full sprite data conversion (1bpp → 4bpp)
Story 6  FPS benchmark baseline recorded at $7000/$7001
Story 7  Three optimizations: byte-aligned sprites → fix erase pass → hot data locality
Story 8  Integration regression: title, sortie, gameplay, game-over; final FPS >= 20
```

Target: >= 20 FPS (51,094 cycles/frame). Stretch: >= 25 FPS (40,875 cycles/frame).
FPS formula: 1,021,875 / [cycles_per_frame at $7000/$7001 as 16-bit little-endian].

---

## Risks and Known Unknowns

| Risk | Story | Mitigation |
|---|---|---|
| AN3 address: $C05E vs $C07E | 1 | Verify empirically in jace; both tested |
| ZP_PALETTE non-rendering reads | 3 | grep choplifter.s for $8C before reassigning |
| DHGR color phase encoding accuracy | 2, 7 | Validate stripe test screenshot empirically |
| Non-rendering game cycle cost unknown | 6 | Story 6 measures; if >15K cycles adjust Story 7 targets |
| renderMoon: 50+ hard-coded HGR addresses | 3 | Handle individually; highest-risk function in Story 3 |
| Aux memory sprite data too large for AUX $6100–$BEFF | 5 | 4bpp sprites ~29KB vs ~22KB available; may need $6000 too |
| RAMRDAUX+RAMWRAUX simultaneously = code fetch from aux = crash | Every story | Strictly follow read→restore→write→restore sequence |

---

## Build System

```bash
cd ~/Documents/code/ChoplifterReverse
make all          # build everything
make sprites      # convert sprites (Story 5+)
make clean        # clean build artifacts
```

Binary output: CHOPLIFTER.po (146432 bytes, ProDOS disk image)
Reference checksum stored in: /tmp/choplifter-s0-reference.md5
