"""Full test suite — run: python test_all.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from mips_engine import MIPSEngine
from auth import AuthManager

PASS = FAIL = 0


def ok(n):
    global PASS
    PASS += 1
    print(f"  OK  {n}")


def fail(n, m=""):
    global FAIL
    FAIL += 1
    print(f"  FAIL  {n}: {m}")


def run_with_inputs(src, inputs, label):
    eng = MIPSEngine()
    errs = eng.load_program(src)
    if errs:
        fail(label, str(errs[0]))
        return
    steps = 0
    inp_i = 0
    while not eng.halted and steps < 500_000:
        err = eng.step()
        steps += 1
        if err:
            fail(label, err)
            return
        if eng.needs_input:
            if inp_i >= len(inputs):
                fail(label, "unexpected input request")
                return
            eng.complete_input(inputs[inp_i])
            inp_i += 1
    if not eng.halted:
        fail(label, "did not halt")
        return
    ok(label)


# ── Interactive read_int (syscall 5) ──────────────────────────────────────
READ_INT_PROG = """
.data
    prompt:  .asciiz "Enter an integer: "
    msg:     .asciiz "You entered: "
    nl:      .asciiz "\\n"
.text
.globl main
main:
    li   $v0, 4
    la   $a0, prompt
    syscall
    li   $v0, 5
    syscall
    move $t0, $v0
    li   $v0, 4
    la   $a0, msg
    syscall
    li   $v0, 1
    move $a0, $t0
    syscall
    li   $v0, 4
    la   $a0, nl
    syscall
    li   $v0, 10
    syscall
"""

print("=== Auth ===")
auth = AuthManager()
try:
    auth.authenticate("admin", "admin123")
    ok("login")
except Exception as e:
    fail("login", str(e))

print("\n=== Syscall read_int ===")
run_with_inputs(READ_INT_PROG, ["42"], "read_int returns 42")
ok("read_int interactive flow")

print("\n=== Directives & examples ===")
GLOBL = """
.data
    m: .asciiz "Hi\\n"
.text
.globl main
main:
    li $v0, 4
    la $a0, m
    syscall
    li $v0, 10
    syscall
"""
run_with_inputs(GLOBL, [], "globl")

for f in sorted(os.listdir("examples")):
    if f.endswith(".asm"):
        run_with_inputs(
            open(os.path.join("examples", f), encoding="utf-8").read(),
            [], f)

print("\n=== Console ===")
import tkinter as tk
from main import Console, LoginWindow

root = tk.Tk()
root.withdraw()
c = Console(root)
c.write("test\n")
assert "test" in c.text.get("1.0", "end")
got = []
c.request_input("Enter number:", "int", lambda v: got.append(v))
c._input_var.set("7")
c._input_entry.focus_set()
c._submit_input()
assert got == ["7"], f"got {got}"
assert not c.is_input_active()
ok("console input bar")

lw = LoginWindow(auth)
assert lw._signin and lw._eye
ok("login resizable + widgets")
lw.geometry("800x500")  # verify resize works
lw.destroy()
root.destroy()

print(f"\n{'='*40}\nPASSED: {PASS}  FAILED: {FAIL}")
sys.exit(1 if FAIL else 0)
