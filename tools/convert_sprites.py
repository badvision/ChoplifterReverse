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
CHOPMAIN_SIZE_PATH   = 'chopmain_size.txt'
INC_PATH             = 'choplifter_sprites.inc'
PREVIEW_DIR          = 'tools/sprite_preview'

CHOPAUX_FLIP_PATH       = 'CHOPAXFLIP'
CHOPMAIN_FLIP_PATH      = 'CHOPMXFLIP'
CHOPAUX_FLIP_SIZE_PATH  = 'chopaux_flip_size.txt'
CHOPMAIN_FLIP_SIZE_PATH = 'chopmain_flip_size.txt'

CHOPGFX_VIRTUAL_BASE = 0xA102
DHGR_HEADER_BASE     = 0xAB1C   # .org for header block in main memory
AUX_DATA_BASE        = 0x6100   # CHOPAUX loads here in aux memory
MAIN_DATA_BASE       = 0xD070   # CHOPMAIN loaded to LC RAM $D070 — avoids overlap with pass1RowPassFlip ($D030-$D068, 57 bytes)
AUX_FLIP_BASE        = 0x75DB   # CHOPAUX_FLIP: AUX $6100 + $14DB = $75DB
MAIN_FLIP_BASE       = 0xE54B   # CHOPMAIN_FLIP: LC $D070 + $14DB = $E54B

# chopperHeadOnDHGR0 was originally HGR sprite at $A41B (Story 4 replaced the
# chopperHeadOnSpriteTable[0] entry with the label).
CHOPPERHEADON_HGR_ADDR = 0xA41B

# Line range in choplifter.s that contains all sprite pointer tables
# chopperSideSpriteTable starts at line 12027, sortieGraphicsTable ends at 12241.
TABLE_START_LINE = 12027
TABLE_END_LINE   = 12246   # exclusive upper bound (inclusive: 12245)


# ----------------------------------------------------------- per-sprite colors

# Sprite index -> DHGR color index (0 = white/default pixel-doubled)
# Tank body, treads, and cannon sprites rendered in medium green (color 12)
SPRITE_COLORS = {
    50: 12,  # Tank turret (body)
    51: 12,  # Tank tread (frame 1)
    52: 12,  # Tank tread (frame 2)
    53: 12,  # Tank cannon, facing full right
    54: 12,  # Tank cannon, facing up and right
    55: 12,  # Tank cannon, facing up
    56: 12,  # Tank cannon, facing up and left
    57: 12,  # Tank cannon, facing full left
}

# [AUX_even, MAIN_even, AUX_odd, MAIN_odd] for each DHGR color index
DHGR_COLOR_BYTES = {
    0:  (0x7F, 0x7F, 0x7F, 0x7F),  # white (default pixel-doubled)
    4:  (0x22, 0x44, 0x08, 0x11),  # DarkGreen
    12: (0x66, 0x4C, 0x19, 0x33),  # Green (medium green)
}


def get_color_bytes(color_idx, col_parity):
    """Return (aux_byte, main_byte) for a given color and column parity.

    col_parity: 0 = even screen column, 1 = odd screen column.
    """
    tbl = DHGR_COLOR_BYTES[color_idx]
    if col_parity == 0:
        return tbl[0], tbl[1]
    else:
        return tbl[2], tbl[3]


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

def hgr_to_dhgr_doubled(b):
    """
    Convert one HGR byte to (AUX, MAIN) via proper 2x pixel doubling.

    Each HGR pixel at bit position i (bit 0 = leftmost) becomes 2 adjacent
    DHGR pixels at positions 2i and 2i+1 within the 14-pixel column group:
      AUX covers positions 0-6:  b0,b0,b1,b1,b2,b2,b3
      MAIN covers positions 7-13: b3,b4,b4,b5,b5,b6,b6

    No bit reversal: HGR bit 0 = leftmost = DHGR bit 0 = leftmost.
    """
    b &= 0x7F
    b0 = (b >> 0) & 1
    b1 = (b >> 1) & 1
    b2 = (b >> 2) & 1
    b3 = (b >> 3) & 1
    b4 = (b >> 4) & 1
    b5 = (b >> 5) & 1
    b6 = (b >> 6) & 1
    aux  = b0 | (b0<<1) | (b1<<2) | (b1<<3) | (b2<<4) | (b2<<5) | (b3<<6)
    main = b3 | (b4<<1) | (b4<<2) | (b5<<3) | (b5<<4) | (b6<<5) | (b6<<6)
    return aux, main


def reverse_bits7(b):
    """Reverse the 7 payload bits: bit 0 becomes bit 6, bit 1 becomes bit 5, etc."""
    b &= 0x7F
    result = 0
    for i in range(7):
        if b & (1 << i):
            result |= 1 << (6 - i)
    return result


def hgr_row_to_dhgr(row_bytes, color=0, col_offset=0):
    """
    Convert one HGR row to (aux_bytes, main_bytes) for DHGR 2x pixel doubling.

    CHOPGFX convention: byte 0 is the LEFTMOST byte; bit 6 is the LEFTMOST pixel
    within each byte (bit 0 is the rightmost pixel within each byte).
    hgr_to_dhgr_doubled() expects bit 0 = leftmost, so we reverse bits within
    each byte before passing to it. Byte order is unchanged (left to right).

    When color != 0: AND the pixel-doubled shape bits with the color phase mask.
    This preserves per-pixel shape detail while encoding the DHGR color phase.
    A solid color mask would lose all shape information (every non-zero byte
    would become a full 7-pixel-wide solid block).
    """
    aux  = bytearray()
    main = bytearray()
    for col_i, b in enumerate(row_bytes):
        rb = reverse_bits7(b)
        a_shape, m_shape = hgr_to_dhgr_doubled(rb)
        if color != 0:
            parity = (col_offset + col_i) % 2
            aux_mask, main_mask = get_color_bytes(color, parity)
            a = a_shape & aux_mask
            m = m_shape & main_mask
        else:
            a = a_shape
            m = m_shape
        aux.append(a)
        main.append(m)
    return bytes(aux), bytes(main)


def convert_all(chopgfx, addresses, head_on_idx):
    """
    Convert all sprites.  Returns:
      headers   -- list of (w_cols, h, aux_ptr, main_ptr, hgr_addr, aux_rows_bytes)
      aux_data  -- bytearray of all DHGR aux pixel data concatenated
      main_data -- bytearray of all DHGR main pixel data concatenated
    """
    aux_data  = bytearray()
    main_data = bytearray()
    headers   = []

    for sprite_idx, addr in enumerate(addresses):
        color = SPRITE_COLORS.get(sprite_idx, 0)
        w_cols, h, pixel_bytes = read_hgr_sprite(chopgfx, addr)
        # w_cols = W_hgr = W_dhgr: width unchanged, each HGR byte -> one AUX+MAIN pair
        aux_rows  = bytearray()
        main_rows = bytearray()
        for row in range(h):
            row_start = row * w_cols
            row_end   = row_start + w_cols
            a, m = hgr_row_to_dhgr(pixel_bytes[row_start:row_end], color=color, col_offset=0)
            aux_rows.extend(a)
            main_rows.extend(m)

        aux_offset  = len(aux_data)
        main_offset = len(main_data)
        aux_data.extend(aux_rows)
        main_data.extend(main_rows)
        aux_ptr  = AUX_DATA_BASE  + aux_offset
        main_ptr = MAIN_DATA_BASE + main_offset
        headers.append((w_cols, h, aux_ptr, main_ptr, addr, bytes(aux_rows)))

    return headers, aux_data, main_data


def compute_flip_data(headers, aux_data, main_data):
    """
    Generate CHOPAUX_FLIP and CHOPMAIN_FLIP for blitImageFlip.

    For a white/default sprite with W columns per row:
        flip_aux[row][col_i]  = reverse_bits7(main_data[row][W-1-col_i])
        flip_main[row][col_i] = reverse_bits7(aux_data[row][W-1-col_i])

    This is the correct DHGR horizontal mirror because:
    - AUX screen col i shows leftward 7 pixels of that column group
    - MAIN screen col i shows rightward 7 pixels of that column group
    - True mirror: pixel at position P maps to mirror position W*14-1-P
    - Result: flip_aux[i] must contain reversed MAIN data from the opposite column

    For colored sprites (color != 0): instead of bit-reversal, the destination
    column parity determines which color bytes to use (same as forward data).
    A source column is "on" if either its aux or main byte is non-zero.

    Returns (aux_flip_data, main_flip_data) as bytes.
    """
    aux_flip  = bytearray()
    main_flip = bytearray()

    aux_offset  = 0
    main_offset = 0

    for sprite_idx, (w, h, _aux_ptr, _main_ptr, _hgr_addr, _pixels) in enumerate(headers):
        color = SPRITE_COLORS.get(sprite_idx, 0)
        for row in range(h):
            row_aux  = aux_data [aux_offset  + row * w : aux_offset  + row * w + w]
            row_main = main_data[main_offset + row * w : main_offset + row * w + w]
            for col in range(w):
                src_col = w - 1 - col
                # Compute shape bits for flip: same AUX/MAIN swap + bit-reversal as
                # white sprites.  For colored sprites, AND the shape bits with the
                # destination column's color phase mask (preserves pixel shape while
                # encoding the color, matching what hgr_row_to_dhgr does for forward data).
                a_shape = reverse_bits7(row_main[src_col])
                m_shape = reverse_bits7(row_aux [src_col])
                if color != 0:
                    parity = col % 2
                    aux_mask, main_mask = get_color_bytes(color, parity)
                    aux_flip .append(a_shape & aux_mask)
                    main_flip.append(m_shape & main_mask)
                else:
                    aux_flip .append(a_shape)
                    main_flip.append(m_shape)
        aux_offset  += w * h
        main_offset += w * h

    return bytes(aux_flip), bytes(main_flip)


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

    # CHOPAUX / CHOPMAIN total size: w_dhgr bytes per row per sprite
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
        assert 0xD070 <= main_ptr < 0xF000, (
            f'Sprite {i}: main_ptr=${main_ptr:04X} out of range (LC RAM $D070-$EFFF)'
        )

    # chopperHeadOnDHGR0 comes from $A41B (W=12px -> W_cols=2, H=13)
    w_ho, h_ho, _aux, _main, addr_ho, _pix = headers[head_on_idx]
    assert addr_ho == CHOPPERHEADON_HGR_ADDR, (
        f'head_on_idx {head_on_idx}: expected addr=${CHOPPERHEADON_HGR_ADDR:04X}, '
        f'got ${addr_ho:04X}'
    )
    assert w_ho == 2, f'chopperHeadOnDHGR0 W expected 2 (W_hgr, Option B doubled), got {w_ho}'
    assert h_ho == 13, f'chopperHeadOnDHGR0 H expected 13, got {h_ho}'

    print(f'Validation passed:')
    print(f'  {n} sprites')
    print(f'  CHOPAUX: {len(aux_data)} bytes (${len(aux_data):04X})')
    print(f'  CHOPMAIN: {len(main_data)} bytes (${len(main_data):04X})')
    print(f'  chopperHeadOnDHGR0 at index {head_on_idx}, '
          f'W={w_ho}, H={h_ho}, aux_ptr=${headers[head_on_idx][2]:04X}')


# ----------------------------------------------------------------------- main

def verify_doubling_math():
    """
    Sanity-check hgr_to_dhgr_doubled() and reverse_bits7() against known
    test vectors before writing any files.  Raises AssertionError on mismatch.
    """
    # $7F = all 7 bits on -> all 14 DHGR pixels white
    a, m = hgr_to_dhgr_doubled(0x7F)
    assert a == 0x7F and m == 0x7F, \
        f'$7F: expected AUX=$7F MAIN=$7F, got AUX=${a:02X} MAIN=${m:02X}'

    # $00 = all black
    a, m = hgr_to_dhgr_doubled(0x00)
    assert a == 0x00 and m == 0x00, \
        f'$00: expected AUX=$00 MAIN=$00, got AUX=${a:02X} MAIN=${m:02X}'

    # $01 = only bit 0 (leftmost pixel) on -> AUX bits 0,1 set = $03, MAIN = $00
    a, m = hgr_to_dhgr_doubled(0x01)
    assert a == 0x03 and m == 0x00, \
        f'$01: expected AUX=$03 MAIN=$00, got AUX=${a:02X} MAIN=${m:02X}'

    # $40 = only bit 6 (rightmost pixel) on -> AUX=$00, MAIN bits 5,6 set = $60
    a, m = hgr_to_dhgr_doubled(0x40)
    assert a == 0x00 and m == 0x60, \
        f'$40: expected AUX=$00 MAIN=$60, got AUX=${a:02X} MAIN=${m:02X}'

    # reverse_bits7 sanity checks
    assert reverse_bits7(0x01) == 0x40, \
        f'reverse_bits7($01): expected $40, got ${reverse_bits7(0x01):02X}'
    assert reverse_bits7(0x40) == 0x01, \
        f'reverse_bits7($40): expected $01, got ${reverse_bits7(0x40):02X}'
    assert reverse_bits7(0x7F) == 0x7F, \
        f'reverse_bits7($7F): expected $7F, got ${reverse_bits7(0x7F):02X}'
    assert reverse_bits7(0x00) == 0x00, \
        f'reverse_bits7($00): expected $00, got ${reverse_bits7(0x00):02X}'
    assert reverse_bits7(0x02) == 0x20, \
        f'reverse_bits7($02): expected $20, got ${reverse_bits7(0x02):02X}'

    # hgr_row_to_dhgr convention check:
    # CHOPGFX: byte 0 = leftmost, bit 6 = leftmost pixel in byte
    # Leftmost pixel = bit 6 of byte 0 = 0x40 -> after reverse_bits7 = 0x01
    # -> hgr_to_dhgr_doubled(0x01) -> aux=0x03 (bits 0,1 = leftmost DHGR pixels)
    aux_row, main_row = hgr_row_to_dhgr(bytes([0x40, 0x00]))
    assert aux_row[0] == 0x03 and main_row[0] == 0x00, \
        f'hgr_row_to_dhgr([0x40,0x00]): leftmost pixel should be aux[0]=$03, ' \
        f'got aux[0]=${aux_row[0]:02X} main[0]=${main_row[0]:02X}'
    # Rightmost pixel = bit 0 of byte W-1 = bit 0 of byte 1 = 0x01 -> reverse_bits7 = 0x40
    # -> hgr_to_dhgr_doubled(0x40) -> main=0x60 (bits 5,6 = rightmost DHGR pixels)
    aux_row2, main_row2 = hgr_row_to_dhgr(bytes([0x00, 0x01]))
    assert main_row2[1] == 0x60 and aux_row2[1] == 0x00, \
        f'hgr_row_to_dhgr([0x00,0x01]): rightmost pixel should be main[1]=$60, ' \
        f'got aux[1]=${aux_row2[1]:02X} main[1]=${main_row2[1]:02X}'

    print('Pixel-doubling math verified: $7F/$00/$01/$40 all correct.')
    print('reverse_bits7 verified: $01/$40/$7F/$00/$02 all correct.')
    print('hgr_row_to_dhgr convention verified: leftmost=aux[0]=$03, rightmost=main[-1]=$60.')


def main():
    # Verify doubling math before writing any files
    verify_doubling_math()

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

    # Write chopmain_size.txt
    with open(CHOPMAIN_SIZE_PATH, 'w') as f:
        f.write(str(len(main_data)) + '\n')
    print(f'Wrote {CHOPMAIN_SIZE_PATH}: {len(main_data)}')

    # Generate and write flip data
    aux_flip_data, main_flip_data = compute_flip_data(headers, aux_data, main_data)

    with open(CHOPAUX_FLIP_PATH, 'wb') as f:
        f.write(aux_flip_data)
    print(f'Wrote {CHOPAUX_FLIP_PATH}: {len(aux_flip_data)} bytes (${len(aux_flip_data):04X})')

    with open(CHOPMAIN_FLIP_PATH, 'wb') as f:
        f.write(main_flip_data)
    print(f'Wrote {CHOPMAIN_FLIP_PATH}: {len(main_flip_data)} bytes (${len(main_flip_data):04X})')

    with open(CHOPAUX_FLIP_SIZE_PATH, 'w') as f:
        f.write(str(len(aux_flip_data)) + '\n')
    print(f'Wrote {CHOPAUX_FLIP_SIZE_PATH}: {len(aux_flip_data)}')

    with open(CHOPMAIN_FLIP_SIZE_PATH, 'w') as f:
        f.write(str(len(main_flip_data)) + '\n')
    print(f'Wrote {CHOPMAIN_FLIP_SIZE_PATH}: {len(main_flip_data)}')

    assert len(aux_flip_data) == len(aux_data), \
        f'CHOPAUX_FLIP size mismatch: {len(aux_flip_data)} vs {len(aux_data)}'
    assert len(main_flip_data) == len(main_data), \
        f'CHOPMAIN_FLIP size mismatch: {len(main_flip_data)} vs {len(main_data)}'

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
