#!/usr/bin/env python3
"""
Choplifter DHGR Sprite Conversion Tool
Story 5: Converts all 128 HGR sprites to DHGR aux-bank format.

Outputs:
  CHOPAUX             -- raw aux pixel data for all sprites, concatenated
  chopaux_size.txt    -- byte count of CHOPAUX (one line, decimal)
  choplifter_sprites.inc  -- .org $AB1C block with headers + equates
  tools/sprite_preview/sprite_NNN.png  -- grayscale preview per sprite

Usage: python3 tools/convert_sprites.py
Run from project root: cd ~/Documents/code/ChoplifterReverse
"""

import re
import os
import sys


# ------------------------------------------------------------------ constants

CHOPGFX_PATH         = 'CHOPGFX'
ASM_PATH             = 'choplifter.s'
CHOPAUX_PATH         = 'CHOPAUX'
CHOPMAIN_PATH        = 'CHOPMAIN'
CHOPAUX_SIZE_PATH    = 'chopaux_size.txt'
INC_PATH             = 'choplifter_sprites.inc'
PREVIEW_DIR          = 'tools/sprite_preview'

CHOPGFX_VIRTUAL_BASE = 0xA102
DHGR_HEADER_BASE     = 0xAB1C   # .org for header block in main memory
AUX_DATA_BASE        = 0x6100   # CHOPAUX loads here in aux memory
MAIN_DATA_BASE       = 0xD060   # CHOPMAIN loaded to LC RAM $D060 — avoids overlap with pass1RowPassFlip ($D030-$D056)

# chopperHeadOnDHGR0 was originally HGR sprite at $A41B (Story 4 replaced the
# chopperHeadOnSpriteTable[0] entry with the label).
CHOPPERHEADON_HGR_ADDR = 0xA41B

# Line range in choplifter.s that contains all sprite pointer tables
# chopperSideSpriteTable starts at line 12027, sortieGraphicsTable ends at 12241.
TABLE_START_LINE = 12027
TABLE_END_LINE   = 12246   # exclusive upper bound (inclusive: 12245)


# -------------------------------------------------------------- sprite parsing

def parse_sprite_addresses(asm_path):
    """
    Scrape all .word $Axxx / .word $Bxxx entries from sprite tables
    in choplifter.s lines TABLE_START_LINE..TABLE_END_LINE.
    Returns (addresses, head_on_index) where addresses[head_on_index]
    is the HGR original for chopperHeadOnDHGR0.

    If the pointer tables have already been updated to dhgrSpriteAddr_NNN form
    (Story 5+), falls back to reading HGR addresses from choplifter_sprites.inc
    'was $XXXX' comments, which are the authoritative source.
    """
    with open(asm_path, 'r') as f:
        lines = f.readlines()

    table_lines = lines[TABLE_START_LINE - 1 : TABLE_END_LINE - 1]

    addresses   = []
    head_on_idx = None

    for line in table_lines:
        stripped = line.strip()
        if stripped.startswith(';'):
            continue
        # Match  .word $AxXX  or  .word $BxXX  or  .word chopperHeadOnDHGR0
        matches = re.findall(
            r'\.word\s+(\$[aAbB][0-9a-fA-F]+|chopperHeadOnDHGR0)',
            line
        )
        for m in matches:
            if m == 'chopperHeadOnDHGR0':
                head_on_idx = len(addresses)
                addresses.append(CHOPPERHEADON_HGR_ADDR)
            else:
                addresses.append(int(m[1:], 16))

    # Story 5+: pointer tables use dhgrSpriteAddr_NNN — fall back to inc file
    if not addresses and os.path.exists(INC_PATH):
        addresses, head_on_idx = parse_addresses_from_inc(INC_PATH)

    return addresses, head_on_idx


def parse_addresses_from_inc(inc_path):
    """
    Read HGR sprite addresses from 'was $XXXX' comments in choplifter_sprites.inc.
    Returns (addresses, head_on_index) in sprite order (000..127).
    chopperHeadOnDHGR0 is at index 11 (the dhgrSprite_011 entry).
    """
    addresses   = []
    head_on_idx = None
    with open(inc_path, 'r') as f:
        lines = f.readlines()
    sprite_idx  = None
    for line in lines:
        m = re.match(r'^dhgrSprite_(\d+):', line.strip())
        if m:
            sprite_idx = int(m.group(1))
            # chopperHeadOnDHGR0 is defined just before dhgrSprite_011
            if sprite_idx == 11:
                head_on_idx = len(addresses)
        else:
            m2 = re.search(r'was \$([0-9A-Fa-f]+)', line)
            if m2 and sprite_idx is not None:
                addresses.append(int(m2.group(1), 16))
                sprite_idx = None
    return addresses, head_on_idx


def hgr_sprite_bpr(w_pixels):
    """
    Return bytes-per-row for an HGR sprite whose header byte[0] = w_pixels.
    Formula from applyClipping in choplifter.s:
        ZP_IMAGE_W_BYTES = (ZP_IMAGE_W + 7) >> 3
    which is ceil(w_pixels / 8).
    """
    return (w_pixels + 7) >> 3


def read_hgr_sprite(chopgfx, addr):
    """
    Parse HGR sprite at virtual address addr from chopgfx bytes.
    Returns (w_cols, h, pixel_bytes) where:
      w_cols = bytes per row (= DHGR columns)
      h      = height in rows
      pixel_bytes = w_cols * h HGR bytes (bit 7 may be set)
    If pixel data extends beyond the CHOPGFX file, the returned bytes are
    zero-padded to the expected size (last sortie card is truncated in source).
    """
    offset   = addr - CHOPGFX_VIRTUAL_BASE
    w_pixels = chopgfx[offset]
    h        = chopgfx[offset + 1]
    w_cols   = hgr_sprite_bpr(w_pixels)
    size     = w_cols * h
    raw = chopgfx[offset + 2 : offset + 2 + size]
    if len(raw) < size:
        # Pad with zeros for truncated data
        raw = raw + bytes(size - len(raw))
    return w_cols, h, raw


# ----------------------------------------------------------------- conversion

def convert_all(chopgfx, addresses, head_on_idx):
    """
    Convert all sprites.  Returns:
      headers   -- list of (w_cols, h, aux_ptr, main_ptr, hgr_addr, pixel_bytes)
      aux_data  -- bytearray of all DHGR aux pixel data concatenated
      main_data -- bytearray of all DHGR main pixel data concatenated (same bytes as aux)
    """
    aux_data  = bytearray()
    main_data = bytearray()
    headers   = []

    for addr in addresses:
        w_cols, h, pixel_bytes = read_hgr_sprite(chopgfx, addr)
        dhgr_pixels = bytes(b & 0x7F for b in pixel_bytes)
        aux_offset  = len(aux_data)
        main_offset = len(main_data)
        aux_data.extend(dhgr_pixels)
        main_data.extend(dhgr_pixels)
        aux_ptr  = AUX_DATA_BASE  + aux_offset
        main_ptr = MAIN_DATA_BASE + main_offset
        headers.append((w_cols, h, aux_ptr, main_ptr, addr, dhgr_pixels))

    return headers, aux_data, main_data


# ----------------------------------------------------------------- inc output

def emit_inc(headers, head_on_idx, inc_path):
    n = len(headers)
    lines = []
    lines.append('; generated by tools/convert_sprites.py -- do not edit manually')
    lines.append('; Story 8: DHGR sprite headers (6 bytes each) + address equates')
    lines.append('; Header layout: W, H, aux_ptr_lo, aux_ptr_hi, main_ptr_lo, main_ptr_hi')
    lines.append('; AUX pixel data: CHOPAUX loaded to $6100 in AUX memory.')
    lines.append(f'; MAIN pixel data: CHOPMAIN loaded to ${MAIN_DATA_BASE:04X} in LC RAM.')
    lines.append('')
    lines.append('; DHGR sprite header block -- placed at $AB1C')
    lines.append(f'; Use .res (not .org) to emit fill bytes and ensure correct placement.')
    lines.append(f'; .org in a relocatable ca65 segment only sets the virtual PC (listing appears')
    lines.append(f'; correct) but does not insert fill bytes unless fill=yes is in linkerConfig.')
    lines.append(f'; .res emits actual zero bytes, guaranteeing placement at ${DHGR_HEADER_BASE:04X}.')
    lines.append(f'.res ${DHGR_HEADER_BASE:04X} - *, $00')
    lines.append('')

    for i, (w, h, aux_ptr, main_ptr, hgr_addr, pixels) in enumerate(headers):
        aux_lo  = aux_ptr  & 0xFF
        aux_hi  = (aux_ptr  >> 8) & 0xFF
        main_lo = main_ptr & 0xFF
        main_hi = (main_ptr >> 8) & 0xFF
        comment = f'; was ${hgr_addr:04X}'
        label_main = f'dhgrSprite_{i:03d}:'

        if i == head_on_idx:
            # Special label required by choplifter.s
            lines.append(f'chopperHeadOnDHGR0:')
        lines.append(f'{label_main}')
        lines.append(
            f'    .byte {w}, {h}, ${aux_lo:02X}, ${aux_hi:02X}, ${main_lo:02X}, ${main_hi:02X}'
            f'   {comment}  aux=${aux_ptr:04X} main=${main_ptr:04X}'
        )

    lines.append('')
    lines.append('; Address equates for pointer table (6 bytes per header):')
    for i in range(n):
        lines.append(f'dhgrSpriteAddr_{i:03d} = ${DHGR_HEADER_BASE:04X} + {i} * 6')

    lines.append('')
    with open(inc_path, 'w') as f:
        f.write('\n'.join(lines) + '\n')


# -------------------------------------------------------------- PNG previews

def emit_previews(headers, chopgfx, addresses, preview_dir):
    os.makedirs(preview_dir, exist_ok=True)
    SCALE = 4   # enlarge each pixel cell for visibility

    try:
        from PIL import Image
        use_pil = True
    except ImportError:
        use_pil = False

    for i, (w_cols, h, aux_ptr, main_ptr, hgr_addr, dhgr_pixels) in enumerate(headers):

        # Build grayscale image: each byte maps to a column, each bit renders
        # the per-column brightness.  For simplicity render each byte as a
        # uniform gray value (normalised to 0-255).
        img_w = w_cols * SCALE
        img_h = h      * SCALE

        if use_pil:
            img = Image.new('L', (img_w, img_h), 0)
            px  = img.load()
            for row in range(h):
                for col in range(w_cols):
                    byte_idx = row * w_cols + col
                    if byte_idx < len(dhgr_pixels):
                        raw = dhgr_pixels[byte_idx] & 0x7F
                        # Scale 7-bit value to 8-bit grey
                        grey = (raw * 255) // 127
                    else:
                        grey = 0
                    for dy in range(SCALE):
                        for dx in range(SCALE):
                            px[col * SCALE + dx, row * SCALE + dy] = grey
            out_path = os.path.join(preview_dir, f'sprite_{i:03d}.png')
            img.save(out_path)
        else:
            # Fallback: PPM (portable pixmap, no library needed)
            out_path = os.path.join(preview_dir, f'sprite_{i:03d}.ppm')
            with open(out_path, 'wb') as f:
                header_bytes = f'P5\n{img_w} {img_h}\n255\n'.encode()
                f.write(header_bytes)
                for row in range(h):
                    for _ in range(SCALE):
                        for col in range(w_cols):
                            byte_idx = row * w_cols + col
                            if byte_idx < len(dhgr_pixels):
                                raw = dhgr_pixels[byte_idx] & 0x7F
                                grey = (raw * 255) // 127
                            else:
                                grey = 0
                            f.write(bytes([grey] * SCALE))


# ----------------------------------------------------------------- validation

def validate(headers, aux_data, main_data, head_on_idx):
    n = len(headers)

    # Sprite count: 128 total (127 explicit hex addresses + chopperHeadOnDHGR0 label)
    assert n == 128, f'Expected 128 sprites, got {n}'

    # CHOPAUX total size
    total_px = sum(w * h for w, h, *_ in headers)
    assert len(aux_data) == total_px, (
        f'CHOPAUX size mismatch: {len(aux_data)} bytes vs expected {total_px}'
    )
    assert len(main_data) == total_px, (
        f'CHOPMAIN size mismatch: {len(main_data)} bytes vs expected {total_px}'
    )
    assert len(aux_data) == len(main_data), (
        f'CHOPAUX/CHOPMAIN size mismatch: {len(aux_data)} vs {len(main_data)}'
    )

    # All aux ptrs within aux memory window
    for i, (w, h, aux_ptr, main_ptr, _hgr_addr, _pixels) in enumerate(headers):
        assert 0x6100 <= aux_ptr < 0xBF00, (
            f'Sprite {i}: aux_ptr=${aux_ptr:04X} out of range'
        )
        assert 0xD060 <= main_ptr < 0xF000, (
            f'Sprite {i}: main_ptr=${main_ptr:04X} out of range (LC RAM $D060-$EFFF)'
        )

    # chopperHeadOnDHGR0 comes from $A41B (W=12px -> W_cols=2, H=13)
    w_ho, h_ho, _aux, _main, addr_ho, _pix = headers[head_on_idx]
    assert addr_ho == CHOPPERHEADON_HGR_ADDR, (
        f'head_on_idx {head_on_idx}: expected addr=${CHOPPERHEADON_HGR_ADDR:04X}, '
        f'got ${addr_ho:04X}'
    )
    assert w_ho == 2, f'chopperHeadOnDHGR0 W_cols expected 2, got {w_ho}'
    assert h_ho == 13, f'chopperHeadOnDHGR0 H expected 13, got {h_ho}'

    print(f'Validation passed:')
    print(f'  {n} sprites')
    print(f'  CHOPAUX: {len(aux_data)} bytes (${len(aux_data):04X})')
    print(f'  CHOPMAIN: {len(main_data)} bytes (${len(main_data):04X})')
    print(f'  chopperHeadOnDHGR0 at index {head_on_idx}, '
          f'W={w_ho}, H={h_ho}, aux_ptr=${headers[head_on_idx][2]:04X}')


# ----------------------------------------------------------------------- main

def main():
    # Load CHOPGFX
    with open(CHOPGFX_PATH, 'rb') as f:
        chopgfx = f.read()

    # Parse sprite addresses from choplifter.s
    addresses, head_on_idx = parse_sprite_addresses(ASM_PATH)
    print(f'Parsed {len(addresses)} sprite addresses from {ASM_PATH}')
    print(f'chopperHeadOnDHGR0 at index {head_on_idx} (HGR addr=${addresses[head_on_idx]:04X})')

    # Convert sprites
    headers, aux_data, main_data = convert_all(chopgfx, addresses, head_on_idx)

    # Write CHOPAUX
    with open(CHOPAUX_PATH, 'wb') as f:
        f.write(aux_data)
    print(f'Wrote {CHOPAUX_PATH}: {len(aux_data)} bytes (${len(aux_data):04X})')

    # Write CHOPMAIN
    with open(CHOPMAIN_PATH, 'wb') as f:
        f.write(main_data)
    print(f'Wrote {CHOPMAIN_PATH}: {len(main_data)} bytes (${len(main_data):04X})')

    # Write chopaux_size.txt
    with open(CHOPAUX_SIZE_PATH, 'w') as f:
        f.write(str(len(aux_data)) + '\n')
    print(f'Wrote {CHOPAUX_SIZE_PATH}: {len(aux_data)}')

    # Write choplifter_sprites.inc
    emit_inc(headers, head_on_idx, INC_PATH)
    print(f'Wrote {INC_PATH}')

    # Write PNG (or PPM fallback) previews
    try:
        from PIL import Image as _PIL_Image
        preview_ext = 'png'
        del _PIL_Image
    except ImportError:
        preview_ext = 'ppm'
    emit_previews(headers, chopgfx, addresses, PREVIEW_DIR)
    print(f'Wrote {len(headers)} sprite previews to {PREVIEW_DIR}/ (.{preview_ext})')

    # Validate
    validate(headers, aux_data, main_data, head_on_idx)

    return 0


if __name__ == '__main__':
    sys.exit(main())
