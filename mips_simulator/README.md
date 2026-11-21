# PyMIPS32 Studio

> A modern, dark-mode MIPS32 simulator for students and educators — built in Python as a better alternative to QtSpim.

![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)

---

## Table of Contents

- [Overview](#overview)
- [Screenshots](#screenshots)
- [Features](#features)
- [Supported Instructions](#supported-instructions)
- [Installation](#installation)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Architecture](#architecture)
- [Limitations](#limitations)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

**PyMIPS32 Studio** is a fully-featured MIPS32 simulator designed for use in Computer Organization and Assembly Language (COAL) courses. It provides a clean, modern alternative to QtSpim with an out-of-the-box dark theme, visual register tracking, and a unique **Undo Step** feature that lets you step *backward* through program execution.

The project is split into two clean modules:

| Module | Role |
|---|---|
| `mips_engine.py` | Pure-Python MIPS32 assembler + execution engine |
| `main.py` | Tkinter-based GUI frontend |

---

## Features

### ✅ Core Simulation
- **32 general-purpose registers** ($zero → $ra), HI, LO, and PC
- **Text segment** at `0x00400000` and **Data segment** at `0x10010000`
- Simulated **stack** initialized at `0x7FFFEFFC`
- Two-pass assembler with **label resolution** and `.data` / `.text` section support
- **Syscall support** (print_int, print_string, print_char, exit)

### 🎨 Modern UI
- **Dark mode** out of the box (no settings required)
- **Syntax highlighting** — opcodes, registers, immediates, labels, comments, directives all colour-coded
- **Line-numbered code editor** with cursor tracking
- **Real-time PC arrow** in both the editor and Text Segment viewer
- Tabbed **Memory Viewer** (Text Segment + Data Segment side-by-side)

### 🔬 Debugging
- **Step** — execute one instruction at a time (F10)
- **Run Continuous** — run until `syscall exit` or end of text (F5)
- **Pause** — interrupt continuous execution at any moment
- **↩ Undo Step** — step *backward* by replaying a cached state history (up to 200 steps) — **a feature QtSpim notoriously lacks**
- **Visual Register Flash** — registers that changed during a Step flash bright green for 800ms
- **Error highlighting** — assembly errors highlighted in red directly in the editor

### 📁 File Operations
- **Open** `.asm` / `.s` files (Ctrl+O)
- **Save** / **Save As** (Ctrl+S)
- **New** — blank template
- Built-in **Fibonacci sample program** loads on startup

---

## Supported Instructions

### Arithmetic & Logical
| Instruction | Description |
|---|---|
| `add`, `addu` | Signed/unsigned addition |
| `sub`, `subu` | Signed/unsigned subtraction |
| `addi`, `addiu` | Add immediate |
| `and`, `andi` | Bitwise AND |
| `or`, `ori` | Bitwise OR |
| `xor`, `xori` | Bitwise XOR |
| `nor` | Bitwise NOR |
| `sll`, `srl`, `sra` | Shift left/right logical/arithmetic |
| `sllv`, `srlv` | Variable shifts |
| `slt`, `sltu`, `slti`, `sltiu` | Set on less than |
| `mult`, `multu`, `div` | Multiply/divide (HI/LO) |
| `mfhi`, `mflo`, `mthi`, `mtlo` | Move from/to HI/LO |
| `lui` | Load upper immediate |

### Pseudo-Instructions
| Instruction | Expands to |
|---|---|
| `move $rd, $rs` | `add $rd, $zero, $rs` |
| `li $rt, imm` | Load immediate |
| `la $rt, label` | Load address |
| `neg $rd, $rs` | Negate |
| `not $rd, $rs` | Bitwise NOT |

### Memory
| Instruction | Description |
|---|---|
| `lw`, `sw` | Load/store word |
| `lh`, `sh` | Load/store halfword |
| `lb`, `lbu`, `sb` | Load/store byte (signed/unsigned) |

### Branch & Jump
| Instruction | Description |
|---|---|
| `beq`, `bne` | Branch if equal/not equal |
| `blt`, `bgt`, `ble`, `bge` | Pseudo branches |
| `bgtz`, `bltz`, `bgez`, `blez` | Branch on zero comparisons |
| `beqz`, `bnez` | Branch if zero/nonzero |
| `j`, `jal` | Jump / Jump and link |
| `jr`, `jalr` | Jump register |

### System
| Instruction | Description |
|---|---|
| `syscall` | System call via `$v0` |
| `nop` | No operation |
| `break` | Halt execution |

### Syscall Codes
| `$v0` | Operation | Args |
|---|---|---|
| 1 | Print integer | `$a0` = int |
| 4 | Print string | `$a0` = string address |
| 5 | Read integer | Returns in `$v0` (always 0 in this simulator) |
| 10 | Exit | — |
| 11 | Print character | `$a0` = char code |
| 17 | Exit with code | `$a0` = exit code |

---

## Installation

### Prerequisites
- Python 3.9 or newer
- `tkinter` (usually bundled with Python; see below if missing)

### Clone and Run

```bash
git clone https://github.com/yourusername/pymips32-studio.git
cd pymips32-studio
python main.py
```

No pip installs required — only the Python standard library is used.

### Tkinter Availability

| Platform | How to get tkinter |
|---|---|
| **Windows** | Included with the official Python installer from python.org |
| **macOS** | `brew install python-tk` (if using Homebrew Python) |
| **Ubuntu/Debian** | `sudo apt install python3-tk` |
| **Fedora/RHEL** | `sudo dnf install python3-tkinter` |
| **Arch** | `sudo pacman -S tk` |

---

## Usage

### Writing a Program

Type your MIPS assembly directly in the **Source Editor** panel. You can use:

```mips
.data
    message: .asciiz "Hello, MIPS!\n"

.text
main:
    li   $v0, 4        # syscall: print_string
    la   $a0, message
    syscall

    li   $v0, 10       # syscall: exit
    syscall
```

### Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| F4 | Assemble |
| F5 | Run |
| F10 | Step |
| F9 | Undo Step |
| Ctrl+O | Open file |
| Ctrl+S | Save file |

### Workflow

1. Write or load a `.asm` file
2. Click **⚙ Assemble** (or press F4)
3. Use **Step** (F10) to execute one instruction at a time
4. Watch registers flash green as they're written
5. Press **↩ Undo** (F9) to step backward
6. Press **▶ Run** (F5) for full continuous execution

---

## Project Structure

```
pymips32-studio/
│
├── main.py            # GUI frontend (Tkinter)
├── mips_engine.py     # MIPS32 assembler + execution engine
│
├── examples/
│   ├── fibonacci.asm
│   ├── bubble_sort.asm
│   └── hello_world.asm
│
├── requirements.txt   # (empty — stdlib only)
├── README.md
├── LICENSE
└── .gitignore
```

---

## Architecture

### Engine (`mips_engine.py`)

```
MIPSEngine
  ├── load_program(source)  → two-pass assembler
  │     ├── Pass 1: strip comments, split .data / .text, resolve data labels + allocate memory
  │     ├── Pass 1b: scan text for instruction labels
  │     └── Pass 2: decode instructions into ParsedInstruction objects
  │
  ├── step()       → execute one instruction + push undo snapshot
  ├── run()        → step loop until halted
  ├── undo()       → pop and restore from undo_stack
  └── reset()      → clear all state
```

### GUI (`main.py`)

```
PyMIPS32App (tk.Tk)
  ├── ToolBar           — file + execution buttons
  ├── PanedWindow (horizontal)
  │     ├── LineNumberedText  — code editor with syntax highlighting
  │     ├── RegisterPanel     — 32 registers + PC/HI/LO with flash animation
  │     └── MemoryPanel       — tabbed Text/Data segment views
  ├── ConsolePanel       — program stdout + status messages
  └── StatusBar          — PC value, status text, undo depth
```

### Undo System

Before each `step()`, the engine deep-copies the full simulator state (`SimulatorState` dataclass) onto a stack up to 200 entries deep. Calling `undo()` pops and restores the previous state — O(1) time, O(N·M) space where N = undo depth and M = memory footprint.

---

## Limitations

- **No floating-point** instructions (FPU / Coprocessor 1)
- **No exception/interrupt** handling
- **No delay slots** — branches take effect immediately
- `read_int` syscall (code 5) always returns 0 (no interactive stdin)
- **No real binary encoding** — the engine operates at the parsed-instruction level, not 32-bit machine words; this is intentional for clarity and speed

---

## Contributing

Pull requests are welcome. For major changes, open an issue first.

```bash
# Fork → clone → branch
git checkout -b feature/your-feature-name
# Make changes, then:
git commit -m "feat: describe your change"
git push origin feature/your-feature-name
# Open a Pull Request
```

---

## License

MIT © 2024 — see [LICENSE](LICENSE) for details.
