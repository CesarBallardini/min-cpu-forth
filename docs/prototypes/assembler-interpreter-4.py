# Minimal Python ITC Forth executioner

from typing import List, Callable, Dict

CELL = 1  # memory cell size (simplified)
MEMORY_SIZE = 1024

# ----------------------
# Stack class
# ----------------------
class Stack:
    def __init__(self, memory, start):
        self.mem = memory
        self.sp = start

    def push(self, value):
        self.sp -= CELL
        self.mem[self.sp] = value

    def pop(self):
        val = self.mem[self.sp]
        self.sp += CELL
        return val

    def peek(self):
        return self.mem[self.sp]

# ----------------------
# CPU class
# ----------------------
class CPU:
    def __init__(self):
        self.mem = [0] * MEMORY_SIZE
        self.ip = 0          # instruction pointer
        self.w = 0           # temporary register
        self.dsp = MEMORY_SIZE  # data stack pointer starts at end
        self.rsp = MEMORY_SIZE  # return stack pointer
        self.data_stack = Stack(self.mem, self.dsp)
        self.return_stack = Stack(self.mem, self.rsp)
        self.halted = False

    # Minimal primitives
    def load(self, addr):
        self.w = self.mem[addr]

    def store(self, addr, val):
        self.mem[addr] = val

    def add(self, r, imm):
        setattr(self, r, getattr(self, r) + imm)

    def jmp(self, addr):
        self.ip = addr

    def jz(self, r, offset):
        if getattr(self, r) == 0:
            self.ip += offset

    def push_d(self, r):
        self.data_stack.push(getattr(self, r))

    def pop_d(self, r):
        setattr(self, r, self.data_stack.pop())

    def push_r(self, r):
        self.return_stack.push(getattr(self, r))

    def pop_r(self, r):
        setattr(self, r, self.return_stack.pop())

    def halt(self):
        self.halted = True

# ----------------------
# Instruction Strategy
# ----------------------
class Instruction:
    def execute(self, cpu: CPU):
        raise NotImplementedError()

# ----------------------
# Executioner / Forth interpreter
# ----------------------
class ForthExecutioner:
    def __init__(self, cpu: CPU):
        self.cpu = cpu
        self.dict: Dict[str, Callable] = {}
        self.colon_defs: Dict[str, List[str]] = {}  # colon definitions
        self.build_minimal_dictionary()

    def add_colon_def(self, name: str, code: List[str]):
        """Add a colon definition"""
        self.colon_defs[name] = code
        self.dict[name] = lambda name=name: self._execute_colon(name)

    def _execute_colon(self, name: str):
        """Execute a colon definition"""
        code = self.colon_defs[name]
        for word in code:
            if word in self.dict:
                # If word is a lambda or primitive, call it
                self.dict[word]()
            else:
                raise ValueError(f"Unknown word: {word}")

    def build_minimal_dictionary(self):
        # --- Stack ops ---
        self.dict['DUP'] = lambda: self.cpu.data_stack.push(self.cpu.data_stack.peek())
        self.dict['DROP'] = lambda: self.cpu.data_stack.pop()
        self.dict['SWAP'] = lambda: self._swap()
        self.dict['OVER'] = lambda: self._over()
        self.dict['ROT'] = lambda: self._rot()
        self.dict['-ROT'] = lambda: self._neg_rot()
        self.dict['NIP'] = lambda: self._nip()
        self.dict['TUCK'] = lambda: self._tuck()

        # --- Arithmetic ---
        self.dict['+'] = lambda: self._binop(lambda a, b: a + b)
        self.dict['-'] = lambda: self._binop(lambda a, b: a - b)
        self.dict['*'] = lambda: self._binop(lambda a, b: a * b)
        self.dict['/'] = lambda: self._binop(lambda a, b: a // b)
        self.dict['MOD'] = lambda: self._binop(lambda a, b: a % b)
        self.dict['NEGATE'] = lambda: self.cpu.data_stack.push(-self.cpu.data_stack.pop())
        self.dict['ABS'] = lambda: self.cpu.data_stack.push(abs(self.cpu.data_stack.pop()))
        self.dict['1+'] = lambda: self.cpu.data_stack.push(self.cpu.data_stack.pop()+1)
        self.dict['1-'] = lambda: self.cpu.data_stack.push(self.cpu.data_stack.pop()-1)

        # --- Memory ops ---
        self.dict['@'] = lambda: self.cpu.data_stack.push(self.cpu.mem[self.cpu.data_stack.pop()])
        self.dict['!'] = lambda: self.cpu.mem.__setitem__(self.cpu.data_stack.pop(), self.cpu.data_stack.pop())
        # byte access could be implemented similarly (C@, C!)

        # --- Return stack ---
        self.dict['>R'] = lambda: self.cpu.return_stack.push(self.cpu.data_stack.pop())
        self.dict['R>'] = lambda: self.cpu.data_stack.push(self.cpu.return_stack.pop())
        self.dict['R@'] = lambda: self.cpu.data_stack.push(self.cpu.return_stack.peek())

        # --- Comparisons / Logic ---
        self.dict['='] = lambda: self._binop(lambda a,b: int(a==b))
        self.dict['<>'] = lambda: self._binop(lambda a,b: int(a!=b))
        self.dict['<'] = lambda: self._binop(lambda a,b: int(a<b))
        self.dict['>'] = lambda: self._binop(lambda a,b: int(a>b))
        self.dict['0='] = lambda: self.cpu.data_stack.push(int(self.cpu.data_stack.pop() == 0))
        self.dict['0<'] = lambda: self.cpu.data_stack.push(int(self.cpu.data_stack.pop() < 0))
        self.dict['AND'] = lambda: self._binop(lambda a,b: a & b)
        self.dict['OR'] = lambda: self._binop(lambda a,b: a | b)
        self.dict['INVERT'] = lambda: self.cpu.data_stack.push(~self.cpu.data_stack.pop())

        # --- Forth control primitives ---
        self.dict['LIT'] = lambda n: self.cpu.data_stack.push(n)
        self.dict['DOCOL'] = lambda addr: self._docol(addr)
        self.dict['EXIT'] = lambda: self._exit()

        # --- Control structures are implemented as colon definitions ---
        self.dict['IF'] = lambda: None
        self.dict['ELSE'] = lambda: None
        self.dict['THEN'] = lambda: None
        self.dict['BEGIN'] = lambda: None
        self.dict['UNTIL'] = lambda: None
        self.dict['WHILE'] = lambda: None
        self.dict['REPEAT'] = lambda: None
        self.dict['DO'] = lambda: None
        self.dict['LOOP'] = lambda: None
        self.dict['+LOOP'] = lambda: None
        self.dict['BYE'] = lambda: self.cpu.halt()

    # ----------------------
    # Helper methods
    # ----------------------
    def _binop(self, func):
        b = self.cpu.data_stack.pop()
        a = self.cpu.data_stack.pop()
        self.cpu.data_stack.push(func(a,b))

    def _swap(self):
        a = self.cpu.data_stack.pop()
        b = self.cpu.data_stack.pop()
        self.cpu.data_stack.push(a)
        self.cpu.data_stack.push(b)

    def _over(self):
        b = self.cpu.data_stack.pop()
        a = self.cpu.data_stack.peek()
        self.cpu.data_stack.push(b)
        self.cpu.data_stack.push(a)

    def _rot(self):
        c = self.cpu.data_stack.pop()
        b = self.cpu.data_stack.pop()
        a = self.cpu.data_stack.pop()
        self.cpu.data_stack.push(b)
        self.cpu.data_stack.push(c)
        self.cpu.data_stack.push(a)

    def _neg_rot(self):
        c = self.cpu.data_stack.pop()
        b = self.cpu.data_stack.pop()
        a = self.cpu.data_stack.pop()
        self.cpu.data_stack.push(c)
        self.cpu.data_stack.push(a)
        self.cpu.data_stack.push(b)

    def _nip(self):
        a = self.cpu.data_stack.pop()
        b = self.cpu.data_stack.pop()
        self.cpu.data_stack.push(a)

    def _tuck(self):
        a = self.cpu.data_stack.pop()
        b = self.cpu.data_stack.pop()
        self.cpu.data_stack.push(a)
        self.cpu.data_stack.push(b)
        self.cpu.data_stack.push(a)

    def _docol(self, addr):
        self.cpu.push_r('ip')
        self.cpu.ip = addr

    def _exit(self):
        self.cpu.pop_r('ip')

# ----------------------
# Example usage
# ----------------------
if __name__ == "__main__":
    cpu = CPU()
    forth = ForthExecutioner(cpu)

    # Test minimal stack arithmetic
    cpu.data_stack.push(3)
    forth.dict['DUP']()
    forth.dict['+']()
    result = cpu.data_stack.pop()
    print("3 DUP + =>", result)  # should print 6



# ----------------------
# Add colon definitions for structured control
# ----------------------
def build_standard_colon_defs(vm: ForthExecutioner):
    # IF ... ELSE ... THEN
    # Compiles down to: 0BRANCH (skip if false), optional BRANCH (skip ELSE)
    vm.add_colon_def('IF_THEN', ['0BRANCH'])  # user would compile literals and 0BRANCH
    vm.add_colon_def('IF_ELSE_THEN', ['0BRANCH', 'BRANCH'])  # simplified

    # BEGIN ... UNTIL
    vm.add_colon_def('BEGIN_UNTIL', ['BEGIN', 'UNTIL'])  # simplified placeholder

    # WHILE ... REPEAT
    vm.add_colon_def('WHILE_REPEAT', ['WHILE', 'REPEAT'])

    # DO ... LOOP
    vm.add_colon_def('DO_LOOP', ['DO', 'LOOP'])
    vm.add_colon_def('DO_PLUS_LOOP', ['DO', '+LOOP'])

    # EXIT
    vm.add_colon_def(';', ['EXIT'])

# ----------------------
# Example usage
# ----------------------
if __name__ == "__main__":
    cpu = CPU()
    vm = ForthExecutioner(cpu)
    build_standard_colon_defs(vm)

    # Example: : SQUARE DUP * ;
    vm.add_colon_def('SQUARE', ['DUP', '*'])

    # Forth program: 3 SQUARE .
    cpu.data_stack.push(3)
    vm.dict['SQUARE']()
    result = cpu.data_stack.pop()
    print("3 SQUARE =>", result)  # should print 9

    # You can add more tests using IF/ELSE/THEN or loops:
    # vm.add_colon_def('TEST', ['LIT', 1, 'IF_THEN', ...])
