;
;  loader
;  A very simplistic code loader for my reverse-engineered Choplifter
;
;  Created by Quinn Dunki on May 5, 2024
;

.segment "STARTUP"

MAINENTRY =		$2000		; Mandated by ProDOS for SYSTEM programs
LOADBUFFER =	$4000		; Use HGR2 as a loading buffer
PRODOS = 		$bf00		; MLI entry point

.org $2000

main:
	; Open the low code file
	jsr PRODOS
	.byte $c8
	.addr fileOpenCode0
	beq :+
	brk
:

	; Load low code at $800
	jsr PRODOS
	.byte $ca
	.addr fileRead0
	beq :+
	brk
:

	; Close the file
	jsr PRODOS
	.byte $cc
	.addr fileClose

	; Open the high code file
	jsr PRODOS
	.byte $c8
	.addr fileOpenCode1
	beq :+
	brk
:

	; Load high code at $6000
	jsr PRODOS
	.byte $ca
	.addr fileRead1
	beq :+
	brk
:

	; Close the file
	jsr PRODOS
	.byte $cc
	.addr fileClose

	; Story 3: CHOPGFX and CHOPGFXHI loads are skipped.
	; The DHGR rendering subsystem (CHOP1) now extends past $A102 and CHOPGFX would
	; clobber rendering code at $A102+. Story 3 uses only blitAlignedImage stubs —
	; no sprite pixel data is accessed. CHOPGFX will be restored/relocated in Story 4+.

	; ---- Story 5: Load CHOPAUX to aux memory ($6100) ----
	; Step 1: Open CHOPAUX file
	jsr PRODOS
	.byte $c8
	.addr fileOpenAux
	beq :+
	brk
:

	; Step 2: Read CHOPAUX into main $4400 (above 1KB OPEN I/O buffer at $4000-$43FF)
	jsr PRODOS
	.byte $ca
	.addr fileReadAux
	beq :+
	brk
:

	; Step 3: Close file
	jsr PRODOS
	.byte $cc
	.addr fileClose

	; Step 4: Copy from main $4400 to aux $6100 via RAMWRAUX
	; Source pointer in ZP $90/$91, dest pointer in ZP $92/$93 (scratch -- safe during init)
	lda #$00
	sta $90					; source lo = $00
	lda #$44
	sta $91					; source hi = $44  => source = $4400 (CHOPAUX read buffer)
	lda #$00
	sta $92					; dest lo = $00
	lda #$61
	sta $93					; dest hi = $61  => dest = $6100

	; Copy chopAuxLen bytes page-by-page (256 bytes per iteration)
	; chopAuxLen is a page-count (hi byte) + remainder (lo byte)
	; We copy >chopAuxLen pages then handle the partial final page
	ldx #>chopAuxLen		; X = number of full pages

	sei
	sta $C005				; RAMWRAUX — writes go to aux memory

chopAuxCopyPageLoop:
	ldy #0
chopAuxCopyByteLoop:
	lda ($90),y				; read from main $4000+offset
	sta ($92),y				; write to aux $6100+offset
	iny
	bne chopAuxCopyByteLoop	; loop 256 bytes

	; Advance source and dest pointers by one page
	inc $91
	inc $93
	dex
	bne chopAuxCopyPageLoop

	; Copy remaining partial page (<chopAuxLen lo bytes)
	ldy #0
	ldx #<chopAuxLen
	beq chopAuxCopyDone		; if remainder is 0, skip

chopAuxCopyRemLoop:
	lda ($90),y
	sta ($92),y
	iny
	dex
	bne chopAuxCopyRemLoop

chopAuxCopyDone:
	sta $C004				; RAMWRMAIN — restore writes to main
	cli

	; ---- Story 10: Load CHOPAUX_FLIP to aux memory ($75DB) ----
	; Load while still in the ProDOS I/O window. RAMWRAUX copy does not touch LC Bank 2.
	; Step 1: Open CHOPAUX_FLIP file
	jsr PRODOS
	.byte $c8
	.addr fileOpenAuxFlip
	beq :+
	brk
:

	; Step 2: Read CHOPAUX_FLIP into main $4400 staging buffer ($4400 is free: CHOPAUX copied)
	jsr PRODOS
	.byte $ca
	.addr fileReadAuxFlip
	beq :+
	brk
:

	; Step 3: Close file
	jsr PRODOS
	.byte $cc
	.addr fileClose

	; Step 4: Copy from main $4400 to aux $75DB via RAMWRAUX (safe — does not affect LC Bank 2)
	lda #$DB
	sta $92					; dest lo = $DB
	lda #$75
	sta $93					; dest hi = $75 => dest = $75DB
	lda #$00
	sta $90					; source lo = $00
	lda #$44
	sta $91					; source hi = $44 => source = $4400

	ldx #>chopAuxFlipLen	; X = number of full pages

	sei
	sta $C005				; RAMWRAUX — writes go to aux memory

@chopAuxFlipCopyPageLoop:
	ldy #0
@chopAuxFlipCopyByteLoop:
	lda ($90),y
	sta ($92),y
	iny
	bne @chopAuxFlipCopyByteLoop

	inc $91
	inc $93
	dex
	bne @chopAuxFlipCopyPageLoop

	ldy #0
	ldx #<chopAuxFlipLen
	beq @chopAuxFlipCopyDone

@chopAuxFlipCopyRemLoop:
	lda ($90),y
	sta ($92),y
	iny
	dex
	bne @chopAuxFlipCopyRemLoop

@chopAuxFlipCopyDone:
	sta $C004				; RAMWRMAIN — restore writes to main
	cli

	; ---- Story 10: Load CHOPMAIN_FLIP to $4400 staging buffer ----
	; $4400 is free: CHOPAUX and CHOPAXFLIP have been copied to AUX already.
	; Read to $4400 (LOADBUFFER=$4000 I/O buffer does not overlap $4400 destination).
	jsr PRODOS
	.byte $c8
	.addr fileOpenMainFlip
	beq :+
	brk
:

	jsr PRODOS
	.byte $ca
	.addr fileReadMainFlip
	beq :+
	brk
:

	jsr PRODOS
	.byte $cc
	.addr fileClose

	; ---- Move CHOPMAIN_FLIP from $4400 to $2300 (main-to-main copy) ----
	; $2300-$37DB: just above loader end ($22FC). Does not overlap
	; LOADBUFFER ($4000-$43FF) or CHOPMAIN staging ($4400-$58DA).
	; After this copy, $4400 is free for CHOPMAIN staging.
	lda #$00
	sta $90					; source lo = $00
	lda #$44
	sta $91					; source hi = $44 => source = $4400
	lda #$00
	sta $92					; dest lo = $00
	lda #$23
	sta $93					; dest hi = $23 => dest = $2300

	ldx #>chopMainFlipLen	; X = number of full pages

@mainFlipReloCopyPageLoop:
	ldy #0
@mainFlipReloCopyByteLoop:
	lda ($90),y
	sta ($92),y
	iny
	bne @mainFlipReloCopyByteLoop

	inc $91
	inc $93
	dex
	bne @mainFlipReloCopyPageLoop

	ldy #0
	ldx #<chopMainFlipLen
	beq @mainFlipReloCopyDone

@mainFlipReloCopyRemLoop:
	lda ($90),y
	sta ($92),y
	iny
	dex
	bne @mainFlipReloCopyRemLoop

@mainFlipReloCopyDone:

	; ---- Story 8: Load CHOPMAIN to main memory staging buffer ($4400) ----
	; $4400 is free: CHOPAXFLIP and CHOPMXFLIP have been moved out.
	; CHOPMAIN stages here temporarily; LC RAM copy happens after all ProDOS I/O.
	jsr PRODOS
	.byte $c8
	.addr fileOpenMain
	beq :+
	brk
:

	jsr PRODOS
	.byte $ca
	.addr fileReadMain
	beq :+
	brk
:

	jsr PRODOS
	.byte $cc
	.addr fileClose

	; ---- All ProDOS I/O is complete. Now perform all LC Bank 2 writes. ----
	; ProDOS MLI calls use LC Bank 2 (kernel at $D000-$FFFF) and restore ProDOS data
	; to that range after each call. Any LC RAM writes made before this point would be
	; overwritten. Performing all LC copies here, after the final ProDOS close, ensures
	; the data survives to game start.

	; LC write-enable (double read of $C083 = LC Bank 2 read+write enable)
pass1RowPassBase   = $1DC0		; verify in choplifter.lst
pass1RowPassLen    = $27		; 39 bytes — verify in choplifter.lst
	lda $C083				; LC Bank 2 read+write enable, first strobe
	lda $C083				; LC Bank 2 read+write enable, second strobe (write now active)

	; Copy pass1RowPass to LC RAM $D000 (39 bytes from CHOP0 at $1DC0).
	ldx #0
@copyPass1:
	lda pass1RowPassBase,x
	sta $D000,x
	inx
	cpx #pass1RowPassLen
	bne @copyPass1

	; Copy CHOPMAIN from $4400 to LC RAM $D070.
	; $D070 + $14DB = $E54B — fits within LC RAM ($D000-$FFFF).
	; Source pointer in ZP $90/$91, dest pointer in ZP $92/$93 (loader scratch).
	lda #$00
	sta $90					; source lo = $00
	lda #$44
	sta $91					; source hi = $44 => source = $4400
	lda #$70
	sta $92					; dest lo = $70
	lda #$D0
	sta $93					; dest hi = $D0 => dest = $D070

	ldx #>chopMainLen		; X = number of full pages

@chopMainCopyPageLoop:
	ldy #0
@chopMainCopyByteLoop:
	lda ($90),y
	sta ($92),y
	iny
	bne @chopMainCopyByteLoop

	inc $91
	inc $93
	dex
	bne @chopMainCopyPageLoop

	ldy #0
	ldx #<chopMainLen
	beq @chopMainCopyDone

@chopMainCopyRemLoop:
	lda ($90),y
	sta ($92),y
	iny
	dex
	bne @chopMainCopyRemLoop

@chopMainCopyDone:

	; Copy CHOPMAIN_FLIP from $2300 to LC RAM $E54B.
	; $E54B + $14DB = $FA26 — fits within LC RAM.
	; LC writes still active from above.
	lda #$4B
	sta $92					; dest lo = $4B
	lda #$E5
	sta $93					; dest hi = $E5 => dest = $E54B
	lda #$00
	sta $90					; source lo = $00
	lda #$23
	sta $91					; source hi = $23 => source = $2300

	ldx #>chopMainFlipLen	; X = number of full pages

@chopMainFlipCopyPageLoop:
	ldy #0
@chopMainFlipCopyByteLoop:
	lda ($90),y
	sta ($92),y
	iny
	bne @chopMainFlipCopyByteLoop

	inc $91
	inc $93
	dex
	bne @chopMainFlipCopyPageLoop

	ldy #0
	ldx #<chopMainFlipLen
	beq @chopMainFlipCopyDone

@chopMainFlipCopyRemLoop:
	lda ($90),y
	sta ($92),y
	iny
	dex
	bne @chopMainFlipCopyRemLoop

@chopMainFlipCopyDone:

	jmp initVectors

chopAuxLen      = $14DB		; CHOPAUX = 5339 bytes (Option B pixel doubling)
chopMainLen     = $14DB		; CHOPMAIN = 5339 bytes (Option B pixel doubling)
chopAuxFlipLen  = $14DB		; CHOPAUX_FLIP = 5339 bytes (same size as CHOPAUX)
chopMainFlipLen = $14DB		; CHOPMAIN_FLIP = 5339 bytes (same size as CHOPMAIN)

ioError:
	brk

initVectors:
	; Prepare game flow vectors. These are things that Dan's loader would have done
	; but have been lost in this reverse engineer because I've converted it to ProDOS
	; None of these vectors ever change during gameplay, so making them an indirection
	; was probably a development and debugging tool.
	lda		#$c7					; Initialize game start vector
	sta		$2a		; ZP_LOADERVECTOR_L  = startDemoMode $09c7 (unchanged)
	lda		#$09
	sta		$2b		; ZP_LOADERVECTOR_H
	lda		#$1f
	sta		$28		; ZP_STARTTITLE_JMP_L = startTitleSequence $081f (unchanged)
	lda		#$08
	sta		$29		; ZP_STARTTITLE_JMP_H
	lda		#$5f					; startNewGame $0b5f (unchanged)
	sta		$3a		; ZP_GAMESTART_JMP_L
	lda		#$0b
	sta		$3b		; ZP_GAMESTART_JMP_H
	lda		#$13					; after sortie banner $0c13 (unchanged)
	sta		$3c		; ZP_NEWSORTIE_JMP_L
	lda		#$0c
	sta		$3d		; ZP_NEWSORTIE_JMP_H
	lda		#$9b					; beginSortie $0b9b (unchanged)
	sta		$4e		; ZP_GAMEINIT_L
	lda		#$0b
	sta		$4f		; ZP_GAMEINIT_H
	lda		#$92					; gameOverLoss $0c92 (unchanged)
	sta		$24		; ZP_INDIRECT_JMP_L
	lda		#$0c
	sta		$25		; ZP_INDIRECT_JMP_H

	; Give ourselves a stub in $300 because Choplifter is about to erase this area of memory
	lda 	#$20		; jsr jumpStartGraphicsDeadCode
	sta		$300
	lda		#$09
	sta		$301
	lda		#$90
	sta		$302

	; Jump into Choplifter loader entry, and Dan's code is none the wiser, partying like it's 1982.
	lda		#$4c		; jmp $0800
	sta		$303
	lda		#$00
	sta		$304
	lda		#$08
	sta		$305

	; Story 6: SETINTCXROM — maps Apple IIe internal ROM over $C100-$CFFF.
	; Kept as defensive hardening; primary IRQ fix is SEI in initRendering (choplifter.s).
	; AN3 ($C05E), AUX memory switching ($C001/$C003-$C005), and DHGR display
	; remain functional — they are main-logic soft switches, not card firmware.
	sta		$C007				; SETINTCXROM — map internal ROM over slot firmware

	; Mirror auxReadByte trampoline to AUX memory so RAMRDAUX is safe during blitImage.
	; auxReadByte address is determined by natural assembly position in choplifter.s.
	; Update this constant whenever LOCODE code before auxReadByte is added/removed.
	; Verify by checking choplifter.lst for the assembled address of auxReadByte.
	; RAMWRAUX: writes go to AUX, reads still come from MAIN — safe for this copy loop.
auxTrampolineBase = $1E0E	; auxReadByte natural position — verified in choplifter.lst (Story 8 QA: $1E0E after table relocation)

auxTrampolineLen  = 10
	ldy		#auxTrampolineLen - 1
	sei
	sta		$C005				; RAMWRAUX — writes now go to AUX
@copyAuxTrampoline:
	lda		auxTrampolineBase,y	; read from MAIN $1D92+Y
	sta		auxTrampolineBase,y	; write to AUX $1D92+Y (RAMWRAUX active)
	dey
	bpl		@copyAuxTrampoline
	sta		$C004				; RAMWRMAIN — restore writes to MAIN
	cli

	; Jump into our new stub, and this loader now ceases to exist
	jmp 	$0300


;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

fileOpenCode0:
	.byte 3
	.addr codePath0
	.addr LOADBUFFER
	.byte 0					; Result (file handle)
	.byte 0					; Padding

fileRead0:
	.byte 4
	.byte 1					; File handle (we know it's gonna be 1)
	.addr $800
	.word $1800
fileRead0Len:
	.word 0					; Result (bytes read)

fileOpenCode1:
	.byte 3
	.addr codePath1
	.addr LOADBUFFER
	.byte 0					; Result (file handle)
	.byte 0					; Padding

fileRead1:
	.byte 4
	.byte 1					; File handle (we know it's gonna be 1)
	.addr $6000
	.word $5000				; Read full HICODE segment — DHGR rendering subsystem may exceed $A0FF
fileRead1Len:
	.word 0					; Result (bytes read)

fileOpenGfx:
	.byte 3
	.addr gfxPath
	.addr LOADBUFFER
	.byte 0					; Result (file handle)
	.byte 0					; Padding

fileReadGfx:
	.byte 4
	.byte 1					; File handle (we know it's gonna be 1)
	.addr $a102
	.word $1ded				; Don't step on ProDOS when loading graphics
fileReadGfxLen:
	.word 0					; Result (bytes read)

fileOpenGfxHi:
	.byte 3
	.addr gfxPathHi
	.addr LOADBUFFER
	.byte 0					; Result (file handle)
	.byte 0					; Padding

fileReadGfxHi:
	.byte 4
	.byte 1					; File handle (we know it's gonna be 1)
	.addr $5000
	.word $70				; This little piece would step on ProDOS
fileReadGfxHiLen:
	.word 0					; Result (bytes read)

fileOpenAux:
	.byte 3
	.addr auxPath
	.addr LOADBUFFER
	.byte 0					; Result (file handle)
	.byte 0					; Padding

fileReadAux:
	.byte 4
	.byte 1					; File handle (we know it's gonna be 1)
	.addr $4400				; $4400 avoids conflict with 1KB OPEN I/O buffer at $4000-$43FF
	.word $14DB				; chopAuxLen = 5339 bytes (Option B pixel doubling)
fileReadAuxLen:
	.word 0					; Result (bytes read)

fileOpenMain:
	.byte 3
	.addr mainPath
	.addr LOADBUFFER
	.byte 0					; Result (file handle)
	.byte 0					; Padding

fileReadMain:
	.byte 4
	.byte 1					; File handle (we know it's gonna be 1)
	.addr $4400				; Reuse $4400 staging buffer (CHOPAUX already copied to AUX)
	.word $14DB				; chopMainLen = 5339 bytes (Option B pixel doubling)
fileReadMainLen:
	.word 0					; Result (bytes read)

fileOpenAuxFlip:
	.byte 3
	.addr auxFlipPath
	.addr LOADBUFFER
	.byte 0					; Result (file handle)
	.byte 0					; Padding

fileReadAuxFlip:
	.byte 4
	.byte 1					; File handle (we know it's gonna be 1)
	.addr $4400				; $4400 avoids conflict with 1KB OPEN I/O buffer at $4000-$43FF
	.word $14DB				; chopAuxFlipLen = 5339 bytes
fileReadAuxFlipLen:
	.word 0					; Result (bytes read)

fileOpenMainFlip:
	.byte 3
	.addr mainFlipPath
	.addr LOADBUFFER
	.byte 0					; Result (file handle)
	.byte 0					; Padding

fileReadMainFlip:
	.byte 4
	.byte 1					; File handle (we know it's gonna be 1)
	.addr $4400				; Stage at $4400 (no conflict with LOADBUFFER=$4000)
	.word $14DB				; chopMainFlipLen = 5339 bytes
fileReadMainFlipLen:
	.word 0					; Result (bytes read)

fileClose:
	.byte 1
	.byte 1					; File handle (we know it's gonna be 1)


.macro  pstring Arg
	.byte   .strlen(Arg), Arg
.endmacro


codePath0:
	pstring "/CHOPLIFTER/CHOP0"
codePath1:
	pstring "/CHOPLIFTER/CHOP1"
gfxPath:
	pstring "/CHOPLIFTER/CHOPGFX"
gfxPathHi:
	pstring "/CHOPLIFTER/CHOPGFXHI"
auxPath:
	pstring "/CHOPLIFTER/CHOPAUX"
mainPath:
	pstring "/CHOPLIFTER/CHOPMAIN"
auxFlipPath:
	pstring "/CHOPLIFTER/CHOPAXFLIP"
mainFlipPath:
	pstring "/CHOPLIFTER/CHOPMXFLIP"
