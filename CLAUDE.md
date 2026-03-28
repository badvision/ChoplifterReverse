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
$8E01–$8EC0  dhgrRowLo — 192 DHGR row address low bytes (in HICODE slack)
$8EC1–$8F80  dhgrRowHi — 192 DHGR row address high bytes (in HICODE slack)
$A100–$A3FF  (reserved for future DHGR row tables if needed; currently unused)
$A102–$AB1B  CHOP1 occupies this range (19228 bytes, HGR sprite pixel data — not yet DHGR)
$AB1C+       DHGR sprite pixel data starts here — main bank nibbles (Story 4+)
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

; NEW — confirmed unused in original (Story 2 additions)
ZP_DHGR_ROW_L      = $B4  ; DHGR row pointer low byte (repurposed from ZP_UNUSEDB4)
ZP_DHGR_ROW_H      = $B5  ; DHGR row pointer high byte (repurposed from ZP_UNUSEDB5)
ZP_FILL_BYTE       = $B6  ; fill value for screenFill / stripe test
ZP_STRIPE_IDX      = $B7  ; outer stripe counter (0..11) for stripeTest
ZP_STRIPE_FILL     = $B8  ; stripe fill byte temp for stripeTest
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

### One mode: Maven terminal (everything — checks, memory, AND screenshots)

The standalone binary (`/Users/brobert/Downloads/Jace`) does NOT support terminal/scripting mode.
Use ONLY the Maven/Java version for all automation and visual validation.

```bash
cd ~/Documents/code/jace
mvn -q exec:java -Dexec.mainClass="jace.JaceLauncher" -Dexec.args="--terminal" <<'EOF'
bootdisk d1 /Users/brobert/Documents/code/ChoplifterReverse/CHOPLIFTER.po 7
run 10000000
screenshot /tmp/jace_frame.png
m
C07F
b
qq
EOF
# Then: Read /tmp/jace_frame.png for multimodal review
```

**Always pass `7` as the slot argument** — slot 7 = SmartPort = instant disk reads.
Slot 6 (default) = spinning Disk ][ emulation = ~600 real seconds to boot.

### Key Maven terminal commands:
- `bootdisk d1 <path>` — load disk image and boot
- `run <cycles>` — execute N cycles (1,021,875 cycles ≈ 1 second)
- `screenshot <file.png>` (alias `ss2`) — render current DHGR screen to 1120×384 PNG with NTSC color
- `m` — enter memory monitor
- `<addr>` — show byte at address
- `<addr>.<addr>` — show range
- `b` — back from monitor
- `savebin <file> <addr> <len>` — save main memory region to file (hex length)
- `saveauxbin <file> <addr> <len>` — save aux memory region to file
- `showtext` — show text screen contents
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

## Discovered Facts (updated as stories complete)

### Story 1 findings
- `enableHiResGraphics` is **dead code** in normal gameplay — called only from a loader stub
  at `$300-$305` that is not part of the main game flow. The actual graphics init path goes
  through `initRendering`. Story 2+ work on DHGR initialization must target `initRendering`.
- AN3 address: **`$C05E` works** on Jace (IIe standard). `$C07E` fallback not needed.
- Uninitialized DHGR VRAM produces vertical color stripes (not HGR diagonal banding) — this
  is expected until `screenFill` is implemented in Story 2.

### Story 2 findings
- **DHGR row tables cannot be placed at $A100/$A200**: CHOPGFX loads at $A102 and would
  overwrite them. Tables must be placed BEFORE $A102 or in a non-overlapping area.
  SOLUTION: Tables placed in HICODE slack at $8E01 (dhgrRowLo) and $8EC1 (dhgrRowHi).
  Both are within the $6000-$A0FF coverage of fileRead1 in the loader.
- **Always use slot 7 (SmartPort) for disk images**: `bootdisk d1 CHOPLIFTER.po 7`
  Slot 6 (default) emulates a spinning Disk ][ — ProDOS file I/O takes ~600 real seconds.
  Slot 7 (SmartPort) is a virtual hard-disk with instant reads. Full ProDOS boot + game
  load completes in ~5-10M cycles with slot 7.
- **`bootdisk` stops at ROM address $FA62**: stops as soon as PC >= $2000 (ROM reset
  vector). ProDOS loader runs AFTER this. Always follow with `run 10000000` (slot 7).
- **screenFill confirmed working**: page 2 cleared to $00 ($4000=all zeros), page 1 also
  initially cleared then overwritten by stripeTest.
- **stripeTest confirmed working**: $2000=$77 (row 191 = stripe 11, fill $77 correct).
  After `run 20000000`, game has overwritten page 1 with HGR blit data (expected — those
  blitters not yet DHGR-aware).
- **DHGR mode active**: game runs to title screen, DHGR screen shows graphical content.
  The garbled appearance is expected — HGR blit functions are Story 4 work.

### Story 3 findings
- **blitRect row table overrun**: `blitRect` used sprite height as row count, decrementing
  `ZP_RENDER_CURR_Y` below 0 (wrapping to 255). Row table lookup at index 192+ returns
  $00 from zero-padded slack area. The resulting write address $0000+Y (Y=column byte)
  pointed directly into ZP $00-$27, corrupting ZP vectors $28-$2B with whatever pixel
  values were being blitted. Fix: added `lda ZP_RENDER_CURR_Y / beq blitRectDone` bounds
  check before `dec ZP_RENDER_CURR_Y`.
- **blitRect RAMWRAUX missing SEI/CLI**: Added SEI before `STA $C005` (RAMWRAUX) and CLI
  after `STA $C004` (RAMWRMAIN) in blitRect. ProDOS 1/60-sec timer IRQ was firing during
  the RAMWRAUX window; the IRQ handler restores RAMWRMAIN then writes cursor state to main
  ZP $24-$2F, corrupting game vectors. The bounds-check fix was the actual root cause;
  the SEI/CLI is defensive hardening.
- **screenFill, renderMoon, renderStars, blitStars** all DHGR-converted (work done in
  previous sessions). Dual-bank RAMWRAUX/RAMWRMAIN pattern with `stz` for main bank zeros.
- **blitAlignedImage stub** — RTS. Houses not visible as distinct shapes; terrain/base
  render via blitRect which works. Houses will be properly rendered in Story 4+ when
  CHOPGFX is restored at $A400.
- **Sky confirmed black**: DHGR page 1 rows 0, 1, 2 (addresses $2000, $2400, $2800 main
  bank) all $00 at 10M cycles — sky fill correct.

### Story 4 findings
- **CHOP1 end address**: CHOP1 (19228 bytes) loads at $6000, ends at $AB1B. First available
  DHGR sprite data address is $AB1C. Story 4 sprite data placed there with `.org $AB1C` in
  the HICODE segment of choplifter.s.
- **parseImageHeader advances +2 only**: `parseImageHeader` reads bytes 0 (width) and 1
  (height), then advances ZP_PARAM_PTR by exactly 2. After the call, ZP_PARAM_PTR points
  at byte 2 (color index), NOT at pixel data (byte 4). `blitImage` must manually add +2
  to skip the color/reserved bytes before reaching pixel data.
- **Guard threshold $AB**: The guard `lda ZP_PARAM_PTR_H / cmp #$AB / bcc blitImageDone`
  uses $AB because DHGR sprite data starts at $AB1C ($AB00 page). All legacy HGR sprite
  pointers point at $A100-$AABB range (CHOPGFX data at $A102+), which passes the guard.
  Only confirmed DHGR data at $AB1C+ should be rendered; old data guard prevents garbage.
- **Inner loop register conflict**: 6502 indirect-Y (`(ptr),y`) requires Y as the offset.
  With Y needed for both sprite column index and screen column index, a save/restore via
  ZP_DRAWSCRATCH1 is used: `sty ZP_DRAWSCRATCH1 / txa / tay / lda (ptr),y /
  ldy ZP_DRAWSCRATCH1` to use X as sprite column and Y as screen column.
- **Sprite visible but colorful**: NTSC DHGR color encoding produces color fringing on the
  white sprite bytes. This is expected — Story 4 writes the same byte value to both aux
  and main banks (simplified white-only mode). True 4bpp color encoding requires separate
  aux/main nibble data, deferred to Story 5.
- **chopperHeadOnSpriteTable runtime animation**: After 10M cycles the game's animation
  counter has advanced the table frame pointer away from $A016=$AB1C. This is normal
  runtime behavior — the table cycles through 5 head-on frames. The initial frame (index 0)
  renders the DHGR sprite; other frames still point at HGR data and are rejected by the
  guard, producing transparent frames during rotation animation.
- **Story 5 note**: The simplified single-bank write (same value to aux and main) must be
  replaced with true dual-bank color data: aux bank receives lower nibble, main bank
  receives upper nibble of each DHGR 4bpp color pair.

### Story 5 findings
- **RAMRDAUX crash in HICODE**: `STA $C003` (RAMRDAUX) inside HICODE ($6000+) crashes
  because AUX memory at those addresses holds sprite data or zeros — not valid opcodes.
  After RAMRDAUX, the CPU fetches the next instruction from AUX, gets garbage, and hits
  BRK. Solution: never place RAMRDAUX-using code in HICODE; see trampoline below.
- **auxReadByte trampoline ($1AA7, 10 bytes in LOCODE)**: Safe RAMRDAUX read from AUX sprite
  data via a 10-byte stub placed at $1AA7 in LOCODE (within CHOP0 = $0800–$1FFF).
  Bytes: `8D 03 C0 B1 BA AA 8D 02 C0 60` = STA $C003 / LDA (ZP_AUX_SPRITE_PTR_L),Y /
  TAX / STA $C002 / RTS. The loader mirrors these 10 bytes to AUX $1AA7 via RAMWRAUX
  before jumping to $0300. With AUX $1AA7 containing the same opcodes as MAIN, RAMRDAUX
  opcode fetches execute the correct code. Returns: X = AUX pixel byte. Clobbers: A, X.
  Preserves: Y. ZP_AUX_SPRITE_PTR_L/H ($BA/$BB) must be set to the AUX row base address.
- **emit_inc() headers-only architecture**: `choplifter_sprites.inc` contains only the
  4-byte sprite headers (W, H, aux_ptr_lo, aux_ptr_hi) at $AB1C — total 512 bytes for
  128 sprites. Pixel data lives ONLY in CHOPAUX (AUX file loaded to AUX $6100 by loader).
  Adding pixel bytes to the inc causes HIRAM overflow (5339 bytes > 512-byte budget at $AB1C).
- **ca65 .org in relocatable segment**: `.org` sets label addresses to the specified value
  but does NOT insert filler bytes. Data lands at the natural code position in the binary.
  Using `.org $1D92` to place trampoline caused JSR to call the wrong address ($1D92 label,
  but bytes landed at $1AA7). Fix: remove `.org`, place code at its natural LOCODE position,
  use `auxTrampolineBase = <actual address>` constant in loader.s.
- **Sprite header format at $AB1C**: `.byte W, H, aux_ptr_lo, aux_ptr_hi` (4 bytes per
  sprite, no pixel data in MAIN). blitImage reads aux_ptr from bytes 2–3 and stores in
  ZP_AUX_SPRITE_PTR_L/H ($BA/$BB) before calling auxReadByte for each pixel.
- **CHOPAUX size**: 5339 bytes ($14DB). Loaded by loader to AUX $4400 (avoids 1KB I/O
  buffer at $4000–$43FF), then copied page-by-page to AUX $6100 via RAMWRAUX loop.
  chopAuxLen = $14DB must match both loader.s constant and fileReadAux parameter.
- **AUX ZP_AUX_SPRITE_PTR_L/H = $BA/$BB**: Used as the base pointer for auxReadByte.
  blitImage advances this pointer by ZP_IMAGE_W after each row to step through sprite data.
- **Jace terminal screenshot limitation**: In headless mode, `screenshot` captures the text
  framebuffer, not the DHGR graphics framebuffer. VRAM content must be verified via `m`
  memory dumps (DHGR VRAM $2000+ showed terrain pattern `51 4A 51 4A...` confirming active
  rendering). Visual DHGR screenshots require Jace GUI mode.
- **HGR bytes-per-row formula**: `ceil(W_pixels / 8)` (NOT 7px/byte as in DHGR screen columns).
  A 12-pixel-wide sprite = ceil(12/8) = 2 bytes per row. HGR sprite header byte 0 is pixel width, not column count.
  DHGR sprite header byte 0 is bytes-per-row (same value as HGR: ceil(pixel_width/8)).

### Story 6 findings
- **blitImage/blitImageFlip right-edge column overflow**: The inner column loop `STA (ZP_DHGR_ROW_L),Y`
  had no right-edge clamp. DHGR page 2 bottom row (dhgrRowHi[0] XOR $60 = $5F, dhgrRowLo[0] = $D0)
  base address = $5FD0. Y=$30 (column 48) → $5FD0 + $30 = $6000 — overwrites the HICODE jump table.
  Fix: added `cpy #40 / bcs blitImageSkipPx` in both `blitImageColLoop` and `blitImageFlipColLoop`
  before any dual-bank write. Also catches left-underflow in flip mode (Y=$FF after dey from 0,
  since $FF >= 40 = bcs taken).
- **auxTrampolineBase address is fragile**: Every instruction added or removed before `auxReadByte`
  in LOCODE shifts its assembled address. After the right-edge clamp (4 bytes added: `cpy #40` + `bcs`
  in each of two loops = 8 bytes), `auxReadByte` shifted from $1AE0 to $1AE8. loader.s
  `auxTrampolineBase` must be updated after every LOCODE code change. Always verify against
  choplifter.lst grep for `auxReadByte:`.
- **Jace monitor `run` command not valid in monitor mode**: Must exit monitor with `q` before
  issuing `run`. `b` in monitor mode sets a breakpoint (not "back"). `q` or `back` returns to main mode.
- **Jace memory read mid-RAMWRAUX window**: Stopping execution while RAMWRAUX is active ($C005 set)
  causes the monitor to read AUX memory at the inspected address. $6000 in AUX holds DHGR screen
  data ($00/$FF alternating), not the jump table. Apparent corruption at stop points is a read-bank
  artifact, not actual main memory corruption. Confirmed via `watch 6000` showing no WRITEs.
- **Story 6 FPS baseline**: **~5.9 FPS** (measured 2026-03-28).
  Method: `FPS_COUNTER_L/H` at $68E5/$68E6 (16-bit, incremented in `pageFlip` at $138C).
  Data: 29 frames in 5,000,000 cycles (15M→20M cycle interval, post-startup steady state).
  FPS = 29 × 1,021,875 / 5,000,000 = 5.93. Cycles/frame ≈ 172,414.
  This is the unoptimized baseline. Story 7 targets must bring this above 20 FPS.
  Note: 20 FPS target requires 51,094 cycles/frame — a 3.4× improvement over baseline.
- **SEI is permanent** during gameplay: `initRendering` sets SEI and never clears it.
  ProDOS 1/60-sec timer IRQ is permanently blocked from the moment rendering starts.
  This is intentional (prevents RAMWRAUX IRQ hazard) but removes the vsync-based timing
  that the original game relied on. FPS is purely cycle-count driven.

---

## Conversion Roadmap

9 sequential stories. No parallelism — each story produces a runnable binary that is
the prerequisite for the next. See PLAN.md for full acceptance criteria per story.

```
Story 0  Repo setup, reference build, CLAUDE.md + PLAN.md  [DONE — bb024d3..3d435eb]
Story 1  DHGR mode init (blank screen, correct soft switches)  [DONE — bb024d3]
Story 2  Row tables + dual-bank write infrastructure (12-stripe test)  [DONE — 2026-03-27]
Story 3  Static background: sky, stars, terrain, moon, houses  [DONE — 2026-03-27]
Story 4  blitImage ported — single sprite (helicopter head-on only)  [DONE — 2026-03-27]
Story 5  All sprites converted, auxReadByte trampoline, CHOPAUX pipeline  [DONE — 2026-03-27]
Story 6  FPS benchmark baseline recorded at $68E5/$68E6  [DONE — 2026-03-28, 5.9 FPS]
Story 7  Three optimizations: byte-aligned sprites → fix erase pass → hot data locality
Story 8  Integration regression: title, sortie, gameplay, game-over; final FPS >= 20
```

Target: >= 20 FPS (51,094 cycles/frame). Stretch: >= 25 FPS (40,875 cycles/frame).
FPS formula: frames_delta × 1,021,875 / cycles_delta (using FPS_COUNTER_L/H at $68E5/$68E6).
Note: $7000/$7001 = BOUNDS_LEFT_L/H (game constants) — NOT the FPS counter address.

---

## Risks and Known Unknowns

| Risk | Story | Mitigation |
|---|---|---|
| AN3 address: $C05E vs $C07E | 1 | Verify empirically in jace; both tested |
| ZP_PALETTE non-rendering reads | 3 | grep choplifter.s for $8C before reassigning |
| DHGR color phase encoding accuracy | 2, 7 | Validate stripe test screenshot empirically |
| Non-rendering game cycle cost unknown | 6 | Story 6 measures; if >15K cycles adjust Story 7 targets |
| renderMoon: 50+ hard-coded HGR addresses | 3 | Handle individually; highest-risk function in Story 3 |
| Aux memory sprite data too large for AUX $6100–$BEFF | 5 | RESOLVED S5: 1bpp→DHGR strips HGR palette bit ($7F AND), total 5339 bytes fits in AUX $6100–$7536 |
| RAMRDAUX+RAMWRAUX simultaneously = code fetch from aux = crash | 5 | RESOLVED S5: auxReadByte trampoline at $1AA7 (LOCODE) mirrored to AUX by loader; RAMRDAUX safe from trampoline |

---

## Build System

```bash
cd ~/Documents/code/ChoplifterReverse
make all          # build everything
make sprites      # convert sprites (Story 5+)
make clean        # clean build artifacts
```

Binary output: CHOPLIFTER.po (146432 bytes, ProDOS disk image)
Reference checksum: `976db862ffc405b4f1c83545edd8c2ed  CHOPLIFTER.po` (146,432 bytes)
Note: use `make clean diskimage loader choplifter` — NOT `make all` (emulate target requires Xcode)

IMPORTANT: `cadius CREATEVOLUME` embeds a build timestamp in volume metadata.
`CHOPLIFTER.po` MD5 is non-deterministic — it changes on every rebuild.
Always use CHOP1 (or CHOP0) MD5 as regression baselines, not CHOPLIFTER.po MD5.
Story 4 CHOP1 MD5: da860d5d218f567b9777b940243f97c7

### GitHub Auth

Use the `badvision` account for all git push and PR operations:
```bash
gh auth switch --user badvision
```
The `brobert_adobe` enterprise account cannot fork public repos (EMU policy).
The upstream remote points to `dwsJason/ChoplifterReverse`. Push to your own fork under `badvision`.
