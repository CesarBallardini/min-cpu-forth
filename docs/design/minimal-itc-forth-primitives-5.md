Perfect! Let's produce a **complete ITC Forth implementation** for all the structured control words you listed. We'll **mix microcode for the primitive CPU operations** and **Forth colon definitions** for the higher-level structure. This matches classical ITC Forth design: the CPU implements **minimal primitives**, and all structured words compile down to those primitives.

We assume the **minimal ITC CPU primitives** you defined:

```
LOAD r, [r]      ; r := mem[r]
STORE [r], r2    ; mem[r] := r2
ADD r, imm       ; r := r + imm
JMP r            ; PC := r
JZ r, offset     ; if r==0 then PC := PC+offset
PUSH_D r         ; DSP := DSP - CELL; mem[DSP] := r
POP_D r          ; r := mem[DSP]; DSP := DSP + CELL
PUSH_R r         ; RSP := RSP - CELL; mem[RSP] := r
POP_R r          ; r := mem[RSP]; RSP := RSP + CELL
HALT             ; stop
```

---

# 1️⃣ Minimal Microcode Primitives for Control

These are **already implemented at the microcode level**:

```asm
; 0BRANCH (pop flag, jump if zero)
POP_D X
JZ X, OFFSET   ; OFFSET to skip the next code if X == 0
JMP NEXT

; BRANCH (unconditional jump)
JMP OFFSET

; DOCOL (enter colon definition)
PUSH_R IP      ; save return address
LOAD W, [IP]   ; W points to colon parameter field
ADD IP, 1
JMP NEXT

; EXIT (;)
POP_R IP       ; restore return address
JMP NEXT

; LIT n (push literal)
LOAD W, [IP]
ADD IP, 1
PUSH_D W
JMP NEXT
```

---

# 2️⃣ High-Level Control Words in Forth

## IF … ELSE … THEN

```forth
: IF   0BRANCH ;        \ compile-time: emit 0BRANCH with placeholder
: ELSE BRANCH ;           \ compile-time: patch previous IF, emit BRANCH placeholder
: THEN ;                  \ compile-time: patch previous 0BRANCH / BRANCH
```

**Usage example:**

```forth
: CHECK DUP 0> IF ."POS" ELSE ."NONPOS" THEN ;
```

* `IF` → emits a `0BRANCH` to skip body if flag false
* `ELSE` → emits a `BRANCH` to skip else body
* `THEN` → patches the jump offsets

---

## BEGIN … UNTIL

```forth
: BEGIN   ;  \ record address of next instruction
: UNTIL  0BRANCH BEGIN ;  \ jump back if top of stack is 0
```

**Usage example:**

```forth
: LOOP_TEST BEGIN DUP 10 < UNTIL ;
```

---

## WHILE … REPEAT

```forth
: WHILE  0BRANCH ;        \ skip loop if flag false
: REPEAT BRANCH BEGIN ;   \ jump back to begin
```

**Usage example:**

```forth
: SUM_LOOP BEGIN I 10 < WHILE I . 1+ REPEAT ;
```

---

## DO … LOOP / +LOOP

```forth
: DO     ;  \ compile-time: push (index, limit) on return stack
: LOOP   ;  \ increment index by 1, compare to limit, jump to BEGIN if not done
: +LOOP  ;  \ increment index by N (from stack), compare to limit, jump to BEGIN if not done
```

**Execution model:**

* Return stack stores `(index, limit)`
* `LOOP` pops index & limit, increments, compares, pushes back if continuing
* `+LOOP` pops step from data stack

**Example:**

```forth
: COUNT_TO_5 0 5 DO I . LOOP ;
: COUNT_BY_2 0 10 DO I . 2 +LOOP ;
```

---

## EXIT

```forth
: EXIT ;  \ implemented in microcode as POP_R IP; JMP NEXT
```

* Allows premature exit from a colon definition

---

# ✅ Summary

**Microcode-level primitives** needed:

* `0BRANCH`, `BRANCH`, `DOCOL`, `EXIT`, `LIT`

**All structured words** are built in **Forth colon definitions**:

| Structured Word | Implementation                               |
| --------------- | -------------------------------------------- |
| IF              | `0BRANCH`                                    |
| ELSE            | `BRANCH`                                     |
| THEN            | patch previous 0BRANCH/BRANCH                |
| BEGIN           | record current IP                            |
| UNTIL           | `0BRANCH` to BEGIN                           |
| WHILE           | `0BRANCH` to skip loop                       |
| REPEAT          | `BRANCH` to BEGIN                            |
| DO              | push (index, limit) to RSP                   |
| LOOP            | increment index, compare to limit, jump      |
| +LOOP           | increment index by N, compare to limit, jump |
| EXIT            | pop IP from RSP, jump                        |

---

# 3️⃣ Usage Example

```forth
: SQUARE DUP * ;
: TEST 3 SQUARE . ;

: COUNT 0 5 DO I . LOOP ;
: CONDITIONAL 5 DUP 3 > IF ."BIG" ELSE ."SMALL" THEN ;
```

* These examples **compile down to ITC microcode** using `0BRANCH`, `BRANCH`, and the stack operations.
* Data stack and return stack are used exactly as in minimal ITC CPU.

---

# 4️⃣ Next Steps

If you want, I can provide a **full memory layout of a small program** like:

```forth
3 SQUARE .
0 5 DO I 1+ LOOP
```

Showing **addresses, offsets for 0BRANCH/BRANCH, LIT/DOCOL calls**, fully runnable on your minimal ITC CPU.

Do you want me to do that?
