"""
PyMIPS32 Studio  —  Professional MIPS32 Simulator
===================================================
Author : PyMIPS32 Contributors
Python : 3.9+  |  tkinter only (stdlib)
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import sys
import re
import traceback

try:
    from mips_engine import MIPSEngine, REGISTER_NAMES, TEXT_BASE, DATA_BASE
    from auth import AuthManager
    from exceptions import (
        MIPSStudioError, AuthException, FileOperationException,
        SimulatorStateException,
    )
except ImportError as ex:
    sys.exit(f"ERROR: missing module — {ex}")

# ══════════════════════════════════════════════════════════════════════════════
#  CURSOR / UE5-INSPIRED DARK THEME
# ══════════════════════════════════════════════════════════════════════════════
T = {
    "win":        "#181818",
    "tb":         "#181818",
    "tb_fg":      "#E8E8E8",
    "tb_muted":   "#858585",
    "tb_hover":   "#2d2d2d",
    "tb_active":  "#3c3c3c",
    "panel":      "#1f1f1f",
    "editor":     "#1e1e1e",
    "row_a":      "#252526",
    "row_b":      "#1e1e1e",
    "hover":      "#2a2d2e",
    "sel":        "#264f78",
    "input":      "#3c3c3c",
    "input_bg":   "#252526",
    "input_fg":   "#ffffff",
    "input_bd":   "#007acc",
    "bd":         "#3c3c3c",
    "bd2":        "#454545",
    "fg":         "#d4d4d4",
    "fg1":        "#9d9d9d",
    "fg2":        "#6e6e6e",
    "blue":       "#3794ff",
    "cyan":       "#4ec9b0",
    "green":      "#4ec9b0",
    "yellow":     "#dcdcaa",
    "orange":     "#ce9178",
    "red":        "#f44747",
    "purple":     "#c586c0",
    "teal":       "#4ec9b0",
    "accent":     "#007acc",
    "accent2":    "#7c3aed",
    "btn_pri":    "#0e639c",
    "btn_run":    "#16825d",
    "btn_warn":   "#bc7c0f",
    "btn_dan":    "#9c2727",
    "sash":       "#454545",
    "hdr":        "#252526",
    "console_bg": "#0d0d0d",
    "console_fg": "#cccccc",
    "s_kw":       "#569cd6",
    "s_ps":       "#c586c0",
    "s_reg":      "#9cdcfe",
    "s_imm":      "#b5cea8",
    "s_lbl":      "#dcdcaa",
    "s_dir":      "#c586c0",
    "s_cmt":      "#6a9955",
    "s_str":      "#ce9178",
    "s_err":      "#5a1d1d",
    "pc":         "#264f78",
}

if sys.platform == "win32":
    MONO, UI = "Consolas", "Segoe UI"
elif sys.platform == "darwin":
    MONO, UI = "Menlo", "SF Pro Display"
else:
    MONO, UI = "DejaVu Sans Mono", "Ubuntu"

FLASH_MS   = 700
RUN_DELAY  = 25          # ms between instructions during Run (visible execution)
STEP_POPUP = False       # step uses status bar; run shows live updates

OPCODES = {"add","addu","sub","subu","addi","addiu","and","andi","or","ori",
           "xor","xori","nor","sll","srl","sra","sllv","srlv","slt","sltu",
           "slti","sltiu","mult","multu","div","mfhi","mflo","mthi","mtlo",
           "lui","lw","sw","lb","lbu","sb","lh","sh",
           "beq","bne","blt","bgt","ble","bge","bgtz","bltz","bgez","blez",
           "beqz","bnez","j","jal","jr","jalr","syscall","nop","break"}
PSEUDOS  = {"move","li","la","neg","not"}
DIRECTS  = {".text",".data",".word",".half",".byte",".asciiz",
            ".ascii",".space",".globl",".align",".extern",".ent",".end"}

SAMPLE = """\
# PyMIPS32 Studio — Fibonacci Demo (fib(10) = 55)

.data
    msg_pre:  .asciiz  "Fibonacci(10) = "
    msg_nl:   .asciiz  "\\n"

.text
.globl main
main:
    li    $a0, 10
    jal   fib
    move  $s0, $v0

    li    $v0, 4
    la    $a0, msg_pre
    syscall

    li    $v0, 1
    move  $a0, $s0
    syscall

    li    $v0, 4
    la    $a0, msg_nl
    syscall

    li    $v0, 10
    syscall

fib:
    addi  $sp, $sp, -12
    sw    $ra,  8($sp)
    sw    $s0,  4($sp)
    sw    $a0,  0($sp)

    slti  $t0, $a0, 2
    beq   $t0, $zero, fib_recurse
    move  $v0, $a0
    j     fib_ret

fib_recurse:
    addi  $a0, $a0, -1
    jal   fib
    move  $s0, $v0

    lw    $a0,  0($sp)
    addi  $a0, $a0, -2
    jal   fib

    add   $v0, $v0, $s0

fib_ret:
    lw    $ra,  8($sp)
    lw    $s0,  4($sp)
    addi  $sp, $sp, 12
    jr    $ra
"""


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def hline(parent, color=None, pady=0):
    tk.Frame(parent, height=1, bg=color or T["bd"]).pack(fill="x", pady=pady)


def show_error(parent, title: str, exc: Exception):
    """Display a detailed error pop-up with traceback for debugging."""
    if isinstance(exc, MIPSStudioError):
        detail = str(exc)
        if exc.context:
            detail += f"\n\nContext: {exc.context}"
        if exc.line:
            detail += f"\nLine: {exc.line}"
    else:
        detail = f"{type(exc).__name__}: {exc}"
    tb = traceback.format_exc()
    if tb and "Traceback" in tb:
        detail += f"\n\n── Traceback ──\n{tb}"
    messagebox.showerror(title, detail, parent=parent)


def show_info(parent, title: str, message: str):
    messagebox.showinfo(title, message, parent=parent)


def show_warn(parent, title: str, message: str):
    messagebox.showwarning(title, message, parent=parent)


# ══════════════════════════════════════════════════════════════════════════════
#  LOGIN WINDOW
# ══════════════════════════════════════════════════════════════════════════════

def _center_window(win, width: int, height: int):
    win.update_idletasks()
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    x = max(0, (sw - width) // 2)
    y = max(0, (sh - height) // 2)
    win.geometry(f"{width}x{height}+{x}+{y}")
    win.lift()
    win.attributes("-topmost", True)
    win.after(400, lambda: win.attributes("-topmost", False))
    win.focus_force()


class LoginWindow(tk.Tk):
    """Standalone login — full layout with branding panel, eye toggle, styled buttons."""

    WIN_W, WIN_H = 720, 460

    def __init__(self, auth: AuthManager):
        super().__init__()
        self.title("PyMIPS32 Studio")
        self.resizable(True, True)
        self.minsize(640, 420)
        self.geometry(f"{self.WIN_W}x{self.WIN_H}")
        self.configure(bg="#0a0a0a")
        self._auth = auth
        self.logged_in = False
        self.username = ""
        self._pass_visible = False

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        root = tk.Frame(self, bg="#0a0a0a")
        root.pack(fill="both", expand=True, padx=20, pady=20)

        shell = tk.Frame(root, bg="#1f1f1f", highlightbackground="#3c3c3c",
                         highlightthickness=1)
        shell.pack(fill="both", expand=True)
        shell.grid_columnconfigure(0, weight=2, minsize=220)
        shell.grid_columnconfigure(1, weight=3, minsize=280)
        shell.grid_rowconfigure(0, weight=1)

        # ── Left brand panel ────────────────────────────────────────────────
        left = tk.Frame(shell, bg="#141414")
        left.grid(row=0, column=0, sticky="nsew")
        left.grid_rowconfigure(1, weight=1)

        brand_top = tk.Frame(left, bg="#141414")
        brand_top.pack(fill="both", expand=True)

        tk.Label(brand_top, text="PyMIPS32", bg="#141414", fg="#ffffff",
                 font=(UI, 28, "bold")).pack(pady=(36, 0), padx=32, anchor="w")
        tk.Label(brand_top, text="Studio", bg="#141414", fg=T["accent"],
                 font=(UI, 24)).pack(padx=32, anchor="w")
        tk.Label(brand_top, text="MIPS32 IDE & Simulator",
                 bg="#141414", fg="#858585", font=(UI, 11)).pack(
                     padx=32, pady=(12, 0), anchor="w")
        tk.Frame(brand_top, bg=T["accent2"], height=2).pack(
            fill="x", padx=32, pady=20)
        for feat in ("Interactive syscall I/O", "Live debug & undo",
                     "Register / memory views"):
            tk.Label(brand_top, text=f"  {feat}", bg="#141414", fg="#6e6e6e",
                     font=(UI, 9)).pack(padx=32, anchor="w", pady=3)

        tk.Label(left, text=f"  {auth.backend_name}",
                 bg="#141414", fg="#505050", font=(UI, 8)).pack(
                     side="bottom", padx=32, pady=14, anchor="w")

        right = tk.Frame(shell, bg="#1f1f1f")
        right.grid(row=0, column=1, sticky="nsew", padx=40, pady=36)

        tk.Label(right, text="Sign in", bg="#1f1f1f", fg="#ffffff",
                 font=(UI, 22, "bold")).pack(anchor="w")
        tk.Label(right, text="Sign in to open the simulator",
                 bg="#1f1f1f", fg="#858585", font=(UI, 10)).pack(
                     anchor="w", pady=(4, 24))

        def _field(parent, label, show=None):
            tk.Label(parent, text=label, bg="#1f1f1f", fg="#9d9d9d",
                     font=(UI, 9)).pack(anchor="w")
            wrap = tk.Frame(parent, bg="#3c3c3c", padx=1, pady=1)
            wrap.pack(fill="x", pady=(6, 16))
            e = tk.Entry(wrap, font=(UI, 12), bg="#252526", fg="#ffffff",
                         insertbackground="#ffffff", relief="flat", bd=0,
                         highlightthickness=0, show=show or "")
            e.pack(fill="x", ipady=10, padx=2, pady=2)
            return e

        self._user = _field(right, "Username")
        self._user.insert(0, "admin")

        tk.Label(right, text="Password", bg="#1f1f1f", fg="#9d9d9d",
                 font=(UI, 9)).pack(anchor="w")
        pass_outer = tk.Frame(right, bg="#3c3c3c", padx=1, pady=1)
        pass_outer.pack(fill="x", pady=(6, 8))
        pass_row = tk.Frame(pass_outer, bg="#252526")
        pass_row.pack(fill="x", padx=2, pady=2)
        self._pass = tk.Entry(pass_row, font=(UI, 12), show="●", bg="#252526",
                               fg="#ffffff", insertbackground="#ffffff",
                               relief="flat", bd=0, highlightthickness=0)
        self._pass.pack(side="left", fill="x", expand=True, ipady=10, padx=(8, 0))
        self._pass.insert(0, "admin123")
        self._eye = tk.Label(pass_row, text="👁", bg="#252526", fg="#858585",
                              font=(UI, 14), cursor="hand2", padx=12)
        self._eye.pack(side="right")
        self._eye.bind("<Button-1>", lambda e: self._toggle_password())
        self._eye.bind("<Enter>", lambda e: self._eye.config(fg=T["accent"]))
        self._eye.bind("<Leave>", lambda e: self._eye.config(fg="#858585"))

        tk.Label(right, text="admin / admin123  ·  student / mips2024",
                 bg="#1f1f1f", fg="#505050", font=(UI, 8)).pack(
                     anchor="w", pady=(0, 20))

        self._signin = tk.Button(
            right, text="Sign In  →", font=(UI, 11, "bold"),
            bg=T["accent"], fg="#ffffff", activebackground="#1a8ad4",
            activeforeground="#ffffff", relief="flat", bd=0,
            cursor="hand2", pady=12, command=self._do_login,
        )
        self._signin.pack(fill="x", pady=(0, 8))

        tk.Button(right, text="Cancel", font=(UI, 10),
                  bg="#1f1f1f", fg="#858585", activebackground="#2d2d2d",
                  relief="flat", bd=0, cursor="hand2", pady=8,
                  command=self._on_close).pack(fill="x")

        self._pass.bind("<Return>", lambda e: self._do_login())
        self._user.bind("<Return>", lambda e: self._pass.focus_set())
        self._user.focus_set()

        _center_window(self, self.WIN_W, self.WIN_H)

    def _toggle_password(self):
        self._pass_visible = not self._pass_visible
        self._pass.config(show="" if self._pass_visible else "●")
        self._eye.config(text="🙈" if self._pass_visible else "👁")

    def _do_login(self):
        try:
            user = self._user.get().strip()
            self._auth.authenticate(user, self._pass.get())
            self.logged_in = True
            self.username = user
            self.quit()
        except AuthException as ex:
            show_error(self, "Login Failed", ex)
        except Exception as ex:
            show_error(self, "Login Error", ex)

    def _on_close(self):
        self.logged_in = False
        self.quit()


# ══════════════════════════════════════════════════════════════════════════════
#  TOOLBAR BUTTON  — compact, text-only, dark bar
# ══════════════════════════════════════════════════════════════════════════════

class ToolBtn(tk.Label):
    """Flat toolbar control. Uses tk.Label (not Frame) to avoid _w conflicts."""

    STYLES = {
        "default": ("#2d2d2d", "#cccccc"),
        "primary": ("#0e639c", "#ffffff"),
        "run":     ("#16825d", "#ffffff"),
        "warn":    ("#bc7c0f", "#ffffff"),
        "danger":  ("#9c2727", "#ffffff"),
    }

    def __init__(self, parent, label, shortcut, cmd, style="default", disabled=False):
        bg, fg = self.STYLES.get(style, self.STYLES["default"])
        super().__init__(
            parent, text=f"{label}",
            bg=bg, fg=fg, font=(UI, 9),
            padx=12, pady=6, cursor="hand2",
            relief="flat", bd=0,
        )
        self._cmd = cmd
        self._enabled = not disabled
        self._style = style
        self._bg = bg
        self._fg = fg
        self._shortcut = shortcut

        tip = f"{label}  ({shortcut})" if shortcut else label
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self._tip = tip

    def _on_enter(self, _=None):
        if not self._enabled:
            return
        self.config(bg=T["tb_hover"])

    def _on_leave(self, _=None):
        if not self._enabled:
            return
        bg, _ = self.STYLES.get(self._style, self.STYLES["default"])
        self.config(bg=bg)

    def _on_click(self, _=None):
        if self._enabled:
            self._cmd()

    def set_enabled(self, yes: bool):
        self._enabled = yes
        if yes:
            bg, fg = self.STYLES.get(self._style, self.STYLES["default"])
            self.config(bg=bg, fg=fg, cursor="hand2")
        else:
            self.config(bg=T["tb_active"], fg=T["tb_muted"], cursor="arrow")


# ══════════════════════════════════════════════════════════════════════════════
#  PANEL HEADER  (draggable title bar style)
# ══════════════════════════════════════════════════════════════════════════════

class PanelHeader(tk.Frame):
    def __init__(self, parent, title, accent):
        super().__init__(parent, bg=T["hdr"])
        self.pack(fill="x")
        tk.Frame(self, width=2, bg=accent).pack(side="left", fill="y")
        tk.Label(self, text=f"  {title}", bg=T["hdr"], fg=T["fg"],
                 font=(UI, 9, "bold"), pady=7).pack(side="left")


# ══════════════════════════════════════════════════════════════════════════════
#  CODE EDITOR
# ══════════════════════════════════════════════════════════════════════════════

class CodeEditor(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=T["editor"])

        self._gutter = tk.Text(
            self, width=4, state="disabled",
            bg=T["row_a"], fg=T["fg2"],
            font=(MONO, 11), relief="flat", bd=0,
            padx=8, pady=6, cursor="arrow", highlightthickness=0,
        )
        self._gutter.pack(side="left", fill="y")
        tk.Frame(self, width=1, bg=T["bd"]).pack(side="left", fill="y")

        self.text = tk.Text(
            self, bg=T["editor"], fg=T["fg"], font=(MONO, 11),
            insertbackground=T["blue"], selectbackground=T["sel"],
            relief="flat", bd=0, padx=14, pady=6, undo=True, wrap="none",
            highlightthickness=0, spacing1=2, spacing3=2,
        )
        vsb = ttk.Scrollbar(self, orient="vertical", command=self._yscroll)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self.text.xview)
        self.text.config(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self.text.pack(side="left", fill="both", expand=True)

        cfg = self.text.tag_configure
        cfg("kw",  foreground=T["s_kw"],  font=(MONO, 11, "bold"))
        cfg("ps",  foreground=T["s_ps"],  font=(MONO, 11, "bold"))
        cfg("reg", foreground=T["s_reg"])
        cfg("imm", foreground=T["s_imm"])
        cfg("lbl", foreground=T["s_lbl"], font=(MONO, 11, "bold"))
        cfg("dir", foreground=T["s_dir"])
        cfg("cmt", foreground=T["s_cmt"], font=(MONO, 11, "italic"))
        cfg("str", foreground=T["s_str"])
        cfg("pc",  background=T["pc"], foreground="#ffffff")
        cfg("err", background=T["s_err"], foreground=T["red"])

        self.text.bind("<KeyRelease>",    self._on_change)
        self.text.bind("<ButtonRelease>", self._on_change)
        self._gutter.bind("<MouseWheel>", self._wheel)
        self.text.bind("<MouseWheel>",    self._wheel)
        self._hl_job = None

    def _yscroll(self, *a):
        self.text.yview(*a)
        self._gutter.yview(*a)

    def _wheel(self, e):
        delta = -1 * (e.delta // 120) if e.delta else (-1 if e.num == 4 else 1)
        self.text.yview_scroll(delta, "units")
        self._gutter.yview_scroll(delta, "units")
        return "break"

    def _on_change(self, _=None):
        self._update_gutter()
        if self._hl_job:
            self.after_cancel(self._hl_job)
        self._hl_job = self.after(80, self._do_highlight)

    def _update_gutter(self):
        n = int(self.text.index("end-1c").split(".")[0])
        self._gutter.config(state="normal")
        self._gutter.delete("1.0", "end")
        self._gutter.insert("1.0", "\n".join(f"{i:>3}" for i in range(1, n + 1)))
        self._gutter.config(state="disabled")
        self._gutter.yview_moveto(self.text.yview()[0])

    def _do_highlight(self):
        t = self.text
        for tag in ("kw", "ps", "reg", "imm", "lbl", "dir", "cmt", "str"):
            t.tag_remove(tag, "1.0", "end")
        lines = t.get("1.0", "end-1c").split("\n")
        for ln, line in enumerate(lines, 1):
            ci = line.find("#")
            if ci >= 0:
                t.tag_add("cmt", f"{ln}.{ci}", f"{ln}.end")
                eff = line[:ci]
            else:
                eff = line
            for m in re.finditer(r'"[^"]*"', eff):
                t.tag_add("str", f"{ln}.{m.start()}", f"{ln}.{m.end()}")
            stripped = eff.strip().lower()
            for d in DIRECTS:
                if stripped.startswith(d):
                    p = eff.lower().find(d)
                    if p >= 0:
                        t.tag_add("dir", f"{ln}.{p}", f"{ln}.{p + len(d)}")
            for m in re.finditer(r'\b([A-Za-z_]\w*)\s*:', eff):
                t.tag_add("lbl", f"{ln}.{m.start()}", f"{ln}.{m.start() + len(m.group(1))}")
            after = re.sub(r'^[A-Za-z_]\w*\s*:', '', eff)
            base  = len(eff) - len(after)
            toks  = re.split(r'[\s,()]+', after.strip())
            col   = base
            for i, tok in enumerate(toks):
                if not tok:
                    continue
                tc  = tok.lower()
                pos = eff.lower().find(tc, col)
                if pos < 0:
                    continue
                end = pos + len(tc)
                if i == 0:
                    if tc in OPCODES:
                        t.tag_add("kw", f"{ln}.{pos}", f"{ln}.{end}")
                    elif tc in PSEUDOS:
                        t.tag_add("ps", f"{ln}.{pos}", f"{ln}.{end}")
                else:
                    if tok.startswith("$"):
                        t.tag_add("reg", f"{ln}.{pos}", f"{ln}.{end}")
                    elif re.match(r'^-?(0x[\da-fA-F]+|\d+)$', tc):
                        t.tag_add("imm", f"{ln}.{pos}", f"{ln}.{end}")
                col = end

    def get(self):
        return self.text.get("1.0", "end-1c")

    def set(self, s):
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", s)
        self._on_change()

    def mark_pc(self, lineno):
        self.text.tag_remove("pc", "1.0", "end")
        if lineno and lineno > 0:
            self.text.tag_add("pc", f"{lineno}.0", f"{lineno}.end+1c")
            self.text.see(f"{lineno}.0")

    def mark_err(self, lineno):
        if lineno > 0:
            self.text.tag_add("err", f"{lineno}.0", f"{lineno}.end+1c")

    def clear_marks(self):
        self.text.tag_remove("pc",  "1.0", "end")
        self.text.tag_remove("err", "1.0", "end")


# ══════════════════════════════════════════════════════════════════════════════
#  REGISTER TABLE
# ══════════════════════════════════════════════════════════════════════════════

class RegTable(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=T["panel"])
        PanelHeader(self, "Integer Registers", T["blue"])
        hline(self)

        hdr = tk.Frame(self, bg=T["panel"])
        hdr.pack(fill="x")
        self._badge = tk.Label(hdr, text="● IDLE", bg=T["panel"],
                                fg=T["fg2"], font=(UI, 8, "bold"))
        self._badge.pack(side="right", padx=10, pady=4)

        ch = tk.Frame(self, bg=T["row_a"])
        ch.pack(fill="x")
        for txt, w, anc in [("  #", 4, "e"), ("Reg", 5, "w"),
                             ("Hex Value", 10, "w"), ("Decimal", 10, "w")]:
            tk.Label(ch, text=txt, width=w, bg=T["row_a"], fg=T["fg1"],
                     font=(UI, 8, "bold"), anchor=anc, padx=5, pady=4).pack(side="left")
        hline(self)

        wrap = tk.Frame(self, bg=T["panel"])
        wrap.pack(fill="both", expand=True)
        cv = tk.Canvas(wrap, bg=T["panel"], highlightthickness=0, bd=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=cv.yview)
        sb.pack(side="right", fill="y")
        cv.pack(fill="both", expand=True)
        cv.configure(yscrollcommand=sb.set)

        inner = tk.Frame(cv, bg=T["panel"])
        win = cv.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.bind("<Configure>", lambda e: cv.itemconfig(win, width=e.width))
        cv.bind("<MouseWheel>", lambda e: cv.yview_scroll(-1 * (e.delta // 120), "units"))

        all_names = list(REGISTER_NAMES) + ["PC", "HI", "LO"]
        self._rows = []
        for i, name in enumerate(all_names):
            bg  = T["row_a"] if i % 2 == 0 else T["row_b"]
            row = tk.Frame(inner, bg=bg)
            row.pack(fill="x")
            numstr = f"${i}" if i < 32 else name
            ln = tk.Label(row, text=numstr, width=4, bg=bg, fg=T["fg2"],
                           font=(MONO, 9), anchor="e", padx=4, pady=3)
            ll = tk.Label(row, text=name, width=5, bg=bg, fg=T["fg1"],
                           font=(MONO, 9, "bold"), anchor="w", padx=3)
            lh = tk.Label(row, text="0x00000000", width=12, bg=bg,
                           fg=T["cyan"], font=(MONO, 9), anchor="w")
            ld = tk.Label(row, text="0", width=11, bg=bg, fg=T["fg"],
                           font=(MONO, 9), anchor="w")
            ln.pack(side="left")
            ll.pack(side="left")
            lh.pack(side="left")
            ld.pack(side="left")
            self._rows.append((ln, ll, lh, ld, row, bg))
        self._jobs = {}

    def set_badge(self, text, color):
        self._badge.config(text=text, fg=color)

    def refresh(self, regs, pc, hi, lo, changed):
        vals = list(regs) + [pc, hi, lo]
        for i, (v, row_data) in enumerate(zip(vals, self._rows)):
            _, _, lh, ld, row, obg = row_data
            u = v & 0xFFFFFFFF
            s = u if u < 0x80000000 else u - 0x100000000
            lh.config(text=f"0x{u:08X}")
            ld.config(text=str(s))
            if i in changed:
                self._flash(i, row, lh, ld, obg)

    def _flash(self, idx, row, lh, ld, obg):
        if idx in self._jobs:
            try:
                row.after_cancel(self._jobs[idx])
            except tk.TclError:
                pass
        for w in (row, lh, ld, *row.winfo_children()):
            try:
                w.config(bg=T["green"])
            except tk.TclError:
                pass
        lh.config(fg="#FFFFFF")
        ld.config(fg="#FFFFFF")

        def _rst():
            for w in (row, *row.winfo_children()):
                try:
                    w.config(bg=obg)
                except tk.TclError:
                    pass
            lh.config(fg=T["cyan"])
            ld.config(fg=T["fg"])
            self._jobs.pop(idx, None)

        self._jobs[idx] = row.after(FLASH_MS, _rst)


# ══════════════════════════════════════════════════════════════════════════════
#  MEMORY VIEWER
# ══════════════════════════════════════════════════════════════════════════════

class MemViewer(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=T["panel"])
        PanelHeader(self, "Memory", T["cyan"])
        hline(self)

        tabbar = tk.Frame(self, bg=T["row_a"])
        tabbar.pack(fill="x")
        self._tabs  = {}
        self._pages = {}
        for key, lbl in [("text", "  Text Segment  "), ("data", "  Data Segment  ")]:
            b = tk.Label(tabbar, text=lbl, bg=T["row_a"], fg=T["fg1"],
                         font=(UI, 9), padx=8, pady=6, cursor="hand2")
            b.pack(side="left")
            b.bind("<Button-1>", lambda e, k=key: self._show(k))
            self._tabs[key] = b
        hline(self)

        body = tk.Frame(self, bg=T["panel"])
        body.pack(fill="both", expand=True)

        for key in ("text", "data"):
            f = tk.Frame(body, bg=T["panel"])
            t = tk.Text(f, bg=T["editor"], fg=T["fg"], font=(MONO, 9),
                        state="disabled", relief="flat", bd=0,
                        padx=10, pady=6, highlightthickness=0, wrap="none")
            vs = ttk.Scrollbar(f, orient="vertical", command=t.yview)
            hs = ttk.Scrollbar(f, orient="horizontal", command=t.xview)
            t.config(yscrollcommand=vs.set, xscrollcommand=hs.set)
            vs.pack(side="right", fill="y")
            hs.pack(side="bottom", fill="x")
            t.pack(fill="both", expand=True)
            t.tag_configure("hd",  foreground=T["fg1"])
            t.tag_configure("pc",  background=T["sel"], foreground=T["blue"])
            t.tag_configure("adr", foreground=T["fg2"])
            t.tag_configure("val", foreground=T["cyan"])
            t.tag_configure("op",  foreground=T["s_kw"])
            t.tag_configure("asc", foreground=T["s_str"])
            self._pages[key] = (f, t)
        self._show("text")

    def _show(self, key):
        for k, (f, _) in self._pages.items():
            f.pack_forget()
        for k, b in self._tabs.items():
            b.config(bg=T["row_a"], fg=T["fg1"])
        self._pages[key][0].pack(fill="both", expand=True)
        self._tabs[key].config(bg=T["editor"], fg=T["blue"])

    def _write(self, key, segments):
        _, t = self._pages[key]
        t.config(state="normal")
        t.delete("1.0", "end")
        for text, tag in segments:
            t.insert("end", text, tag)
        t.config(state="disabled")

    def update_text(self, seg, pc):
        rows = [("  Addr           Machine / Instruction\n", "hd"),
                ("  " + "─" * 52 + "\n", "hd")]
        for addr in sorted(seg):
            instr = seg[addr]
            arrow = "► " if addr == pc else "  "
            line  = f"{arrow}0x{addr:08X}   {instr.raw_text}\n"
            tag   = "pc" if addr == pc else "op"
            rows.append((line, tag))
        self._write("text", rows)
        _, t = self._pages["text"]
        content = t.get("1.0", "end")
        for i, ln in enumerate(content.split("\n"), 1):
            if "►" in ln:
                t.config(state="normal")
                t.see(f"{i}.0")
                t.config(state="disabled")
                break

    def update_data(self, mem, base=DATA_BASE, count=80):
        rows = [("  Address         Hex           UInt32       ASCII\n", "hd"),
                ("  " + "─" * 58 + "\n", "hd")]
        addrs = sorted(set(range(base, base + 32 * 4, 4)) |
                       {a for a in mem if base <= a < base + count * 4})
        for addr in addrs[:count]:
            val = mem.get(addr, 0) & 0xFFFFFFFF
            b   = [(val >> sh) & 0xFF for sh in (24, 16, 8, 0)]
            asc = "".join(chr(x) if 32 <= x < 127 else "." for x in b)
            rows += [
                (f"  0x{addr:08X}  ", "adr"),
                (f"0x{val:08X}  ", "val"),
                (f"{val:>12}   ", "val"),
                (f"{asc}\n", "asc"),
            ]
        self._write("data", rows)


# ══════════════════════════════════════════════════════════════════════════════
#  CONSOLE
# ══════════════════════════════════════════════════════════════════════════════

class Console(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=T["console_bg"])
        self._input_cb = None
        self._input_kind = "int"
        self._input_active = False

        # ── INPUT BAR (top — always visible, highlighted when active) ───────
        self._in_wrap = tk.Frame(self, bg="#1a1a1a", height=54)
        self._in_wrap.pack(fill="x", side="top")
        self._in_wrap.pack_propagate(False)

        in_inner = tk.Frame(self._in_wrap, bg="#252526",
                            highlightbackground="#3c3c3c", highlightthickness=1)
        in_inner.pack(fill="both", expand=True, padx=8, pady=6)

        top_row = tk.Frame(in_inner, bg="#252526")
        top_row.pack(fill="x", padx=8, pady=(6, 2))
        self._prompt_lbl = tk.Label(top_row, text="INPUT",
                                     bg="#252526", fg="#858585",
                                     font=(UI, 8, "bold"))
        self._prompt_lbl.pack(side="left")
        self._state_lbl = tk.Label(top_row, text="● idle", bg="#252526",
                                    fg="#6e6e6e", font=(UI, 8))
        self._state_lbl.pack(side="right")

        entry_row = tk.Frame(in_inner, bg="#252526")
        entry_row.pack(fill="x", padx=8, pady=(0, 6))

        self._input_var = tk.StringVar()
        self._input_entry = tk.Entry(
            entry_row, textvariable=self._input_var, font=(MONO, 13),
            bg="#1e1e1e", fg="#ffffff", insertbackground="#ffffff",
            relief="flat", bd=0, state="disabled",
            highlightthickness=2, highlightbackground="#3c3c3c",
            highlightcolor="#3c3c3c",
        )
        self._input_entry.pack(side="left", fill="x", expand=True, ipady=8)

        self._submit_btn = tk.Button(
            entry_row, text="Enter ↵", font=(UI, 9, "bold"),
            bg="#0e639c", fg="#ffffff", activebackground="#1177bb",
            relief="flat", bd=0, padx=16, pady=6, state="disabled",
            cursor="hand2", command=self._submit_input,
        )
        self._submit_btn.pack(side="right", padx=(8, 0))

        self._input_entry.bind("<Return>", self._on_entry_return)
        # Block simulator shortcuts from firing while the entry has focus
        for seq in ("<F4>", "<F5>", "<F6>", "<F8>", "<F9>", "<F10>",
                    "<Control-r>", "<Control-p>"):
            self._input_entry.bind(seq, self._stop_propagation, add="+")

        # ── Terminal output ─────────────────────────────────────────────────
        bar = tk.Frame(self, bg="#141414")
        bar.pack(fill="x")
        tk.Frame(bar, width=2, bg=T["accent"]).pack(side="left", fill="y")
        tk.Label(bar, text="  TERMINAL", bg="#141414",
                 fg="#6e6e6e", font=(UI, 8, "bold"), pady=4).pack(side="left")
        clr = tk.Label(bar, text="Clear", bg="#141414", fg="#6e6e6e",
                        font=(UI, 8), cursor="hand2", padx=10)
        clr.pack(side="right")
        clr.bind("<Button-1>", lambda e: self.clear())
        clr.bind("<Enter>", lambda e: clr.config(fg="#cccccc"))
        clr.bind("<Leave>", lambda e: clr.config(fg="#6e6e6e"))

        self.text = tk.Text(
            self, bg=T["console_bg"], fg=T["console_fg"], font=(MONO, 11),
            state="disabled", relief="flat", bd=0,
            padx=14, pady=10, highlightthickness=0, wrap="word",
            insertbackground=T["console_fg"],
        )
        sb = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        sb.pack(side="right", fill="y")
        self.text.pack(fill="both", expand=True)
        self.text.config(yscrollcommand=sb.set)
        self.text.tag_configure("err",  foreground="#f44747")
        self.text.tag_configure("warn", foreground="#dcdcaa")
        self.text.tag_configure("info", foreground="#3794ff")
        self.text.tag_configure("ok",   foreground="#4ec9b0")
        self.text.tag_configure("run",  foreground="#c586c0")
        self.text.tag_configure("in",   foreground="#ce9178")

    def _stop_propagation(self, event):
        return "break"

    def _on_entry_return(self, event):
        self._submit_input()
        return "break"

    def is_input_active(self):
        return self._input_active

    def set_state(self, text, color="#4ec9b0"):
        self._state_lbl.config(text=text, fg=color)

    def request_input(self, prompt: str, kind: str, callback):
        self._input_cb = callback
        self._input_kind = kind
        hint = "type a number" if kind == "int" else "type text"
        self._prompt_lbl.config(text=f"INPUT  ·  {prompt}  ({hint})")
        self._input_var.set("")
        self._input_active = True

        self._in_wrap.config(bg="#1a2a3a")
        self._input_entry.config(
            state="normal",
            highlightbackground=T["accent"],
            highlightcolor=T["accent"],
        )
        self._submit_btn.config(state="normal", bg=T["accent"])
        self.set_state("● waiting — type below, press Enter", "#dcdcaa")

        self._input_entry.focus_set()
        self._input_entry.icursor("end")
        self.after(80, self._ensure_input_focus)

    def _ensure_input_focus(self):
        if self._input_active:
            try:
                self._input_entry.focus_force()
                self._input_entry.icursor("end")
            except tk.TclError:
                pass

    def disable_input(self):
        self._input_cb = None
        self._input_active = False
        self._input_entry.config(
            state="disabled",
            highlightbackground="#3c3c3c",
            highlightcolor="#3c3c3c",
        )
        self._submit_btn.config(state="disabled", bg="#0e639c")
        self._in_wrap.config(bg="#1a1a1a")
        self._prompt_lbl.config(text="INPUT  ·  program will prompt here when needed")
        self.set_state("● idle", "#6e6e6e")

    def _submit_input(self):
        if not self._input_cb:
            return
        val = self._input_var.get()
        if self._input_kind == "int":
            try:
                int(val.strip())
            except ValueError:
                show_warn(self, "Invalid Input", "Please enter a valid integer.")
                return
        cb = self._input_cb
        self._input_cb = None
        self._input_active = False
        self._input_entry.config(state="disabled")
        self._submit_btn.config(state="disabled")
        cb(val)

    def _append_line(self, msg, tag="ok"):
        self.text.config(state="normal")
        self.text.insert("end", msg, tag)
        self.text.see("end")
        self.text.config(state="disabled")

    def set(self, msg, tag="ok"):
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        if msg:
            self.text.insert("1.0", msg, tag)
        self.text.see("end")
        self.text.config(state="disabled")

    def write(self, msg, tag="ok"):
        self._append_line(msg, tag)

    def clear(self):
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.config(state="disabled")


# ══════════════════════════════════════════════════════════════════════════════
#  STATUS BAR
# ══════════════════════════════════════════════════════════════════════════════

class StatusBar(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg="#161B22", height=26)
        self.pack_propagate(False)
        self._pc  = self._seg("PC: 0x00400000", "#79C0FF")
        self._instr = self._seg("", "#8B949E")
        self._steps = self._seg("Steps: 0", "#A5D6FF")
        self._msg = self._seg("Ready", "#C9D1D9")
        self._ud  = self._seg("Undo: 0", "#6E7681", side="right")
        self._user_lbl = self._seg(f"User: —", "#6E7681", side="right")

    def _seg(self, text, fg, side="left"):
        l = tk.Label(self, text=text, bg="#161B22", fg=fg, font=(UI, 8), padx=10)
        l.pack(side=side)
        tk.Frame(self, width=1, bg="#30363D").pack(side=side, fill="y", pady=3)
        return l

    def update(self, pc, msg, undo_n, instr="", steps=0, user=""):
        self._pc.config(text=f"PC: 0x{pc:08X}")
        if instr:
            self._instr.config(text=f"Instr: {instr[:42]}")
        self._steps.config(text=f"Steps: {steps}")
        self._msg.config(text=msg or "Ready")
        self._ud.config(text=f"Undo: {undo_n}")
        if user:
            self._user_lbl.config(text=f"User: {user}")


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN APPLICATION
# ══════════════════════════════════════════════════════════════════════════════

class App(tk.Tk):
    def __init__(self, username: str = "user"):
        super().__init__()
        self._username = username
        self.title(f"PyMIPS32 Studio — {username}")
        self.geometry("1600x960")
        self.minsize(1200, 760)
        self.configure(bg=T["win"])

        self._eng       = MIPSEngine()
        self._assembled = False
        self._running   = False
        self._cur_file  = None
        self._run_steps = 0
        self._run_delay = RUN_DELAY

        self._build_menu()
        self._build_ui()
        self._bind_shortcuts()

        self.after(80, lambda: self._editor.set(SAMPLE))
        self._status.update(TEXT_BASE,
            "Ready — Assemble (F4) then Run (F5) or Step (F10 / Space)", 0,
            user=username)
        _center_window(self, 1600, 960)

    # ── MENU BAR ─────────────────────────────────────────────────────────────
    def _build_menu(self):
        menubar = tk.Menu(self, bg=T["panel"], fg=T["fg"], activebackground=T["hover"],
                          activeforeground=T["fg"], relief="flat")
        self.config(menu=menubar)

        file_m = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_m)
        file_m.add_command(label="New          Ctrl+N", command=self._do_new)
        file_m.add_command(label="Open         Ctrl+O", command=self._do_open)
        file_m.add_command(label="Save         Ctrl+S", command=self._do_save)
        file_m.add_separator()
        file_m.add_command(label="Exit         Alt+F4", command=self._do_exit)

        sim_m = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Simulator", menu=sim_m)
        sim_m.add_command(label="Assemble     F4",      command=self._do_assemble)
        sim_m.add_command(label="Run          F5 / Ctrl+R", command=self._do_run)
        sim_m.add_command(label="Pause        F6 / Ctrl+P", command=self._do_pause)
        sim_m.add_command(label="Step         F10 / Space", command=self._do_step)
        sim_m.add_command(label="Undo Step    F9",      command=self._do_undo)
        sim_m.add_command(label="Reset        F8",      command=self._do_reset)

        view_m = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_m)
        view_m.add_command(label="Reset Panel Layout", command=self._reset_layout)
        view_m.add_command(label="Find in Editor       Ctrl+F", command=self._do_find)

        tools_m = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_m)
        tools_m.add_command(label="Clear Console", command=lambda: self._console.clear())
        tools_m.add_command(label="Go to Line…         Ctrl+G", command=self._do_goto_line)

        help_m = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_m)
        help_m.add_command(label="Keyboard Shortcuts", command=self._show_shortcuts)
        help_m.add_command(label="About", command=self._show_about)

    def _show_shortcuts(self):
        show_info(self, "Keyboard Shortcuts",
                  "File:\n"
                  "  Ctrl+N  New    Ctrl+O  Open    Ctrl+S  Save\n\n"
                  "Simulator:\n"
                  "  F4  Assemble     F5 / Ctrl+R  Run\n"
                  "  F6 / Ctrl+P  Pause     F8  Reset\n"
                  "  F9  Undo Step    F10 / Space  Step\n\n"
                  "Panels: drag the sash between panels to resize.\n"
                  "Console: drag the sash above the console to resize height.")

    def _show_about(self):
        show_info(self, "About PyMIPS32 Studio",
                  "PyMIPS32 Studio — Professional MIPS32 Simulator\n\n"
                  "Features: assembler, step/run execution, undo,\n"
                  "register & memory views, syscall I/O.\n\n"
                  f"Logged in as: {self._username}")

    def _reset_layout(self):
        try:
            self._main_pane.sash_place(0, 380, 0)
            self._vert_pane.sash_place(0, 0, 620)
        except tk.TclError:
            pass
        show_info(self, "Layout Reset", "Panel sizes have been reset to defaults.")

    # ── UI ───────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # Toolbar — dark, compact, industry style
        tb = tk.Frame(self, bg=T["tb"], height=44)
        tb.pack(fill="x", side="top")
        tb.pack_propagate(False)

        brand = tk.Frame(tb, bg=T["tb"])
        brand.pack(side="left", padx=(16, 12), pady=6)
        tk.Label(brand, text="PyMIPS32", bg=T["tb"], fg=T["tb_fg"],
                 font=(UI, 13, "bold")).pack(side="left")
        tk.Label(brand, text=" Studio", bg=T["tb"], fg=T["tb_muted"],
                 font=(UI, 13)).pack(side="left")

        tk.Frame(tb, width=1, bg="#334155").pack(side="left", fill="y", pady=8, padx=4)

        def btn(label, key, cmd, style="default", dis=False):
            b = ToolBtn(tb, label, key, cmd, style=style, disabled=dis)
            b.pack(side="left", padx=1, pady=6)
            return b

        grp = tk.Frame(tb, bg=T["tb"])
        grp.pack(side="left", padx=4)
        self._b_new  = btn("New",      "Ctrl+N", self._do_new)
        self._b_open = btn("Open",     "Ctrl+O", self._do_open)
        self._b_save = btn("Save",     "Ctrl+S", self._do_save)

        tk.Frame(tb, width=1, bg="#334155").pack(side="left", fill="y", pady=8, padx=6)

        grp2 = tk.Frame(tb, bg=T["tb"])
        grp2.pack(side="left", padx=2)
        self._b_asm  = btn("Assemble", "F4",     self._do_assemble, style="primary")

        tk.Frame(tb, width=1, bg="#334155").pack(side="left", fill="y", pady=8, padx=6)

        grp3 = tk.Frame(tb, bg=T["tb"])
        grp3.pack(side="left", padx=2)
        self._b_run  = btn("Run",      "F5",     self._do_run,      style="run")
        self._b_pau  = btn("Pause",    "F6",     self._do_pause,    style="warn", dis=True)
        self._b_step = btn("Step",     "F10",    self._do_step,     style="primary")
        self._b_undo = btn("Undo",     "F9",     self._do_undo)
        self._b_rst  = btn("Reset",    "F8",     self._do_reset,    style="danger")

        # Speed control
        spd = tk.Frame(tb, bg=T["tb"])
        spd.pack(side="right", padx=12)
        tk.Label(spd, text="Speed", bg=T["tb"], fg=T["tb_muted"],
                 font=(UI, 8)).pack(side="left", padx=(0, 6))
        self._speed = tk.Scale(
            spd, from_=1, to=100, orient="horizontal", length=110,
            bg=T["tb"], fg=T["tb_fg"], troughcolor="#334155",
            highlightthickness=0, sliderrelief="flat", showvalue=False,
            command=self._on_speed,
        )
        self._speed.set(50)
        self._speed.pack(side="left")
        self._speed_lbl = tk.Label(spd, text="50%", bg=T["tb"],
                                    fg=T["tb_muted"], font=(UI, 8), width=4)
        self._speed_lbl.pack(side="left", padx=4)

        # Status bar at bottom
        self._status = StatusBar(self)
        self._status.pack(fill="x", side="bottom")

        # Configure ttk for dark theme
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TScrollbar", background="#252526", troughcolor="#1e1e1e",
                        bordercolor="#3c3c3c", arrowcolor="#858585")

        # Vertical split: main area | console (resizable sash)
        self._vert_pane = tk.PanedWindow(
            self, orient="vertical", bg=T["sash"],
            sashwidth=6, sashrelief="flat", opaqueresize=True,
        )
        self._vert_pane.pack(fill="both", expand=True)

        main_area = tk.Frame(self._vert_pane, bg=T["win"])
        self._vert_pane.add(main_area, minsize=400)

        console_wrap = tk.Frame(self._vert_pane, bg=T["panel"])
        self._vert_pane.add(console_wrap, minsize=100)
        self._console = Console(console_wrap)
        self._console.pack(fill="both", expand=True)

        # Horizontal split inside main: LEFT = regs+mem, RIGHT = editor
        self._main_pane = tk.PanedWindow(
            main_area, orient="horizontal", bg=T["sash"],
            sashwidth=6, sashrelief="flat", opaqueresize=True,
        )
        self._main_pane.pack(fill="both", expand=True, padx=4, pady=4)

        # LEFT column — registers + memory (QtSpim style, on the left)
        left_col = tk.Frame(self._main_pane, bg=T["win"])
        self._main_pane.add(left_col, minsize=320, width=380)

        left_split = tk.PanedWindow(
            left_col, orient="vertical", bg=T["sash"],
            sashwidth=5, sashrelief="flat", opaqueresize=True,
        )
        left_split.pack(fill="both", expand=True)

        reg_wrap = tk.Frame(left_split, bg=T["panel"],
                            highlightbackground=T["bd"], highlightthickness=1)
        left_split.add(reg_wrap, minsize=180)
        self._regs = RegTable(reg_wrap)
        self._regs.pack(fill="both", expand=True)

        mem_wrap = tk.Frame(left_split, bg=T["panel"],
                            highlightbackground=T["bd"], highlightthickness=1)
        left_split.add(mem_wrap, minsize=160)
        self._mem = MemViewer(mem_wrap)
        self._mem.pack(fill="both", expand=True)

        # RIGHT column — source editor
        right_col = tk.Frame(self._main_pane, bg=T["panel"],
                             highlightbackground=T["bd"], highlightthickness=1)
        self._main_pane.add(right_col, minsize=400)

        ehdr = tk.Frame(right_col, bg=T["hdr"])
        ehdr.pack(fill="x")
        tk.Frame(ehdr, width=2, bg=T["blue"]).pack(side="left", fill="y")
        tk.Label(ehdr, text="  SOURCE EDITOR", bg=T["hdr"], fg=T["fg"],
                 font=(UI, 9, "bold"), pady=7).pack(side="left")
        self._flbl = tk.Label(ehdr, text="untitled.asm", bg=T["hdr"],
                               fg=T["fg2"], font=(UI, 8))
        self._flbl.pack(side="right", padx=12, pady=4)
        hline(right_col)

        self._editor = CodeEditor(right_col)
        self._editor.pack(fill="both", expand=True)

        # Editor context menu (mouse execution)
        self._ctx = tk.Menu(self, tearoff=0)
        self._ctx.add_command(label="Assemble (F4)",  command=self._do_assemble)
        self._ctx.add_command(label="Run (F5)",       command=self._do_run)
        self._ctx.add_command(label="Step (F10)",     command=self._do_step)
        self._ctx.add_command(label="Pause (F6)",     command=self._do_pause)
        self._ctx.add_separator()
        self._ctx.add_command(label="Undo (F9)",      command=self._do_undo)
        self._ctx.add_command(label="Reset (F8)",     command=self._do_reset)
        self._editor.text.bind("<Button-3>", self._show_context_menu)

    def _show_context_menu(self, event):
        try:
            self._ctx.tk_popup(event.x_root, event.y_root)
        finally:
            self._ctx.grab_release()

    def _bind_shortcuts(self):
        def guard(fn):
            def handler(event=None):
                if self._eng.needs_input or self._console.is_input_active():
                    return "break"
                try:
                    if event and event.widget.winfo_class() == "Entry":
                        return "break"
                except tk.TclError:
                    pass
                fn()
            return handler

        binds = [
            ("<F4>",        self._do_assemble),
            ("<F5>",        self._do_run),
            ("<F6>",        self._do_pause),
            ("<F8>",        self._do_reset),
            ("<F9>",        self._do_undo),
            ("<F10>",       self._do_step),
            ("<Control-o>", self._do_open),
            ("<Control-s>", self._do_save),
            ("<Control-n>", self._do_new),
            ("<Control-r>", self._do_run),
            ("<Control-p>", self._do_pause),
            ("<Control-f>", self._do_find),
            ("<Control-g>", self._do_goto_line),
            ("<Alt-F4>",    self._do_exit),
        ]
        for key, fn in binds:
            self.bind_all(key, guard(fn))

        # Space = step only when editor focused and not waiting for input
        def space_step(event):
            if self._eng.needs_input or self._console.is_input_active():
                return "break"
            if event.widget is self._editor.text:
                self._do_step()
            return "break"
        self._editor.text.bind("<space>", space_step)

    # ── REFRESH ──────────────────────────────────────────────────────────────
    def _current_instr_text(self) -> str:
        e = self._eng
        if e.pc in e.text_segment:
            return e.text_segment[e.pc].raw_text
        return "—"

    def _refresh(self, status=""):
        e = self._eng
        self._regs.refresh(e.registers, e.pc, e.hi, e.lo, e.changed_registers)
        self._mem.update_text(e.text_segment, e.pc)
        self._mem.update_data(e.memory)
        self._console.set(e.console_output)
        if e.pc in e.text_segment:
            self._editor.mark_pc(e.text_segment[e.pc].source_line)
        else:
            self._editor.mark_pc(0)
        instr = self._current_instr_text()
        self._status.update(e.pc, status, e.undo_depth, instr,
                            steps=self._run_steps, user=self._username)

    def _on_speed(self, val):
        v = int(float(val))
        self._run_delay = max(1, 210 - v * 2)
        self._speed_lbl.config(text=f"{v}%")

    def _handle_input_wait(self):
        """Pause execution and activate the console input bar."""
        req = self._eng.pending_input
        if not req:
            return
        # Update views without stealing focus from the input entry
        e = self._eng
        self._regs.refresh(e.registers, e.pc, e.hi, e.lo, e.changed_registers)
        self._mem.update_text(e.text_segment, e.pc)
        self._mem.update_data(e.memory)
        self._console.set(e.console_output)
        if e.pc in e.text_segment:
            self._editor.mark_pc(e.text_segment[e.pc].source_line)
        instr = self._current_instr_text()
        self._status.update(e.pc, "Waiting for input — type in INPUT bar above",
                            e.undo_depth, instr,
                            steps=self._run_steps, user=self._username)
        self._regs.set_badge("● INPUT", T["yellow"])
        self._console.request_input(req.prompt, req.kind, self._on_input_submitted)

    def _on_input_submitted(self, value: str):
        try:
            self._eng.complete_input(value)
            self._console.disable_input()
            self._console.write(f"[input] {value.strip()}\n", "in")
            self._refresh("Input received — continuing")
            self._regs.set_badge("● RUNNING" if self._running else "● IDLE",
                                  T["green"] if self._running else T["fg2"])
            if self._running:
                self.after(10, self._run_tick)
        except Exception as ex:
            show_error(self, "Input Error", ex)
            self._handle_input_wait()

    def _do_find(self):
        from tkinter import simpledialog
        term = simpledialog.askstring("Find", "Search for:", parent=self)
        if not term:
            return
        t = self._editor.text
        t.tag_remove("sel", "1.0", "end")
        idx = t.search(term, "insert", stopindex="end")
        if not idx:
            idx = t.search(term, "1.0", stopindex="end")
        if idx:
            end = f"{idx}+{len(term)}c"
            t.tag_add("sel", idx, end)
            t.mark_set("insert", end)
            t.see(idx)
        else:
            show_warn(self, "Find", f'"{term}" not found.')

    def _do_goto_line(self):
        from tkinter import simpledialog
        ln = simpledialog.askinteger("Go to Line", "Line number:", parent=self, minvalue=1)
        if ln:
            self._editor.text.see(f"{ln}.0")
            self._editor.text.mark_set("insert", f"{ln}.0")

    def _set_exec_ui(self, running: bool):
        for b in (self._b_run, self._b_step, self._b_undo, self._b_rst,
                  self._b_asm, self._b_new, self._b_open, self._b_save):
            b.set_enabled(not running)
        self._b_pau.set_enabled(running)
        badge = ("● RUNNING", T["green"]) if running else ("● IDLE", T["fg2"])
        self._regs.set_badge(*badge)

    def _require_assembled(self) -> bool:
        if not self._assembled:
            self._do_assemble()
        return self._assembled

  # ── COMMANDS ─────────────────────────────────────────────────────────────
    def _do_exit(self):
        if self._running:
            self._running = False
        if messagebox.askyesno("Exit", "Close PyMIPS32 Studio?", parent=self):
            self.destroy()

    def _do_new(self):
        if not messagebox.askyesno("New File",
                "Discard current code and start a new file?", parent=self):
            return
        try:
            self._editor.set("# New MIPS program\n.text\nmain:\n    nop\n"
                             "    li   $v0, 10\n    syscall\n")
            self._eng.reset()
            self._assembled = False
            self._cur_file  = None
            self._flbl.config(text="● untitled.asm")
            self.title(f"PyMIPS32 Studio — {self._username}")
            self._refresh("New file created.")
            show_info(self, "New File", "A blank MIPS program has been created.\n"
                      "Write your code, then press Assemble (F4).")
        except Exception as ex:
            show_error(self, "New File Error", ex)

    def _do_open(self):
        path = filedialog.askopenfilename(
            parent=self, title="Open MIPS Assembly File",
            filetypes=[("MIPS Assembly", "*.asm *.s"), ("All Files", "*.*")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                src = f.read()
            self._editor.clear_marks()
            self._editor.set(src)
            self._cur_file = path
            name = os.path.basename(path)
            self._flbl.config(text=f"  {name}")
            self.title(f"PyMIPS32 Studio — {name}")
            self._eng.reset()
            self._assembled = False
            self._console.clear()
            self._status.update(TEXT_BASE, f"Opened: {name}", 0)
            show_info(self, "File Opened",
                      f"Loaded: {name}\n\nPress Assemble (F4) to load into the simulator.")
        except Exception as ex:
            show_error(self, "Open Error",
                       FileOperationException(str(ex), context=path))

    def _do_save(self):
        path = self._cur_file
        if not path:
            path = filedialog.asksaveasfilename(
                parent=self, title="Save MIPS Assembly File",
                defaultextension=".asm",
                filetypes=[("MIPS Assembly", "*.asm *.s"), ("All Files", "*.*")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._editor.get())
            self._cur_file = path
            name = os.path.basename(path)
            self._flbl.config(text=f"  {name}")
            self.title(f"PyMIPS32 Studio — {name}")
            self._status.update(self._eng.pc, f"Saved: {name}", self._eng.undo_depth)
            show_info(self, "File Saved", f"Saved successfully to:\n{path}")
        except Exception as ex:
            show_error(self, "Save Error",
                       FileOperationException(str(ex), context=path or ""))

    def _do_assemble(self):
        src = self._editor.get()
        if not src.strip():
            show_warn(self, "Assemble", "Nothing to assemble.\nThe editor is empty.")
            self._console.write("Nothing to assemble.\n", "warn")
            return
        try:
            self._eng.reset()
            self._assembled = False
            self._editor.clear_marks()
            self._console.clear()

            errors = self._eng.load_program(src)
            if errors:
                self._console.write(
                    f"══ Assembly Failed — {len(errors)} error(s) ══\n\n", "err")
                for err in errors:
                    self._console.write(
                        f"  Line {err.line_number}: {err.message}\n", "err")
                    self._editor.mark_err(err.line_number)
                self._status.update(self._eng.pc,
                    f"Assembly failed — {len(errors)} error(s)", 0)
                show_error(self, "Assembly Failed",
                           MIPSStudioError(
                               f"{len(errors)} assembly error(s) found.",
                               context=errors[0].message,
                               line=errors[0].line_number))
                return

            n = len(self._eng.text_segment)
            self._assembled = True
            self._console.write(
                f"══ Assembly Successful ══\n\n"
                f"  {n} instruction(s) loaded at 0x{TEXT_BASE:08X}\n"
                f"  Step (F10/Space) or Run (F5/Ctrl+R) to execute.\n\n",
                "info")
            self._refresh(f"Assembled — {n} instruction(s)")
            show_info(self, "Assembly Successful",
                      f"{n} instruction(s) loaded at 0x{TEXT_BASE:08X}.\n"
                      "Use Step (F10) or Run (F5) to execute.")
        except Exception as ex:
            show_error(self, "Assembly Error", ex)

    def _do_run(self):
        try:
            if not self._require_assembled():
                return
            if self._running:
                show_warn(self, "Run", "Simulator is already running.\nUse Pause (F6) to stop.")
                return
            if self._eng.halted:
                show_warn(self, "Run",
                          "Program has halted.\nPress Reset (F8) to restart execution.")
                return
            if self._eng.pc not in self._eng.text_segment:
                raise SimulatorStateException(
                    "PC is outside the text segment.",
                    context=f"PC = 0x{self._eng.pc:08X}")

            self._running = True
            self._run_steps = 0
            self._set_exec_ui(True)
            self._console.write("\n[Run] Execution started\n", "run")
            self._run_tick()
        except SimulatorStateException as ex:
            show_error(self, "Cannot Run", ex)
        except Exception as ex:
            show_error(self, "Run Error", ex)

    def _run_tick(self):
        """Execute one instruction on the main thread with visible UI updates."""
        if not self._running:
            self._finish_run("Execution paused.")
            return
        if self._eng.halted:
            self._finish_run("Program halted (syscall exit).")
            return
        if self._eng.pc not in self._eng.text_segment:
            self._finish_run("PC left text segment — execution stopped.")
            show_warn(self, "Execution Stopped",
                      f"PC = 0x{self._eng.pc:08X} is outside the text segment.")
            return

        instr = self._eng.text_segment.get(self._eng.pc)
        err = self._eng.step()
        self._run_steps += 1

        if err:
            self._console.write(f"\n✕ Runtime error: {err}\n", "err")
            self._refresh(f"Error at step {self._run_steps}")
            self._finish_run("Stopped due to runtime error.")
            show_error(self, "Runtime Error",
                       MIPSStudioError(err, context=self._current_instr_text(),
                                       line=instr.source_line if instr else 0))
            return

        if self._eng.needs_input:
            self._handle_input_wait()
            return

        self._refresh(f"Running — step {self._run_steps}")
        if self._run_steps % 10 == 0:
            self.update_idletasks()

        self.after(self._run_delay, self._run_tick)

    def _finish_run(self, msg: str):
        self._running = False
        self._set_exec_ui(False)
        self._refresh(msg)
        if self._run_steps > 0:
            self._console.write(
                f"\n■ Run finished after {self._run_steps} step(s). {msg}\n", "info")

    def _do_pause(self):
        if self._running:
            self._running = False
            show_info(self, "Paused",
                      f"Execution paused after {self._run_steps} step(s).\n"
                      "Press Run (F5) to continue or Step (F10) for one instruction.")
        else:
            show_warn(self, "Pause", "Simulator is not currently running.")

    def _do_step(self):
        try:
            if not self._require_assembled():
                return
            if self._running:
                show_warn(self, "Step", "Pause Run first (F6), then use Step.")
                return
            if self._eng.halted:
                show_warn(self, "Step",
                          "Program halted.\nPress Reset (F8) to restart.")
                return
            if self._eng.pc not in self._eng.text_segment:
                raise SimulatorStateException(
                    "PC is outside the text segment.",
                    context=f"PC = 0x{self._eng.pc:08X}")

            instr_before = self._current_instr_text()
            err = self._eng.step()
            if err:
                self._console.write(f"\n✕ {err}\n", "err")
                self._refresh(f"Error: {err}")
                show_error(self, "Runtime Error",
                           MIPSStudioError(err, context=instr_before))
                return

            if self._eng.needs_input:
                self._run_steps += 1
                self._handle_input_wait()
                return

            changed = self._eng.changed_registers
            names = [REGISTER_NAMES[i] for i in changed if i < 32]
            detail = f"Changed: {', '.join(names)}" if names else "No register changes"
            self._refresh(f"Step — {detail}")
        except SimulatorStateException as ex:
            show_error(self, "Cannot Step", ex)
        except Exception as ex:
            show_error(self, "Step Error", ex)

    def _do_undo(self):
        try:
            if not self._assembled:
                raise SimulatorStateException("Nothing assembled yet.", context="Assemble first")
            if self._running:
                raise SimulatorStateException("Pause execution before undo.")
            if self._eng.undo():
                self._refresh(f"Undo → PC = 0x{self._eng.pc:08X}")
            else:
                show_warn(self, "Undo", "Nothing to undo.")
        except SimulatorStateException as ex:
            show_error(self, "Undo Error", ex)

    def _do_reset(self):
        if not messagebox.askyesno("Reset Simulator",
                "Clear all registers, memory, and execution state?", parent=self):
            return
        try:
            self._running = False
            self._set_exec_ui(False)
            self._eng.reset()
            self._assembled = False
            self._editor.clear_marks()
            self._console.clear()

            src = self._editor.get()
            if src.strip():
                errs = self._eng.load_program(src)
                if errs:
                    self._assembled = False
                    show_warn(self, "Reset",
                              f"Re-assembled with {len(errs)} error(s). See console.")
                    for err in errs:
                        self._console.write(f"  Line {err.line_number}: {err.message}\n", "err")
                else:
                    self._assembled = True

            self._refresh("Reset complete.")
            self._console.write(
                "[Reset] Simulator cleared. Press Step or Run to execute.\n", "info")
        except Exception as ex:
            show_error(self, "Reset Error", ex)


# ══════════════════════════════════════════════════════════════════════════════
def main():
    try:
        auth = AuthManager()
        login = LoginWindow(auth)
        login.mainloop()

        if not login.logged_in:
            login.destroy()
            return

        username = login.username
        login.destroy()

        app = App(username=username)
        app.after(300, lambda: show_info(app, "Welcome",
                   f"Signed in as {username}.\n"
                   "Open or write code, then Assemble (F4) and Run (F5)."))
        app.mainloop()
    except Exception:
        traceback.print_exc()
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "PyMIPS32 Studio — Startup Error",
                traceback.format_exc(),
                parent=root,
            )
            root.destroy()
        except Exception:
            input("Startup failed. Press Enter to close...")


if __name__ == "__main__":
    main()
