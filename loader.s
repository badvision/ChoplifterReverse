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
	bne ioError

	; Load low code at $800
	jsr PRODOS
	.byte $ca
	.addr fileRead0
	bne ioError
	
	; Close the file
	jsr PRODOS
	.byte $cc
	.addr fileClose

	; Open the high code file
	jsr PRODOS
	.byte $c8
	.addr fileOpenCode1
	bne ioError

	; Load high code at $6000
	jsr PRODOS
	.byte $ca
	.addr fileRead1
	bne ioError

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
	bne ioError

	; Step 2: Read CHOPAUX into main $4400 (above 1KB OPEN I/O buffer at $4000-$43FF)
	jsr PRODOS
	.byte $ca
	.addr fileReadAux
	bne ioError

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

	jmp initVectors

chopAuxLen = $14DB			; CHOPAUX = 5339 bytes

ioError:
	brk

initVectors:
	; Prepare game flow vectors. These are things that Dan's loader would have done
	; but have been lost in this reverse engineer because I've converted it to ProDOS
	; None of these vectors ever change during gameplay, so making them an indirection
	; was probably a development and debugging tool.
	lda		#$c7					; Initialize game start vector
	sta		$2a		; ZP_LOADERVECTOR_L
	lda		#$09
	sta		$2b		; ZP_LOADERVECTOR_H
	lda		#$1f
	sta		$28		; ZP_STARTTITLE_JMP_L
	lda		#$08
	sta		$29		; ZP_STARTTITLE_JMP_H
	lda		#$5f
	sta		$3a		; ZP_GAMESTART_JMP_L
	lda		#$0b
	sta		$3b		; ZP_GAMESTART_JMP_H
	lda		#$13
	sta		$3c		; ZP_NEWSORTIE_JMP_L
	lda		#$0c
	sta		$3d		; ZP_NEWSORTIE_JMP_H
	lda		#$9b
	sta		$4e		; ZP_GAMEINIT_L
	lda		#$0b
	sta		$4f		; ZP_GAMEINIT_H
	lda		#$92
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

	; Mirror auxReadByte trampoline to AUX memory so RAMRDAUX is safe during blitImage.
	; auxReadByte lives at $1AA7 in CHOP0 (already loaded). Copy 10 bytes to AUX $1AA7.
	; RAMWRAUX: writes go to AUX, reads still come from MAIN — safe for this copy loop.
auxTrampolineBase = $1AA7
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
	.word $14DB				; chopAuxLen = 5339 bytes
fileReadAuxLen:
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
