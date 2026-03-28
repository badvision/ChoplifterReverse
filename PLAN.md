# ChoplifterReverse: HGR to DHGR Conversion — Project Plan

**Target repository**: `~/Documents/code/ChoplifterReverse`
**Source**: https://github.com/dwsJason/ChoplifterReverse
**Goal**: Convert single hi-res (HGR) graphics to double hi-res (DHGR) color graphics
**Toolchain**: CC65 assembler, cadius disk image tool, Jace Apple II emulator
**Architecture reference**: `CLAUDE.md` in this repository

---

## Current Story

> Update this section at the start of each session. It is the primary session-resume signal.

**Current story**: Story 7 — Rendering Optimizations
**Status**: NOT STARTED
**Last session**: 2026-03-28 (Story 6 completed, baseline FPS = 5.9)
**Blocking issues**: None

---

## Baseline Metrics

> Populated progressively. Never delete entries; add new rows.

| Metric | Value | Story | Date |
|--------|-------|-------|------|
| Reference binary checksum | (capture in Story 0) | S0 | — |
| Story 2 binary checksum | d66da169a5a98ba9bd5e8889c5a25987 | S2 | 2026-03-27 |
| Story 3 binary checksum | 443251a24d7afaa5404eac99377dbbb6 | S3 | 2026-03-27 |
| Story 4 CHOP1 MD5 (stable) | da860d5d218f567b9777b940243f97c7 | S4 | 2026-03-27 |
| Story 5 CHOP1 MD5 (stable) | 552f3d751ccc05d98d5a6e62587ce09a | S5 | 2026-03-27 |
| Story 5 CHOP0 MD5 (stable) | 4a2ae49116907507040f511eacd52ce0 | S5 | 2026-03-27 |
| Story 6 CHOP1 MD5 (stable) | d4e8fd677d79ffcaebfd08d1d97a982c | S6 | 2026-03-28 |
| Story 6 CHOP0 MD5 (stable) | 6bdf07482d9feca23f8c337733c7f723 | S6 | 2026-03-28 |
| DHGR baseline cycles/frame | ~172,414 | S6 | 2026-03-28 |
| DHGR baseline FPS | ~5.9 FPS | S6 | 2026-03-28 |
| Post-opt-7a cycles/frame | (capture in Story 7a) | S7 | — |
| Post-opt-7b cycles/frame | (capture in Story 7b) | S7 | — |
| Post-opt-7c cycles/frame | (capture in Story 7c) | S7 | — |
| Final FPS (Story 8) | (capture in Story 8) | S8 | — |
| Final binary checksum | (capture in Story 8) | S8 | — |

Note: `cadius CREATEVOLUME` embeds a build timestamp in volume metadata.
`CHOPLIFTER.po` MD5 is non-deterministic (changes on every rebuild).
Use CHOP1 (or CHOP0) MD5 for all regression baselines — those are stable.

FPS formula: `1,021,875 / [cycles_per_frame]`
Target: >= 20 FPS (51,094 cycles/frame maximum)
Stretch target: >= 25 FPS (40,875 cycles/frame maximum)

---

## Session Notes

> Append one entry per session. Newest at top.

### Session 5 — 2026-03-28
- Story 6 completed: FPS benchmark baseline measured at ~5.9 FPS (172,414 cycles/frame).
- Two bugs fixed during stabilization:
  1. `.org $1FF6` removed from choplifter.s — the directive was setting auxReadByte label address
     to $1FF6 but bytes physically landed at their natural LOCODE position. JSR called $1FF6
     (unwritten memory = zeros = BRK). auxReadByte now at natural position $1AE8 (post-fix).
  2. blitImage/blitImageFlip right-edge column overflow — no clamp on Y before dual-bank write.
     DHGR page 2 bottom row at $5FD0; Y=$30 (col 48) → $6000 = HICODE jump table corruption.
     Fix: `cpy #40 / bcs skip` added in both blitImageColLoop and blitImageFlipColLoop.
     Also fixes blitImageFlip left-underflow: Y=$FF after dey from 0 → $FF >= 40 → skip.
- auxTrampolineBase updated: $1AE0 → $1AE8 after 8 bytes of column clamp code added.
- FPS counter confirmed at $68E5/$68E6 (not $7000/$7001 which = BOUNDS_LEFT_L/H game constants).
- Jace terminal notes: use `q` to exit monitor mode (not `b`); `b` sets a breakpoint.
  Jace memory reads while RAMWRAUX active return AUX bank values — not actual main corruption.
- Story 6 CHOP1 MD5 (stable): d4e8fd677d79ffcaebfd08d1d97a982c
- Story 6 CHOP0 MD5 (stable): 6bdf07482d9feca23f8c337733c7f723

### Session 4 — 2026-03-27
- Story 5 completed: all 128 sprites converted and loaded; auxReadByte trampoline enables
  safe RAMRDAUX reads; blitImage/blitImageFlip ported to dual-bank DHGR writes.
- Key implementation: CHOPAUX (5339 bytes) loaded to AUX $6100 by loader. Headers-only
  (.byte W, H, aux_ptr_lo, aux_ptr_hi) placed at HICODE $AB1C (512 bytes = 128 sprites × 4 bytes).
  Pixel data lives exclusively in AUX memory — never in MAIN.
- Key discovery: RAMRDAUX crash — STA $C003 inside HICODE ($6000+) crashes because AUX at
  those addresses contains sprite data/zeros, not valid opcodes. CPU fetches garbage → BRK.
  Solution: auxReadByte trampoline (10 bytes at $1AA7 in LOCODE). Loader mirrors these
  bytes to AUX $1AA7 via RAMWRAUX loop so RAMRDAUX is safe: AUX $1AA7 has valid opcodes.
- Key discovery: ca65 .org in relocatable segment sets label addresses but does NOT insert
  filler — bytes land at the natural code position. Attempted .org $1D92 trampoline
  placement caused JSR to call wrong address. Fix: removed .org, used natural LOCODE placement.
- Key discovery: convert_sprites.py emit_inc() must output headers-only (4 bytes/sprite).
  Adding pixel bytes to the inc caused HIRAM overflow (503 bytes). Pixel data must stay
  in CHOPAUX (AUX file only).
- Jace validation confirmed: PC=$185B (blitImage inner loop), $AB1C correct sprite headers,
  $1AA7 trampoline intact, DHGR VRAM $2000+ non-zero (terrain/sky pattern active).
- Story 5 CHOP1 MD5 (stable): 552f3d751ccc05d98d5a6e62587ce09a
- Story 5 CHOP0 MD5 (stable): 4a2ae49116907507040f511eacd52ce0

### Session 3 — 2026-03-27
- Story 4 completed: blitImage DHGR port — helicopter head-on sprite visible.
- Key implementation: chopperHeadOnDHGR0 sprite data placed at $AB1C (first byte after
  CHOP1 at $AB1B). Data is 2 cols × 13 rows, white, CHOPGFX bytes ANDed with $7F.
- Key discovery: parseImageHeader advances ZP_PARAM_PTR by only 2 bytes (reads bytes 0
  and 1), not 4. Must manually add +2 after call to skip color/reserved bytes.
- Key discovery: inner loop register conflict resolved with ZP_DRAWSCRATCH1 save/restore —
  X used for sprite column, Y for screen column, with txa/tay for indirect-Y reads.
- Guard confirmed working: ptr_H < $AB triggers early RTS, old HGR pointers transparent.
- Sprite visible on screenshot: head-on helicopter shape with NTSC color in upper-right
  area, black sky/stars background and terrain still intact (Story 3 background preserved).
- Memory at $AB1C = $02 confirmed. chopperHeadOnSpriteTable[0] = $AB1C confirmed.
- Story 4 CHOP1 MD5 (stable): da860d5d218f567b9777b940243f97c7
- Story 4 CHOPLIFTER.po MD5 (non-deterministic, cadius timestamp): varies per rebuild

### Session 2 — 2026-03-27
- Story 2 completed: DHGR row tables, screenFill, stripeTest implemented and validated.
- Key discovery: DHGR row tables at $A100/$A200 conflict with CHOPGFX load at $A102.
  Tables relocated to HICODE slack area $8E01/$8EC1 (384 bytes within 511-byte slack).
- Key discovery: ProDOS boot requires ~10M+ emulated cycles to complete disk I/O.
  Jace boot validation must use `run 20000000` minimum, not `run 3000000`.
- stripeTest verified: $2000=$77 (row 191, stripe 11 fill), page 2 cleared to $00.
- DHGR mode active: screenshot shows graphical content (garbled title screen expected —
  HGR blit functions not yet DHGR-aware, that is Story 4 work).
- Story 2 CHOPLIFTER.po MD5: d66da169a5a98ba9bd5e8889c5a25987

### Session 1 — 2026-03-27
- Requirements analysis and architecture design completed by prior agents.
- PLAN.md and CLAUDE.md written by product owner agent.
- Story 0 is ready to execute: clone repo, build, capture reference checksum.
- Key risk flagged: 4bpp sprite data expansion (~7.4KB → ~30KB) requires aux memory placement.

---

## Architecture Quick Reference

Full architecture in `CLAUDE.md`. Summary for session context:

**DHGR init order** (order-dependent, do not reorder):
1. 80-column card active: `bit $C00D` then `bit $C00F`
2. Enable AN3 color mode: `bit $C05E` → `bit $C07E`
3. Display page 2, full screen, hi-res, DHGR: `bit $C057` → `bit $C052` → `bit $C050` → `bit $C05F`

**Dual-bank write pattern** (used by every VRAM write):
```
bit $C003    ; RAMRDAUX
lda (src),y  ; read from aux
bit $C002    ; RAMRDMAIN
bit $C005    ; RAMWRAUX
sta (dst),y  ; write to aux VRAM
bit $C004    ; RAMWRMAIN
sta (dst),y  ; write to main VRAM
```

**New zero page variables**:
- `ZP_AUXPTR_L` = $B4, `ZP_AUXPTR_H` = $B5 (aux memory row pointer)
- `ZP_TMPBYTE` = $B6 (temp for dual-bank pixel hold)
- `ZP_BLIT_WIDTH` = $B7, `ZP_BLIT_HEIGHT` = $B8

**Memory layout**:
- Main $0800–$1FFF: LOCODE (unchanged)
- Main $2000–$5FFF: DHGR display pages 1+2 (main banks)
- Main $6000–$9FFF: HICODE (unchanged)
- Main $A000–$A0FF: sprite pointer tables
- Main $A100–$A3FF: row tables (768 bytes: main base addresses + aux base addresses)
- Main $A400–$BEFF: main-bank sprite pixel data
- Aux $6100–$BEFF: aux-bank sprite pixel data (~29,684 bytes)
- Aux $2000–$5FFF: DHGR display pages 1+2 (aux banks)

**Invariants** (must not change):
- All jump table entry points (blitImage, renderTiltedSprite, etc.)
- ZP_PAGEMASK XOR trick ($60) — works identically for DHGR page selection
- All game logic, physics, input, sound, entity system
- All code in main memory (aux holds sprite data only)

**Color encoding**: 1bpp white pixel → DHGR color index 15 (white); 1bpp black → index 0 (black/transparent)

**Sprite conversion tool**: `tools/convert_sprites.py` — converts 1bpp sprite binaries to DHGR 4bpp format

**Jace emulator**:
- GUI binary: `/Users/brobert/Downloads/Jace` — use for visual/multimodal screenshot review
- Maven terminal (scripted validation): `cd ~/Documents/code/jace && mvn -q exec:java -Dexec.mainClass="jace.JaceLauncher" -Dexec.args="--terminal"`
- Screenshot: `screencapture -x /tmp/jace_frame.png` (requires GUI mode, not terminal)

---

## Stories

Stories are sequential. Do not begin Story N+1 until Story N acceptance criteria are fully verified.
Each story ends with a git commit and a new regression checksum.

---

### Story 0: Repo Setup + Reference Binary

**Status**: NOT STARTED

**Scope**: Establish the working repository, verify clean build, capture reference state.

**Work items**:
1. Fork `dwsJason/ChoplifterReverse` on GitHub; clone to `~/Documents/code/ChoplifterReverse`
2. Run `make all` — verify zero errors and `CHOPLIFTER.po` produced
3. Capture reference checksum to `/tmp/choplifter-s0-reference.md5`
4. Boot disk in Jace Maven terminal — verify no ProDOS error after 5 seconds
5. Scaffold `tools/convert_sprites.py` (stub with argparse, not yet functional)
6. Write `CLAUDE.md` (architecture reference) and this `PLAN.md` into repository
7. Initial git commit with all of the above

**Acceptance criteria** (all must pass before Story 1 begins):

- [ ] `make all 2>&1 | grep -c "error:"` returns `0`
- [ ] `ls -la CHOPLIFTER.po | awk '{print $5}'` returns `143360`
- [ ] `/tmp/choplifter-s0-reference.md5` file exists and is non-empty
- [ ] Jace Maven boot test: `bootdisk d1 CHOPLIFTER.po` + `run 5000000` + `showtext` shows game content (not ProDOS startup)
- [ ] `tools/convert_sprites.py` exists (stub acceptable)
- [ ] `CLAUDE.md` and `PLAN.md` committed to repository

**Validation commands**:
```bash
cd ~/Documents/code/ChoplifterReverse
make all 2>&1 | grep -c "error:"          # must be 0
ls -la CHOPLIFTER.po | awk '{print $5}'   # must be 143360
md5sum CHOPLIFTER.po > /tmp/choplifter-s0-reference.md5
cat /tmp/choplifter-s0-reference.md5      # record in Baseline Metrics above
```

Jace boot test:
```bash
cd ~/Documents/code/jace
mvn -q exec:java -Dexec.mainClass="jace.JaceLauncher" -Dexec.args="--terminal" <<'EOF'
bootdisk d1 /Users/brobert/Documents/code/ChoplifterReverse/CHOPLIFTER.po
run 5000000
showtext
qq
EOF
```

**Post-story action**: Record reference checksum in Baseline Metrics table above. Update "Current Story" to Story 1.

---

### Story 1: DHGR Mode Init

**Status**: NOT STARTED
**Prerequisite**: Story 0 complete and verified.

**Scope**: Replace `enableHiResGraphics` with DHGR init sequence. Game launches to blank DHGR screen. All blit calls are no-ops (stubs). No rendering yet — black screen only.

**Files expected to change**: `choplifter.s` (init routine only)

**Work items**:
1. Replace `enableHiResGraphics` at $12C1 with DHGR init sequence (see Architecture Quick Reference)
2. Stub all blit entry points to `rts` (so callers do not crash)
3. Verify `initPageMask` still sets `ZP_PAGEMASK` correctly ($00 for page 1)
4. Build, boot in Jace, verify no crash and DHGR mode active

**Acceptance criteria** (all must pass):

- [ ] `make all 2>&1 | grep -c "error:"` returns `0`
- [ ] Jace Maven terminal: after boot, `m / C07F / b` — bit 7 of returned byte must be 1 (AN3 color mode active)
- [ ] Native Jace GUI screenshot: uniform dark screen visible — NO HGR color fringe columns (no violet/green lines along left or right edge)
- [ ] All blit calls are no-ops (stubs returning immediately) — screen is black only

**Validation — DHGR mode bit check** (Maven terminal):
```
bootdisk d1 /path/to/CHOPLIFTER.po
run 3000000
m
C07F
b
qq
```
The byte at $C07F must have bit 7 set ($80 or higher).

**Validation — visual** (multimodal review):
```bash
/Users/brobert/Downloads/Jace /Users/brobert/Documents/code/ChoplifterReverse/CHOPLIFTER.po &
sleep 4
screencapture -x /tmp/jace_s1.png
```
Review `/tmp/jace_s1.png` for: uniform black or dark screen, no HGR color fringe artifacts.

**Post-story action**: Update "Current Story" to Story 2.

---

### Story 2: DHGR Row Tables + Dual-Bank Write Test

**Status**: NOT STARTED
**Prerequisite**: Story 1 complete and verified.

**Scope**: Implement dual-bank write infrastructure and row address tables. Validate with a standalone 12-stripe color test pattern — not yet part of the game render loop.

**Files expected to change**: `choplifter.s` (add row tables at $A100, add `dhgr_fillrow` test function)

**Work items**:
1. Add dual row tables at $A100–$A3FF (768 bytes: main base addresses + aux base addresses for 192 rows)
2. Implement `dhgr_fillrow` test function: writes a caller-specified color byte to all 40 aux bytes and 40 main bytes of a given row using the dual-bank write pattern
3. Write test program that calls `dhgr_fillrow` 12 times to produce 12 horizontal color stripes (rows 0–15, 16–31, ..., 176–191 each in a distinct color)
4. Build and run test; verify bytes and visual output

**Acceptance criteria** (all must pass):

- [ ] `make all 2>&1 | grep -c "error:"` returns `0`
- [ ] Maven terminal `savebin` check: `savebin /tmp/row.bin [row_0_main_addr] 0028` — all 40 bytes non-zero and uniform within each stripe
- [ ] All written VRAM bytes have bit 7 = 0 (no high bit set — DHGR requirement)
- [ ] Native Jace GUI screenshot: 12 distinct horizontal color bands visible, no missing half-columns, no fringe artifacts
- [ ] At least 4 distinctly different colors visible (validates aux/main interleave is correct)

**Validation — byte check** (Maven terminal):
```
bootdisk d1 /path/to/CHOPLIFTER.po
run 3000000
savebin /tmp/row_main.bin 2000 0028
m
2000.2027
b
qq
```
Inspect `/tmp/row_main.bin`: bytes must be non-zero and uniform per stripe. Bit 7 of every byte must be 0.

**Validation — aux/main interleave check**:
Read main bytes at $2000, then switch to RAMRDAUX and read same range. Both must be non-zero. If aux bytes are $00 while main bytes are non-zero, soft-switch sequencing is broken.

**Validation — visual** (multimodal review):
Capture screenshot of Jace showing the 12-stripe test pattern. Review for 12 distinct color bands.

**Post-story action**: Update "Current Story" to Story 3.

---

### Story 3: Static Background Render

**Status**: DONE — 2026-03-27
**Prerequisite**: Story 2 complete and verified.

**Scope**: Convert background and terrain rendering to DHGR. No sprites in this story — only background elements that do not use sprite pointer lookups.

**Functions to convert**:
- `screenFill` — add RAMWRAUX bracket (40 bytes aux, 40 bytes main per row)
- `renderMoon` — recalculate 50+ hard-coded absolute addresses for DHGR nibble format
- `renderStars` / `renderStars1` — star field using DHGR pixel writes
- `renderBase`, `renderFence`, `renderHouses` — terrain elements (these go through `blitAlignedImage`; that stub must be minimally functional for solid-color fills)

**Acceptance criteria** (all must pass):

- [ ] `make all 2>&1 | grep -c "error:"` returns `0`
- [ ] Screenshot shows: sky (uniform dark color), star field (discrete dots), terrain line, moon (circular shape), houses (rectangular shapes)
- [ ] Terrain Y position matches HGR reference within ±2 pixels (compare to Story 0 screenshot)
- [ ] Sky region bytes uniform: `savebin /tmp/sky_row.bin 2028 0028` — all bytes equal to sky fill value
- [ ] No HGR color fringe on any background element (no violet/green column artifacts)

**Validation — sky byte uniformity** (Maven terminal):
```
bootdisk d1 /path/to/CHOPLIFTER.po
run 5000000
savebin /tmp/sky_row.bin 2028 0028
qq
```
All 40 bytes of the saved bin must equal the sky fill byte.

**Validation — visual comparison** (multimodal review):
1. Capture HGR reference screenshot from Story 0 build at title screen (~2 seconds after boot)
2. Capture DHGR Story 3 screenshot at same game state
3. Compare terrain Y position — must match within ±2 pixels

**Post-story action**: Record new regression checksum. Update "Current Story" to Story 4.

---

### Story 4: Single Sprite Blit (Player Helicopter)

**Status**: DONE — 2026-03-27
**Prerequisite**: Story 3 complete and verified.

**Scope**: Port `blitImage` to DHGR for a single sprite only. Target: `chopperHeadOnSpriteTable[0]` (forward-facing helicopter, used in title sequence). All other sprites remain transparent/stubbed.

**Work items**:
1. Implement `blitImage` for DHGR using dual-bank write pattern and aux-side sprite source reads
2. Convert `chopperHeadOnSpriteTable[0]` sprite data from 1bpp to DHGR 4bpp using `tools/convert_sprites.py`
3. Place converted sprite data in correct memory location (main $A400+ and aux $6100+)
4. Render helicopter head-on sprite at screen center (X=140, Y=96) and capture result

**Acceptance criteria** (all must pass):

- [ ] `make all 2>&1 | grep -c "error:"` returns `0`
- [ ] Screenshot shows helicopter head-on sprite: correct shape, correct DHGR colors, correct position
- [ ] No double-image or ghost pixels (confirms aux + main writes are interleaved correctly)
- [ ] `savebin` of sprite row: non-zero bytes confined to expected width (within ±7 pixels = 1 byte tolerance)
- [ ] At least 2 distinct byte values in sprite VRAM row (confirms 4bpp, not 1bpp monochrome)
- [ ] Background renders correctly behind sprite (Story 3 background still visible)

**Read sprite dimensions first** (establish bounding box for acceptance check):
```bash
# Sprite header is 2 bytes: widthInPixels, heightInPixels
# chopperHeadOnSpriteTable[0] pointer is at $A41B in the binary
xxd CHOPLIFTER.bin | grep -A2 "at offset corresponding to A41B"
```
Record width and height here: width = ___, height = ___

**Validation — bounding box** (Maven terminal):
```
savebin /tmp/sprite_row.bin [row_address_for_Y=96] 0050
```
Non-zero bytes in the saved bin must be confined to the byte range corresponding to X=140 ± sprite_width_bytes.

**Validation — visual** (multimodal review):
Screenshot showing helicopter head-on sprite at center screen with background behind it.

**Post-story action**: Record new regression checksum. Update "Current Story" to Story 5.

---

### Story 5: Full Sprite Pipeline

**Status**: DONE — 2026-03-27
**Prerequisite**: Story 4 complete and verified.

**Scope**: Port all remaining blit functions and convert all sprite data. Full game frame renders correctly with all sprite types.

**Functions to port**:
- `blitImageFlip` — horizontally flipped blit
- `blitAlignedImage` — byte-aligned fast path
- `renderSprite` — full sprite with clip
- `renderSpriteFlip` — flipped sprite with clip
- `renderSpriteRight` — right-facing variant
- `renderTiltedSpriteLeft` / `renderTiltedSpriteRight` — tilted helicopter sprites

**Sprite data to convert** (all via `tools/convert_sprites.py`):
- Helicopter side views: 11 tilt angles
- Helicopter head-on: 5 rotation frames
- Helicopter squished: 2 sprites
- Main rotor: 3 animation frames
- Tail rotor: 4 animation frames
- Enemy jets: 14+ sprites
- Tanks, aliens, hostages, explosions
- HUD elements (bubble, background bubble)
- Title graphics (Choplifter logo, "Your Mission", Broderbund Presents, Dan Gorlin logo, The End, crown, sortie cards)

**Acceptance criteria** (all must pass):

- [ ] `make all 2>&1 | grep -c "error:"` returns `0`
- [ ] Screenshot of full game frame: helicopter visible, ground terrain, at least one enemy type, HUD numbers in correct position
- [ ] Left-facing helicopter screenshot: sprite correctly mirrored
- [ ] Right-facing helicopter screenshot: sprite correctly oriented
- [ ] Animation sequences advance without ghost pixels (no double-image artifacts)
- [ ] `run 30000000` in Maven terminal completes without crash (BRK or hang)
- [ ] No HGR color fringe on any sprite type

**Validation — 30-second run** (Maven terminal):
```
bootdisk d1 /path/to/CHOPLIFTER.po
run 30000000
showtext
qq
```
Must complete without CPU exception. `showtext` output must not contain "SYNTAX ERROR" or "BREAK".

**Validation — left/right facing** (two screenshots):
1. Boot game, record screenshot immediately after title (helicopter faces right)
2. Apply joystick/key input to turn, record screenshot after helicopter faces left
Both screenshots reviewed multimodally for correct sprite orientation.

**Post-story action**: Record new regression checksum. Save Story 5 screenshot as visual baseline for Story 7 regression comparisons. Update "Current Story" to Story 6.

---

### Story 6: FPS Benchmark Baseline

**Status**: DONE — 2026-03-28, baseline 5.9 FPS
**Prerequisite**: Story 5 complete and verified.

**Scope**: Instrument the main render loop with a cycle counter. Record cycles-per-frame and FPS baseline. This is the regression baseline for all Story 7 optimizations.

**Work items**:
1. Identify the main render loop (calls `jumpEraseAllSprites` + `jumpRenderMoon` + `jumpPageFlip` in sequence)
2. At loop top: read `$C073` (cycle counter low byte) or use a VBL-based frame counter
3. Alternative (simpler): use a frame counter variable — increment each iteration, run for N cycles, divide
4. Write cycles-per-frame result as 16-bit little-endian to $7000/$7001
5. Build, run benchmark, read result, compute FPS

**Acceptance criteria** (all must pass):

- [ ] `make all 2>&1 | grep -c "error:"` returns `0`
- [ ] After `run 5000000`: Maven terminal `m / 7000.7001 / b` returns non-zero 16-bit value
- [ ] Computed FPS recorded in Baseline Metrics table above and in source code comment
- [ ] Visual spot-check screenshot confirms game is actually rendering (not spinning in empty loop)

**Validation** (Maven terminal):
```
bootdisk d1 /path/to/CHOPLIFTER.po
run 5000000
m
7000.7001
b
qq
```
Record the two bytes as a 16-bit little-endian integer. Compute: `FPS = 1,021,875 / value`.

**Record in source**: Add comment in render loop: `; DHGR baseline: NNNN cycles/frame`

**Post-story action**: Record baseline FPS in Baseline Metrics table. Update "Current Story" to Story 7.

---

### Story 7: Rendering Optimizations

**Status**: NOT STARTED
**Prerequisite**: Story 6 complete and verified (baseline FPS recorded).

**Scope**: Three sequential optimizations. Each must be validated independently before proceeding to the next. Each must show FPS improvement and no visual regression.

**7a — Byte-aligned sprites** (do first):
Eliminate runtime divide-by-7 in `calcRowBitByte` + blit inner loop. Constrain all sprites to DHGR column boundaries. Sprites are pre-shifted during conversion in `tools/convert_sprites.py`.

Acceptance criteria for 7a:
- [ ] `blitImage` body (in LOCODE savebin dump) contains no JSR to `calcRowBitByte`
- [ ] FPS improves vs baseline (cycles/frame strictly less than baseline value at $7000)
- [ ] Visual screenshot matches Story 5 baseline (multimodal review, no corruption)

Verify no `calcRowBitByte` call:
```bash
# After build: savebin LOCODE segment and scan for the JSR target address
savebin /tmp/locode.bin 0800 1800
# Check that the 3-byte sequence JSR lo hi (where lo/hi = calcRowBitByte address) is absent from blitImage body
```

**7b — Eliminate redundant erase/redraw** (do second):
Sprites overwrite their previous position rather than erase-then-draw. Use double-buffer correctly so sprites are drawn fresh to the back buffer each frame without a separate erase pass.

Acceptance criteria for 7b:
- [ ] FPS improves vs post-7a value (cycles/frame strictly less)
- [ ] No ghost pixels visible in screenshot (sprites do not leave trails)
- [ ] Visual screenshot matches Story 5 baseline (multimodal review)

**7c — Hot sprite data in aux at low addresses** (do third):
Most-frequently-drawn sprites (helicopter main views, rotor) placed at lowest aux addresses ($6100+) for cache/prefetch locality. Less-used sprites (title graphics, explosions) placed at higher addresses.

Acceptance criteria for 7c:
- [ ] FPS improves vs post-7b value (cycles/frame strictly less)
- [ ] No visual regression vs Story 5 baseline (multimodal review)

**Overall Story 7 completion criteria** (all sub-tasks done):
- [ ] FPS >= 20 (cycles/frame <= 51,094) — measured at $7000/$7001 after `run 5000000`
- [ ] No visual regression vs Story 5 reference screenshot
- [ ] `calcRowBitByte` confirmed absent from `blitImage` body

**Post-story action**: Record post-optimization FPS in Baseline Metrics table. Update "Current Story" to Story 8.

---

### Story 8: Full Game Integration

**Status**: NOT STARTED
**Prerequisite**: Story 7 complete and verified.

**Scope**: Regression pass across all game screens. Final cleanup, binary rename, and release checksum.

**Work items**:
1. Run full game through: title sequence, sortie selection, active gameplay, game-over screen
2. Fix any rendering artifacts not caught in Stories 3–7
3. Verify FPS >= 20 during active gameplay (not just in isolated benchmark)
4. Rename output to `CHOPLIFTER-DHGR.po`
5. Record final binary checksum

**Acceptance criteria** (all must pass):

- [ ] `make all 2>&1 | grep -c "error:"` returns `0`
- [ ] Maven terminal `run 10000000` completes without hang or ProDOS error
- [ ] Title sequence screenshot: Choplifter logo visible, no HGR palette fringe on logo text
- [ ] Active gameplay screenshot: helicopter airborne, rotor animation visible, score HUD in correct position, no artifacts
- [ ] Game-over screen screenshot: recognizable as game-over (not garbage/black)
- [ ] All three sortie cards screenshots: First, Second, Third Sortie graphics recognizable
- [ ] Final FPS >= 20 throughout gameplay
- [ ] `CHOPLIFTER-DHGR.po` exists and md5sum recorded in commit message

**Validation — 10-second smoke test** (Maven terminal):
```
bootdisk d1 /path/to/CHOPLIFTER.po
run 10000000
showtext
qq
```
Output must not contain ProDOS error. Process must complete (not hang).

**Validation — screenshot sequence** (five screenshots):
1. Title screen (frame ~60 after boot)
2. Sortie 1 card
3. Sortie 2 card
4. Active gameplay (helicopter airborne)
5. Game-over screen

All five reviewed multimodally before accepting Story 8.

**Validation — final FPS** (Maven terminal):
```
run 5000000
m
7000.7001
b
```
Computed FPS must be >= 20.

**Release artifacts**:
```bash
mv CHOPLIFTER.po CHOPLIFTER-DHGR.po
md5sum CHOPLIFTER-DHGR.po   # record in commit message and Baseline Metrics table
git add -A
git commit -m "Story 8: DHGR conversion complete. Final FPS: XX. MD5: <hash>"
```

**Post-story action**: Record final checksum in Baseline Metrics table. Project complete.

---

## Known Risks and Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| 4bpp sprite data ~4x size expansion (~30KB) exceeds main memory slot | HIGH | Aux memory placement at $6100–$BEFF. Blit engine reads src from aux via RAMRDAUX bracket. |
| `renderMoon` uses 50+ hard-coded absolute HGR addresses | HIGH | Recalculate all addresses for DHGR nibble format in Story 3. Treat as a manual pixel-repaint task. |
| Self-modifying blit code must write both aux + main banks | HIGH | Use ZP_AUXPTR indirect write rather than second self-modified STA; or use fixed dual-STA pattern. |
| 1bpp→4bpp color mapping must be defined | HIGH | White (1) → DHGR index 15; black/transparent (0) → index 0. Tools/convert_sprites.py enforces this. |
| FPS regression: DHGR requires 2x writes + soft-switch overhead | MEDIUM | Story 6 baseline captures the actual cost. Story 7 optimizations (byte-alignment first) recover cycles. |
| Jace terminal mode has no screenshot command | MEDIUM | Visual validation uses native Jace binary + macOS `screencapture -x`. |
| Title animation hard-coded X byte positions | MEDIUM | Audit all `jumpSetAnimLoc` parameter sites in Story 8 for 80-vs-40 byte-row recalibration. |
| Game logic coupling (inadvertent side effects) | LOW | Jump table isolates all graphics entry points. Game logic files unchanged. Regression: `run 30000000` per story. |

---

## Dependency and Sequencing Notes

Stories 0–8 are strictly sequential. Each story's acceptance criteria must fully pass before the next begins. The dependency chain is:

```
S0 (clean build + reference)
  → S1 (DHGR mode, blank screen)
  → S2 (row tables + dual-bank write infrastructure)
  → S3 (background renders correctly)
  → S4 (single sprite via blitImage)
  → S5 (all sprites + full pipeline)
  → S6 (FPS baseline captured)
  → S7a → S7b → S7c (optimizations, each validated)
  → S8 (integration + release)
```

No parallelism is appropriate: each story depends on the infrastructure of all prior stories.

---

## Quick Session Startup Checklist

At the start of each session:
1. Read this file — find "Current Story" section at top
2. Read `CLAUDE.md` for architecture details
3. Run `make all` to confirm build is clean
4. Run the acceptance criteria validation commands for the current story to establish baseline before making changes
5. Make changes, build, validate acceptance criteria, git commit
6. Update "Current Story" section and "Session Notes" section in this file
7. If story complete: update "Current Story" to next story, record any metrics in Baseline Metrics table

---

*This plan is the primary working document for the DHGR conversion project. Keep it accurate. Future Claude sessions rely on it as their only source of project state.*
