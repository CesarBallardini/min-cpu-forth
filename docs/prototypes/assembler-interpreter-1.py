"""
Minimal ITC Virtual CPU + Forth Dictionary Demo
Now extended with a tiny threaded Forth system demo.
"""

from typing import List, Dict, Callable

# === CPU / Memory / Stack from before ===

class Stack:
    def __init__(self, memory: List[int], base: int, size: int):
        self.memory = memory
        self.base = base
        self.sp = base + size  # downward-growing
        self.size = size

    def push(self, val: int):
        if self.sp <= self.base:
            raise OverflowError("Stack overflow")
        self.sp -= 1
        self.memory[self.sp] = val

    def pop(self) -> int:
        if self.sp >= self.base + self.size:
            raise OverflowError("Stack underflow")
        val = self.memory[self.sp]
        self.sp += 1
        return val

    def peek(self) -> int:
        return self.memory[self.sp]


class CPU:
    def __init__(self, memsize: int = 65536):
        self.memory = [0] * memsize
        self.PC = 0
        self.IP = 0
        self.W = 0
        # Data stack at top 1k
        self.D = Stack(self.memory, memsize - 2048, 1024)
        # Return stack at next 1k
        self.R = Stack(self.memory, memsize - 1024, 1024)


# === Primitive operations for the micro-ISA ===

class Instruction:
    def execute(self, cpu: CPU):
        raise NotImplementedError


class NOP(Instruction):
    def execute(self, cpu):
        pass


class LOAD(Instruction):
    def __init__(self, reg: str, addr_reg: str):
        self.reg = reg; self.addr_reg = addr_reg
    def execute(self, cpu):
        setattr(cpu, self.reg, cpu.memory[getattr(cpu, self.addr_reg)])


class STORE(Instruction):
    def __init__(self, addr_reg: str, reg: str):
        self.addr_reg = addr_reg; self.reg = reg
    def execute(self, cpu):
        cpu.memory[getattr(cpu, self.addr_reg)] = getattr(cpu, self.reg)


class ADD(Instruction):
    def __init__(self, reg_a: str, reg_b: str):
        self.reg_a = reg_a; self.reg_b = reg_b
    def execute(self, cpu):
        setattr(cpu, self.reg_a, getattr(cpu, self.reg_a) + getattr(cpu, self.reg_b))


class JMP(Instruction):
    def __init__(self, addr_reg: str):
        self.addr_reg = addr_reg
    def execute(self, cpu):
        cpu.PC = getattr(cpu, self.addr_reg)


class JZ(Instruction):
    def __init__(self, reg: str, target: int):
        self.reg = reg; self.target = target
    def execute(self, cpu):
        if getattr(cpu, self.reg) == 0:
            cpu.PC = self.target


class NEXT(Instruction):
    """Advance inner interpreter"""
    def execute(self, cpu):
        w = cpu.memory[cpu.IP]; cpu.IP += 1
        cpu.W = w
        # Jump to code field
        cpu.PC = cpu.memory[w]


# === Forth system glue ===

class ForthVM:
    def __init__(self, cpu: CPU):
        self.cpu = cpu
        self.dictionary: Dict[str, int] = {}
        self.here = 0x1000  # code/data space start
        self.primitives: Dict[str, Callable] = {}

        # Install core words
        self.install_primitive("EXIT", self.prim_exit)
        self.install_primitive("LIT", self.prim_lit)
        self.install_primitive("DUP", self.prim_dup)
        self.install_primitive("*", self.prim_mul)
        self.install_primitive(".", self.prim_dot)

    def install_primitive(self, name: str, fn: Callable):
        addr = self.here
        self.cpu.memory[addr] = -1  # marker: primitive
        self.primitives[name] = fn
        self.dictionary[name] = addr
        self.here += 1

    def add_colon_def(self, name: str, body_words: List[str]):
        addr = self.here
        self.dictionary[name] = addr
        self.cpu.memory[addr] = self.dictionary["DOCOL"]  # code field
        self.here += 1
        # body
        for w in body_words:
            self.cpu.memory[self.here] = self.dictionary[w] if w in self.dictionary else int(w)
            self.here += 1
        self.cpu.memory[self.here] = self.dictionary["EXIT"]; self.here += 1

    # === Core primitives ===
    def prim_exit(self):
        self.cpu.IP = self.cpu.R.pop()
        self.cpu.PC = -99  # signal NEXT

    def prim_lit(self):
        val = self.cpu.memory[self.cpu.IP]; self.cpu.IP += 1
        self.cpu.D.push(val)
        self.cpu.PC = -99

    def prim_dup(self):
        v = self.cpu.D.pop()
        self.cpu.D.push(v); self.cpu.D.push(v)
        self.cpu.PC = -99

    def prim_mul(self):
        b = self.cpu.D.pop(); a = self.cpu.D.pop()
        self.cpu.D.push(a*b)
        self.cpu.PC = -99

    def prim_dot(self):
        v = self.cpu.D.pop()
        print(v)
        self.cpu.PC = -99

    # === Inner interpreter ===
    def run_word(self, name: str):
        addr = self.dictionary[name]
        if addr in self.primitives:
            self.primitives[name]()
        elif self.cpu.memory[addr] == -1:
            self.primitives[name]()
        else:
            # colon def
            self.cpu.R.push(self.cpu.IP)
            self.cpu.IP = addr + 1
            while True:
                w = self.cpu.memory[self.cpu.IP]; self.cpu.IP += 1
                if w in self.primitives:
                    self.primitives[w]()
                elif self.cpu.memory[w] == -1:
                    # primitive by addr
                    for pname, fn in self.primitives.items():
                        if self.dictionary[pname] == w:
                            fn(); break
                else:
                    # colon def call
                    self.cpu.R.push(self.cpu.IP)
                    self.cpu.IP = w + 1
                if self.cpu.IP == 0:
                    break

    def repl(self, line: str):
        for token in line.strip().split():
            if token.isdigit():
                self.cpu.D.push(int(token))
            elif token in self.dictionary:
                self.run_word(token)
            else:
                print(f"Unknown word: {token}")


# === Demo ===
if __name__ == "__main__":
    cpu = CPU()
    vm = ForthVM(cpu)
    # Add DOCOL primitive (fake)
    vm.dictionary["DOCOL"] = -2

    # Define : SQUARE DUP * ;
    vm.add_colon_def("SQUARE", ["DUP", "*"])

    # Run: 3 SQUARE .
    vm.repl("3 SQUARE .")
