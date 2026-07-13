```assembler
LOAD   r, [r]       ; r := mem[r]
STORE  [r], r2      ; mem[r] := r2
ADD    r, imm       ; r := r + imm
JMP    r            ; PC := r
JZ     r, offset    ; if r==0 then IP := IP+offset
PUSH_D r            ; DSP := DSP - CELL; mem[DSP] := r
POP_D  r            ; r := mem[DSP]; DSP := DSP + CELL
PUSH_R r            ; RSP := RSP - CELL; mem[RSP] := r
POP_R  r            ; r := mem[RSP]; RSP := RSP + CELL
HALT                ; stop
```

## Registers available:

* IP (interpreter pointer)
* W (current word CFA)
* ACC (scratch accumulator)
* XT (target code pointer)
* DSP, RSP (data & return stack pointers)

## Microcode Routines

### 1. NEXT

```assembler
; NEXT:
;   W  := [IP]        ; fetch CFA
;   IP := IP + CELL
;   XT := [W]         ; fetch code field
;   JMP XT

LOAD   W, [IP]        ; W = mem[IP]
ADD    IP, CELL       ; advance thread pointer
LOAD   XT, [W]        ; XT = mem[CFA]
JMP    XT             ; jump to primitive at XT
```

### 2. DOCOL

```assembler
; DOCOL:
;   PUSH_R IP         ; save old IP
;   IP := W + CELL    ; point IP to parameter field
;   NEXT

PUSH_R IP
ADD    W, CELL
MOV    IP, W          ; (pseudo: copy W into IP)
JMP    NEXT

```

(MOV is not part of the 7 ops, but we can synthesize it:
ACC := W; IP := ACC via stack round-trip, or reserve a trivial MOV in microcode.)

### 3. EXIT

```assembler
; EXIT:
;   POP_R IP          ; restore return IP
;   NEXT

POP_R  IP
JMP    NEXT
```

### 4. LIT

```assembler
; LIT:
;   PUSH_D [IP]       ; push literal onto data stack
;   IP := IP + CELL
;   NEXT

LOAD   ACC, [IP]      ; ACC = literal
PUSH_D ACC
ADD    IP, CELL
JMP    NEXT
```

### 5. 0BRANCH

```assembler
; 0BRANCH:
;   x := POP_D
;   if x==0 then IP := IP + offset
;   NEXT

POP_D  ACC            ; ACC = top of stack
JZ     ACC, offset    ; if ACC==0, skip/branch
JMP    NEXT
```


(offset is encoded in the instruction stream after the CFA of 0BRANCH. Microcode routine fetches it just like LIT would; here I’ve shown it as an immediate operand for clarity.)

## Notes

With only LOAD/STORE/ADD/JMP/JZ/PUSH/POP, we’re at the absolute minimum.

I used a MOV in DOCOL, but you can synthesize it:

```assembler
PUSH_D W
POP_D IP
```

That way you don’t need a dedicated MOV.

Branch offsets (0BRANCH) can be encoded as signed cells in the thread following the CFA, exactly like LIT does. Then:

```assembler
LOAD   ACC, [IP]     ; ACC = offset
ADD    IP, CELL
POP_D  XT            ; XT = condition
JZ     XT, ACC       ; apply offset if zero
JMP    NEXT
```

With just these microcoded routines, you can run colon definitions, literals, branching, and returns — which is the full execution model of ITC Forth. All other words (DUP, +, @, etc.) are just more microcoded primitives added later.
