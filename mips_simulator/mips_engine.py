"""
mips_engine.py - MIPS32 Simulation Engine
==========================================
Core simulator for a MIPS32 subset. Handles:
  - 32 general-purpose registers + HI/LO/PC
  - Text segment (instruction memory)
  - Data segment (data memory)
  - Assembler: label resolution, instruction encoding
  - Step / Run execution with state snapshotting (for Undo)
  - Basic syscall handling (print_int, print_string, exit)

Supported Instructions
----------------------
  R-type : add, sub, and, or, sll, srl, jr
  I-type : addi, ori, lw, sw, beq, bne
  J-type : j, jal
"""

import re
from dataclasses import dataclass
from typing import Optional

from exceptions import AssemblyException, RuntimeException, SyscallInputRequired


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEXT_BASE  = 0x00400000   # .text segment start
DATA_BASE  = 0x10010000   # .data segment start
STACK_BASE = 0x7FFFEFFC   # $sp initial value

# Text-segment directives that emit no instructions
_TEXT_DIR_RE = re.compile(
    r'^\.(globl|extern|ent|end|type|weak|set|abi|nan|ident)\b',
    re.IGNORECASE,
)
_ALIGN_RE = re.compile(r'^\.align\s+(\d+)', re.IGNORECASE)

REGISTER_NAMES = [
    "$zero", "$at", "$v0", "$v1",
    "$a0",   "$a1", "$a2", "$a3",
    "$t0",   "$t1", "$t2", "$t3", "$t4", "$t5", "$t6", "$t7",
    "$s0",   "$s1", "$s2", "$s3", "$s4", "$s5", "$s6", "$s7",
    "$t8",   "$t9",
    "$k0",   "$k1",
    "$gp",   "$sp", "$fp", "$ra",
]

# Numeric aliases  e.g. $0, $1, … $31
REGISTER_ALIASES = {f"${i}": i for i in range(32)}
REGISTER_MAP = {name: idx for idx, name in enumerate(REGISTER_NAMES)}
REGISTER_MAP.update(REGISTER_ALIASES)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SimulatorState:
    """
    A full snapshot of simulator state — used for undo history.
    All mutable containers are deep-copied before storage.
    """
    registers: list            # list[int] length 32
    pc: int
    hi: int
    lo: int
    memory: dict               # dict[int, int]  word-addressed
    console_output: str


@dataclass
class AssemblyError:
    line_number: int
    message: str

    def __str__(self):
        return f"Line {self.line_number}: {self.message}"


@dataclass
class ParsedInstruction:
    address: int
    source_line: int           # 1-based line number in original source
    raw_text: str              # trimmed original source text
    op: str                    # mnemonic
    args: list                 # list of parsed argument strings


# ---------------------------------------------------------------------------
# Assembler helpers
# ---------------------------------------------------------------------------

def _parse_register(token: str) -> int:
    """Return register index (0-31) or raise ValueError."""
    t = token.strip().rstrip(',')
    if t in REGISTER_MAP:
        return REGISTER_MAP[t]
    raise ValueError(f"Unknown register: '{token}'")


def _parse_immediate(token: str, labels: dict, pc: int = 0, relative: bool = False) -> int:
    """
    Parse an immediate value — decimal, hex (0x…), or a label.
    If relative=True (branches), convert absolute label address to
    the signed 16-bit offset.
    """
    t = token.strip().rstrip(',')
    # Label reference
    if t in labels:
        addr = labels[t]
        if relative:
            return (addr - (pc + 4)) >> 2   # branch offset in words
        return addr
    try:
        if t.startswith('0x') or t.startswith('0X'):
            return int(t, 16)
        return int(t)
    except ValueError:
        raise ValueError(f"Invalid immediate / unknown label: '{token}'")


def _parse_mem_operand(token: str):
    """
    Parse 'offset(base)' memory operand.
    Returns (offset: int_str, base: str).
    """
    t = token.strip()
    m = re.match(r'^(-?\w+)\((\$\w+)\)$', t)
    if not m:
        raise ValueError(f"Bad memory operand: '{token}'. Expected format: offset($reg)")
    return m.group(1), m.group(2)


# ---------------------------------------------------------------------------
# MIPSEngine — the main class
# ---------------------------------------------------------------------------

class MIPSEngine:
    """
    Full MIPS32 simulation engine.

    Usage:
        engine = MIPSEngine()
        errors = engine.load_program(source_code_string)
        if not errors:
            engine.step()         # execute one instruction
            engine.run()          # execute until halt / end
            engine.undo()         # revert last step
    """

    MAX_UNDO_DEPTH = 200

    def __init__(self):
        self._registers  = [0] * 32
        self._pc         = TEXT_BASE
        self._hi         = 0
        self._lo         = 0
        self._memory     = {}          # word-addr → int32
        self._text_seg   = {}          # addr → ParsedInstruction
        self._data_seg_info = []       # list of (label, addr, value_str)  for viewer
        self._labels     = {}          # name → address
        self._console    = ""
        self._running    = False
        self._halted     = False
        self._undo_stack: list[SimulatorState] = []
        self._errors: list[AssemblyError] = []
        self._changed_registers: set[int] = set()
        self._pending_input: Optional[SyscallInputRequired] = None

        # Initialise $sp
        self._registers[29] = STACK_BASE   # $sp = 29

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def registers(self) -> list:
        return list(self._registers)

    @property
    def pc(self) -> int:
        return self._pc

    @property
    def hi(self) -> int:
        return self._hi

    @property
    def lo(self) -> int:
        return self._lo

    @property
    def halted(self) -> bool:
        return self._halted

    @property
    def console_output(self) -> str:
        return self._console

    @property
    def needs_input(self) -> bool:
        return self._pending_input is not None

    @property
    def pending_input(self) -> Optional[SyscallInputRequired]:
        return self._pending_input

    @property
    def changed_registers(self) -> set:
        return set(self._changed_registers)

    @property
    def memory(self) -> dict:
        """Word- and byte-addressed simulated memory snapshot."""
        return dict(self._memory)

    @property
    def text_segment(self) -> dict:
        """Returns dict addr → ParsedInstruction."""
        return dict(self._text_seg)

    @property
    def data_segment(self) -> list:
        """Returns list of (label, addr, value) tuples."""
        return list(self._data_seg_info)

    @property
    def errors(self) -> list:
        return list(self._errors)

    # ------------------------------------------------------------------
    # Memory helpers
    # ------------------------------------------------------------------

    def read_word(self, addr: int) -> int:
        """Read a 32-bit signed word from simulated memory."""
        if addr % 4 != 0:
            raise RuntimeException(
                f"Unaligned word read at 0x{addr:08X}",
                context="Memory access must be 4-byte aligned",
            )
        val = self._memory.get(addr, 0)
        # Sign-extend from 32 bits
        if val >= 0x80000000:
            val -= 0x100000000
        return val

    def write_word(self, addr: int, value: int):
        """Write a 32-bit word to simulated memory."""
        if addr % 4 != 0:
            raise RuntimeException(
                f"Unaligned word write at 0x{addr:08X}",
                context="Memory access must be 4-byte aligned",
            )
        self._memory[addr] = value & 0xFFFFFFFF

    def get_memory_view(self, start: int, count: int) -> list:
        """
        Return list of (address, value) for 'count' words from 'start'.
        Missing addresses show 0.
        """
        result = []
        for i in range(count):
            addr = start + i * 4
            result.append((addr, self._memory.get(addr, 0)))
        return result

    # ------------------------------------------------------------------
    # Register helpers
    # ------------------------------------------------------------------

    def _set_reg(self, idx: int, value: int):
        """Write to a register, enforcing $zero = 0, wrapping to 32 bits."""
        if idx == 0:
            return  # $zero is always 0
        self._registers[idx] = value & 0xFFFFFFFF
        self._changed_registers.add(idx)

    def _get_reg(self, idx: int) -> int:
        """Read register, sign-extending to Python int."""
        val = self._registers[idx] & 0xFFFFFFFF
        if val >= 0x80000000:
            val -= 0x100000000
        return val

    # ------------------------------------------------------------------
    # Assembler / Loader
    # ------------------------------------------------------------------

    def load_program(self, source: str) -> list:
        """
        Assemble 'source' text and load into the simulator.
        Resets all state first.
        Returns list[AssemblyError].  Empty list = success.
        """
        self.reset()
        self._errors = []
        errors = self._errors

        lines = source.splitlines()

        # ---- Pass 1: strip comments, collect labels, split segments ----
        text_lines = []   # (original_line_no, text)
        data_lines = []   # (original_line_no, text)
        in_data = False

        for lineno, raw in enumerate(lines, start=1):
            line = raw.split('#')[0].strip()
            if not line:
                continue
            # Support multiple instructions per line separated by ';'
            parts = [p.strip() for p in line.split(';') if p.strip()]
            for part in parts:
                low = part.lower()
                if low == '.text':
                    in_data = False
                    continue
                if low == '.data':
                    in_data = True
                    continue
                if in_data:
                    data_lines.append((lineno, part))
                else:
                    text_lines.append((lineno, part))

        # ---- Pass 1b: resolve .data labels + allocate memory ----
        data_addr = DATA_BASE
        raw_string_store = {}   # addr → bytes  (for .asciiz)

        i = 0
        while i < len(data_lines):
            lineno, line = data_lines[i]
            # Label on this line?
            label_match = re.match(r'^(\w+)\s*:\s*(.*)', line)
            if label_match:
                lbl   = label_match.group(1)
                rest  = label_match.group(2).strip()
                self._labels[lbl] = data_addr
                line = rest

            if not line:
                i += 1
                continue

            # Directives
            dir_match = re.match(r'\.(word|half|byte|asciiz|ascii|space)\s+(.*)', line, re.IGNORECASE)
            if not dir_match:
                errors.append(AssemblyError(lineno, f"Unrecognised .data directive: '{line}'"))
                i += 1
                continue

            directive = dir_match.group(1).lower()
            operand   = dir_match.group(2).strip()

            try:
                if directive == 'word':
                    vals = [v.strip() for v in operand.split(',')]
                    for v in vals:
                        self.write_word(data_addr, int(v, 0))
                        self._data_seg_info.append((None, data_addr, int(v, 0)))
                        data_addr += 4

                elif directive in ('half',):
                    vals = [v.strip() for v in operand.split(',')]
                    for v in vals:
                        self._memory[data_addr] = int(v, 0) & 0xFFFF
                        self._data_seg_info.append((None, data_addr, int(v, 0)))
                        data_addr += 2
                    # Align to word
                    if data_addr % 4:
                        data_addr += 4 - (data_addr % 4)

                elif directive == 'byte':
                    vals = [v.strip() for v in operand.split(',')]
                    for v in vals:
                        self._memory[data_addr] = int(v, 0) & 0xFF
                        data_addr += 1
                    if data_addr % 4:
                        data_addr += 4 - (data_addr % 4)

                elif directive in ('asciiz', 'ascii'):
                    # Extract string literal between quotes
                    sm = re.match(r'^"(.*)"$', operand)
                    if not sm:
                        raise ValueError("String must be enclosed in double quotes")
                    s = sm.group(1)
                    # Handle escape sequences
                    s = s.replace('\\n', '\n').replace('\\t', '\t').replace('\\0', '\0').replace('\\"', '"')
                    encoded = s.encode('latin-1', errors='replace')
                    if directive == 'asciiz':
                        encoded += b'\x00'
                    raw_string_store[data_addr] = encoded
                    for b in encoded:
                        self._memory[data_addr] = b
                        data_addr += 1
                    if data_addr % 4:
                        data_addr += 4 - (data_addr % 4)

                elif directive == 'space':
                    n = int(operand, 0)
                    data_addr += n
                    if data_addr % 4:
                        data_addr += 4 - (data_addr % 4)

            except Exception as e:
                errors.append(AssemblyError(lineno, str(e)))

            i += 1

        # ---- Pass 2: resolve text labels (first pass: collect, no decode) ----
        text_addr = TEXT_BASE
        clean_text = []   # (lineno, line, address)

        for lineno, line in text_lines:
            # Label?
            label_match = re.match(r'^(\w+)\s*:\s*(.*)', line)
            if label_match:
                lbl  = label_match.group(1)
                rest = label_match.group(2).strip()
                self._labels[lbl] = text_addr
                line = rest

            if not line:
                continue

            stripped = line.strip()

            # Skip text-segment assembler directives (no machine code)
            if _TEXT_DIR_RE.match(stripped):
                continue
            align_m = _ALIGN_RE.match(stripped)
            if align_m:
                align_bytes = 1 << int(align_m.group(1))
                text_addr = ((text_addr + align_bytes - 1) // align_bytes) * align_bytes
                continue

            clean_text.append((lineno, stripped, text_addr))
            text_addr += 4

        # ---- Pass 3: decode instructions ----
        for lineno, line, addr in clean_text:
            try:
                instr = self._parse_instruction(line, addr, lineno)
                self._text_seg[addr] = instr
            except Exception as e:
                errors.append(AssemblyError(lineno, str(e)))

        if not errors:
            self._pc = TEXT_BASE
        return errors

    def _parse_instruction(self, line: str, addr: int, lineno: int) -> ParsedInstruction:
        """Parse a single assembly instruction line into a ParsedInstruction."""
        tokens = re.split(r'[\s,]+', line.strip())
        tokens = [t for t in tokens if t]
        if not tokens:
            raise ValueError("Empty instruction")

        op = tokens[0].lower()
        args = tokens[1:]

        return ParsedInstruction(
            address=addr,
            source_line=lineno,
            raw_text=line.strip(),
            op=op,
            args=args,
        )

    # ------------------------------------------------------------------
    # State snapshot helpers
    # ------------------------------------------------------------------

    def _snapshot(self) -> SimulatorState:
        return SimulatorState(
            registers=list(self._registers),
            pc=self._pc,
            hi=self._hi,
            lo=self._lo,
            memory=dict(self._memory),
            console_output=self._console,
        )

    def _restore(self, state: SimulatorState):
        self._registers = list(state.registers)
        self._pc        = state.pc
        self._hi        = state.hi
        self._lo        = state.lo
        self._memory    = dict(state.memory)
        self._console   = state.console_output
        self._halted    = False

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def step(self) -> Optional[str]:
        """
        Execute exactly one instruction at PC.
        Returns an error string on fault, None on success.
        Saves state for undo before executing.
        """
        if self._halted:
            return "Simulator is halted. Reset to run again."

        if self._pc not in self._text_seg:
            self._halted = True
            return f"PC=0x{self._pc:08X} is not in the text segment — execution halted."

        # Push undo snapshot
        snap = self._snapshot()
        if len(self._undo_stack) >= self.MAX_UNDO_DEPTH:
            self._undo_stack.pop(0)
        self._undo_stack.append(snap)

        self._changed_registers = set()

        instr = self._text_seg[self._pc]
        try:
            self._execute(instr)
        except SyscallInputRequired as req:
            self._pending_input = req
            return None
        except SystemExit:
            self._halted = True
            return None
        except RuntimeException as e:
            self._halted = True
            return str(e)
        except Exception as e:
            self._halted = True
            rex = RuntimeException(
                str(e),
                context=f"PC=0x{self._pc:08X}  {instr.raw_text}",
                line=instr.source_line,
            )
            return str(rex)

        return None

    def complete_input(self, value: str):
        """Resume execution after the user supplies syscall input."""
        req = self._pending_input
        if not req:
            return

        if req.kind == "int":
            try:
                n = int(value.strip())
            except ValueError as ex:
                raise RuntimeException(
                    f"Invalid integer: '{value}'", context="syscall 5 read_int"
                ) from ex
            self._set_reg(2, n)
            self._console += f"{n}\n"

        elif req.kind == "string":
            s = value[: max(0, req.max_len - 1)]
            addr = req.buffer_addr
            for i, ch in enumerate(s):
                self._memory[addr + i] = ord(ch) & 0xFF
            self._memory[addr + len(s)] = 0
            self._set_reg(2, len(s))
            self._console += s + "\n"

        elif req.kind == "float":
            try:
                f = float(value.strip())
            except ValueError as ex:
                raise RuntimeException(
                    f"Invalid float: '{value}'", context="syscall 6 read_float"
                ) from ex
            import struct
            bits = struct.unpack("I", struct.pack("f", f))[0]
            self._set_reg(2, bits)

        else:
            raise RuntimeException(f"Unknown input type: {req.kind}")

        self._pending_input = None
        self._pc += 4

    def _input_prompt(self) -> str:
        """Best-effort prompt from recent console output (e.g. print_string)."""
        text = self._console
        if not text:
            return "Enter value:"
        tail = text.split("\n")[-1]
        return tail if tail.strip() else "Enter value:"

    def run(self, max_steps: int = 100_000) -> Optional[str]:
        """
        Execute instructions until halt or max_steps reached.
        Returns error string or None.
        """
        for _ in range(max_steps):
            if self._halted:
                break
            if self._pc not in self._text_seg:
                self._halted = True
                break
            err = self.step()
            if err:
                return err
        return None

    def undo(self) -> bool:
        """Restore previous state. Returns True on success, False if nothing to undo."""
        if not self._undo_stack:
            return False
        self._restore(self._undo_stack.pop())
        self._changed_registers = set()
        return True

    def reset(self):
        """Full reset — clear all state."""
        self._registers     = [0] * 32
        self._registers[29] = STACK_BASE   # $sp
        self._pc            = TEXT_BASE
        self._hi            = 0
        self._lo            = 0
        self._memory        = {}
        self._text_seg      = {}
        self._data_seg_info = []
        self._labels        = {}
        self._console       = ""
        self._halted        = False
        self._running       = False
        self._undo_stack    = []
        self._changed_registers = set()
        self._errors        = []
        self._pending_input = None

    # ------------------------------------------------------------------
    # Instruction executor
    # ------------------------------------------------------------------

    def _execute(self, instr: ParsedInstruction):
        """Dispatch and execute a single ParsedInstruction, updating PC."""
        op   = instr.op
        args = instr.args
        pc   = self._pc
        next_pc = pc + 4   # default — overridden by branches/jumps

        # -------- Arithmetic / Logical --------

        if op == 'add':
            rd, rs, rt = _parse_register(args[0]), _parse_register(args[1]), _parse_register(args[2])
            result = self._get_reg(rs) + self._get_reg(rt)
            self._set_reg(rd, result)

        elif op == 'addu':
            rd, rs, rt = _parse_register(args[0]), _parse_register(args[1]), _parse_register(args[2])
            result = (self._registers[rs] + self._registers[rt]) & 0xFFFFFFFF
            self._set_reg(rd, result)

        elif op == 'sub':
            rd, rs, rt = _parse_register(args[0]), _parse_register(args[1]), _parse_register(args[2])
            self._set_reg(rd, self._get_reg(rs) - self._get_reg(rt))

        elif op == 'subu':
            rd, rs, rt = _parse_register(args[0]), _parse_register(args[1]), _parse_register(args[2])
            self._set_reg(rd, (self._registers[rs] - self._registers[rt]) & 0xFFFFFFFF)

        elif op == 'addi':
            rt, rs = _parse_register(args[0]), _parse_register(args[1])
            imm = _parse_immediate(args[2], self._labels)
            self._set_reg(rt, self._get_reg(rs) + imm)

        elif op == 'addiu':
            rt, rs = _parse_register(args[0]), _parse_register(args[1])
            imm = _parse_immediate(args[2], self._labels)
            self._set_reg(rt, (self._registers[rs] + imm) & 0xFFFFFFFF)

        elif op in ('and', 'and_'):
            rd, rs, rt = _parse_register(args[0]), _parse_register(args[1]), _parse_register(args[2])
            self._set_reg(rd, self._registers[rs] & self._registers[rt])

        elif op == 'andi':
            rt, rs = _parse_register(args[0]), _parse_register(args[1])
            imm = _parse_immediate(args[2], self._labels) & 0xFFFF
            self._set_reg(rt, self._registers[rs] & imm)

        elif op == 'or':
            rd, rs, rt = _parse_register(args[0]), _parse_register(args[1]), _parse_register(args[2])
            self._set_reg(rd, self._registers[rs] | self._registers[rt])

        elif op == 'ori':
            rt, rs = _parse_register(args[0]), _parse_register(args[1])
            imm = _parse_immediate(args[2], self._labels) & 0xFFFF
            self._set_reg(rt, self._registers[rs] | imm)

        elif op == 'xor':
            rd, rs, rt = _parse_register(args[0]), _parse_register(args[1]), _parse_register(args[2])
            self._set_reg(rd, self._registers[rs] ^ self._registers[rt])

        elif op == 'xori':
            rt, rs = _parse_register(args[0]), _parse_register(args[1])
            imm = _parse_immediate(args[2], self._labels) & 0xFFFF
            self._set_reg(rt, self._registers[rs] ^ imm)

        elif op == 'nor':
            rd, rs, rt = _parse_register(args[0]), _parse_register(args[1]), _parse_register(args[2])
            self._set_reg(rd, ~(self._registers[rs] | self._registers[rt]) & 0xFFFFFFFF)

        elif op == 'sll':
            rd, rt = _parse_register(args[0]), _parse_register(args[1])
            shamt = int(args[2]) & 0x1F
            self._set_reg(rd, (self._registers[rt] << shamt) & 0xFFFFFFFF)

        elif op == 'srl':
            rd, rt = _parse_register(args[0]), _parse_register(args[1])
            shamt = int(args[2]) & 0x1F
            self._set_reg(rd, (self._registers[rt] & 0xFFFFFFFF) >> shamt)

        elif op == 'sra':
            rd, rt = _parse_register(args[0]), _parse_register(args[1])
            shamt = int(args[2]) & 0x1F
            val = self._get_reg(rt)
            self._set_reg(rd, val >> shamt)

        elif op == 'sllv':
            rd, rt, rs = _parse_register(args[0]), _parse_register(args[1]), _parse_register(args[2])
            shamt = self._registers[rs] & 0x1F
            self._set_reg(rd, (self._registers[rt] << shamt) & 0xFFFFFFFF)

        elif op == 'srlv':
            rd, rt, rs = _parse_register(args[0]), _parse_register(args[1]), _parse_register(args[2])
            shamt = self._registers[rs] & 0x1F
            self._set_reg(rd, (self._registers[rt] & 0xFFFFFFFF) >> shamt)

        elif op == 'slt':
            rd, rs, rt = _parse_register(args[0]), _parse_register(args[1]), _parse_register(args[2])
            self._set_reg(rd, 1 if self._get_reg(rs) < self._get_reg(rt) else 0)

        elif op == 'sltu':
            rd, rs, rt = _parse_register(args[0]), _parse_register(args[1]), _parse_register(args[2])
            self._set_reg(rd, 1 if self._registers[rs] < self._registers[rt] else 0)

        elif op == 'slti':
            rt, rs = _parse_register(args[0]), _parse_register(args[1])
            imm = _parse_immediate(args[2], self._labels)
            self._set_reg(rt, 1 if self._get_reg(rs) < imm else 0)

        elif op == 'sltiu':
            rt, rs = _parse_register(args[0]), _parse_register(args[1])
            imm = _parse_immediate(args[2], self._labels) & 0xFFFFFFFF
            self._set_reg(rt, 1 if self._registers[rs] < imm else 0)

        elif op == 'mult':
            rs, rt = _parse_register(args[0]), _parse_register(args[1])
            result = self._get_reg(rs) * self._get_reg(rt)
            self._lo = result & 0xFFFFFFFF
            self._hi = (result >> 32) & 0xFFFFFFFF

        elif op == 'multu':
            rs, rt = _parse_register(args[0]), _parse_register(args[1])
            result = (self._registers[rs] & 0xFFFFFFFF) * (self._registers[rt] & 0xFFFFFFFF)
            self._lo = result & 0xFFFFFFFF
            self._hi = (result >> 32) & 0xFFFFFFFF

        elif op == 'div':
            rs, rt = _parse_register(args[0]), _parse_register(args[1])
            divisor = self._get_reg(rt)
            if divisor == 0:
                raise RuntimeException("Division by zero", context=instr.raw_text, line=instr.source_line)
            self._lo = int(self._get_reg(rs) / divisor)
            self._hi = self._get_reg(rs) % divisor

        elif op == 'mfhi':
            rd = _parse_register(args[0])
            self._set_reg(rd, self._hi)

        elif op == 'mflo':
            rd = _parse_register(args[0])
            self._set_reg(rd, self._lo)

        elif op == 'mthi':
            rs = _parse_register(args[0])
            self._hi = self._registers[rs]

        elif op == 'mtlo':
            rs = _parse_register(args[0])
            self._lo = self._registers[rs]

        elif op == 'lui':
            rt = _parse_register(args[0])
            imm = _parse_immediate(args[1], self._labels) & 0xFFFF
            self._set_reg(rt, (imm << 16) & 0xFFFFFFFF)

        elif op == 'move':
            # Pseudo-instruction: move $rd, $rs  → add $rd, $zero, $rs
            rd, rs = _parse_register(args[0]), _parse_register(args[1])
            self._set_reg(rd, self._registers[rs])

        elif op == 'li':
            # Pseudo-instruction: li $rt, imm
            rt = _parse_register(args[0])
            imm = _parse_immediate(args[1], self._labels)
            self._set_reg(rt, imm)

        elif op == 'la':
            # Pseudo-instruction: la $rt, label  — load address
            rt = _parse_register(args[0])
            addr_val = _parse_immediate(args[1], self._labels)
            self._set_reg(rt, addr_val)

        elif op == 'neg':
            rd, rs = _parse_register(args[0]), _parse_register(args[1])
            self._set_reg(rd, (-self._get_reg(rs)) & 0xFFFFFFFF)

        elif op == 'not':
            rd, rs = _parse_register(args[0]), _parse_register(args[1])
            self._set_reg(rd, (~self._registers[rs]) & 0xFFFFFFFF)

        # -------- Memory --------

        elif op == 'lw':
            rt = _parse_register(args[0])
            offset_s, base_s = _parse_mem_operand(args[1])
            base = _parse_register(base_s)
            offset = int(offset_s, 0) if offset_s.startswith('0x') or offset_s.startswith('-0x') else int(offset_s)
            addr = (self._registers[base] + offset) & 0xFFFFFFFF
            self._set_reg(rt, self.read_word(addr))

        elif op == 'sw':
            rt = _parse_register(args[0])
            offset_s, base_s = _parse_mem_operand(args[1])
            base = _parse_register(base_s)
            offset = int(offset_s, 0) if offset_s.startswith('0x') or offset_s.startswith('-0x') else int(offset_s)
            addr = (self._registers[base] + offset) & 0xFFFFFFFF
            self.write_word(addr, self._registers[rt])

        elif op == 'lb':
            rt = _parse_register(args[0])
            offset_s, base_s = _parse_mem_operand(args[1])
            base = _parse_register(base_s)
            offset = int(offset_s)
            addr = (self._registers[base] + offset) & 0xFFFFFFFF
            byte_val = self._memory.get(addr, 0) & 0xFF
            # Sign-extend byte
            if byte_val >= 0x80:
                byte_val -= 0x100
            self._set_reg(rt, byte_val)

        elif op == 'lbu':
            rt = _parse_register(args[0])
            offset_s, base_s = _parse_mem_operand(args[1])
            base = _parse_register(base_s)
            offset = int(offset_s)
            addr = (self._registers[base] + offset) & 0xFFFFFFFF
            self._set_reg(rt, self._memory.get(addr, 0) & 0xFF)

        elif op == 'sb':
            rt = _parse_register(args[0])
            offset_s, base_s = _parse_mem_operand(args[1])
            base = _parse_register(base_s)
            offset = int(offset_s)
            addr = (self._registers[base] + offset) & 0xFFFFFFFF
            self._memory[addr] = self._registers[rt] & 0xFF

        elif op == 'lh':
            rt = _parse_register(args[0])
            offset_s, base_s = _parse_mem_operand(args[1])
            base = _parse_register(base_s)
            offset = int(offset_s)
            addr = (self._registers[base] + offset) & 0xFFFFFFFF
            half = self._memory.get(addr, 0) & 0xFFFF
            if half >= 0x8000:
                half -= 0x10000
            self._set_reg(rt, half)

        elif op == 'sh':
            rt = _parse_register(args[0])
            offset_s, base_s = _parse_mem_operand(args[1])
            base = _parse_register(base_s)
            offset = int(offset_s)
            addr = (self._registers[base] + offset) & 0xFFFFFFFF
            self._memory[addr] = self._registers[rt] & 0xFFFF

        # -------- Branches --------

        elif op == 'beq':
            rs, rt = _parse_register(args[0]), _parse_register(args[1])
            target_s = args[2].strip()
            if self._registers[rs] == self._registers[rt]:
                if target_s in self._labels:
                    next_pc = self._labels[target_s]
                else:
                    offset = int(target_s)
                    next_pc = pc + 4 + (offset << 2)

        elif op == 'bne':
            rs, rt = _parse_register(args[0]), _parse_register(args[1])
            target_s = args[2].strip()
            if self._registers[rs] != self._registers[rt]:
                if target_s in self._labels:
                    next_pc = self._labels[target_s]
                else:
                    offset = int(target_s)
                    next_pc = pc + 4 + (offset << 2)

        elif op == 'blt':
            rs, rt = _parse_register(args[0]), _parse_register(args[1])
            target_s = args[2].strip()
            if self._get_reg(rs) < self._get_reg(rt):
                next_pc = self._labels[target_s] if target_s in self._labels else pc + 4 + (int(target_s) << 2)

        elif op == 'bgt':
            rs, rt = _parse_register(args[0]), _parse_register(args[1])
            target_s = args[2].strip()
            if self._get_reg(rs) > self._get_reg(rt):
                next_pc = self._labels[target_s] if target_s in self._labels else pc + 4 + (int(target_s) << 2)

        elif op == 'ble':
            rs, rt = _parse_register(args[0]), _parse_register(args[1])
            target_s = args[2].strip()
            if self._get_reg(rs) <= self._get_reg(rt):
                next_pc = self._labels[target_s] if target_s in self._labels else pc + 4 + (int(target_s) << 2)

        elif op == 'bge':
            rs, rt = _parse_register(args[0]), _parse_register(args[1])
            target_s = args[2].strip()
            if self._get_reg(rs) >= self._get_reg(rt):
                next_pc = self._labels[target_s] if target_s in self._labels else pc + 4 + (int(target_s) << 2)

        elif op == 'bgtz':
            rs = _parse_register(args[0])
            target_s = args[1].strip()
            if self._get_reg(rs) > 0:
                next_pc = self._labels[target_s] if target_s in self._labels else pc + 4 + (int(target_s) << 2)

        elif op == 'bltz':
            rs = _parse_register(args[0])
            target_s = args[1].strip()
            if self._get_reg(rs) < 0:
                next_pc = self._labels[target_s] if target_s in self._labels else pc + 4 + (int(target_s) << 2)

        elif op == 'bgez':
            rs = _parse_register(args[0])
            target_s = args[1].strip()
            if self._get_reg(rs) >= 0:
                next_pc = self._labels[target_s] if target_s in self._labels else pc + 4 + (int(target_s) << 2)

        elif op == 'blez':
            rs = _parse_register(args[0])
            target_s = args[1].strip()
            if self._get_reg(rs) <= 0:
                next_pc = self._labels[target_s] if target_s in self._labels else pc + 4 + (int(target_s) << 2)

        elif op == 'beqz':
            rs = _parse_register(args[0])
            target_s = args[1].strip()
            if self._registers[rs] == 0:
                next_pc = self._labels[target_s] if target_s in self._labels else pc + 4 + (int(target_s) << 2)

        elif op == 'bnez':
            rs = _parse_register(args[0])
            target_s = args[1].strip()
            if self._registers[rs] != 0:
                next_pc = self._labels[target_s] if target_s in self._labels else pc + 4 + (int(target_s) << 2)

        # -------- Jumps --------

        elif op == 'j':
            target_s = args[0].strip()
            if target_s in self._labels:
                next_pc = self._labels[target_s]
            else:
                next_pc = int(target_s, 0)

        elif op == 'jal':
            target_s = args[0].strip()
            self._set_reg(31, pc + 4)   # $ra = PC + 4
            if target_s in self._labels:
                next_pc = self._labels[target_s]
            else:
                next_pc = int(target_s, 0)

        elif op == 'jr':
            rs = _parse_register(args[0])
            next_pc = self._registers[rs] & 0xFFFFFFFF

        elif op == 'jalr':
            rs = _parse_register(args[0])
            self._set_reg(31, pc + 4)
            next_pc = self._registers[rs] & 0xFFFFFFFF

        # -------- Syscall --------

        elif op == 'syscall':
            self._handle_syscall()

        # -------- nop --------

        elif op == 'nop':
            pass

        # -------- break --------

        elif op == 'break':
            self._halted = True
            self._console += "\n[break instruction — execution halted]\n"
            self._pc = next_pc
            raise SystemExit("break")

        else:
            raise ValueError(f"Unrecognised instruction: '{op}'")

        self._pc = next_pc

    # ------------------------------------------------------------------
    # Syscall handler
    # ------------------------------------------------------------------

    def _handle_syscall(self):
        """
        Handle MIPS syscalls via $v0 (register 2).
          1  = print_int   ($a0 = integer)
          2  = print_float (not implemented)
          4  = print_string ($a0 = addr of null-terminated string)
          5  = read_int   (returns 0; interactive I/O not supported)
          10 = exit
          11 = print_char ($a0 = char code)
          17 = exit2      ($a0 = exit code)
        """
        code = self._registers[2]   # $v0

        if code == 1:
            # print_int
            val = self._get_reg(4)    # $a0
            self._console += str(val)

        elif code == 4:
            # print_string: read null-terminated bytes from $a0
            addr = self._registers[4]   # $a0
            s = ""
            for _ in range(4096):   # safety limit
                b = self._memory.get(addr, 0) & 0xFF
                if b == 0:
                    break
                s += chr(b)
                addr += 1
            self._console += s

        elif code == 5:
            raise SyscallInputRequired("int", self._input_prompt())

        elif code == 6:
            raise SyscallInputRequired("float", self._input_prompt())

        elif code == 8:
            raise SyscallInputRequired(
                "string", self._input_prompt(),
                buffer_addr=self._registers[4],
                max_len=max(1, self._registers[5] & 0xFFFFFFFF),
            )

        elif code == 10:
            # exit
            self._halted = True
            self._console += "\n[Program exited (syscall 10)]\n"
            raise SystemExit("syscall 10")

        elif code == 11:
            # print_char
            ch = self._registers[4] & 0xFF
            self._console += chr(ch)

        elif code == 17:
            # exit2
            code_val = self._get_reg(4)
            self._halted = True
            self._console += f"\n[Program exited with code {code_val} (syscall 17)]\n"
            raise SystemExit(f"syscall 17 code={code_val}")

        else:
            self._console += f"\n[Unsupported syscall: {code}]\n"

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def get_label_for_address(self, addr: int) -> Optional[str]:
        """Return the label name for a given address, or None."""
        for name, a in self._labels.items():
            if a == addr:
                return name
        return None

    def disassemble(self, addr: int) -> str:
        """Return the raw source text for the instruction at addr, or a placeholder."""
        if addr in self._text_seg:
            return self._text_seg[addr].raw_text
        return "<no instruction>"

    @property
    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    @property
    def undo_depth(self) -> int:
        return len(self._undo_stack)
