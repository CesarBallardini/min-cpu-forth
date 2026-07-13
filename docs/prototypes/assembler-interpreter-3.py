# ----------------------
# Extend ForthExecutioner for colon definitions
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
