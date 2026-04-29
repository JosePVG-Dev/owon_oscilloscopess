# PyVISA Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the broken pywinusb HID connection with PyVISA USBTMC and fix all identified bugs.

**Architecture:** Oscilloscope class uses pyvisa for USBTMC communication with OWON SDS1202. Waveform parsing handles IEEE 488.2 binary block headers. All bugs fixed across oscope.py, main.py, database.py, and requirements.txt.

**Tech Stack:** pyvisa, pyvisa-py, numpy, sqlite3 (stdlib), argparse (stdlib)

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `requirements.txt` | Modify | Replace `pyusb` with `pyvisa` and `pyvisa-py` |
| `oscope.py` | Rewrite | PyVISA USBTMC connection, proper SCPI, fixed parser, fixed simulator |
| `main.py` | Modify | Fix fallback bug, fix connect redundancy, fix `--recent`, fix typo, fix bare except |
| `database.py` | Modify | Remove unused `datetime` import |

---

### Task 1: Update requirements.txt

- [ ] Replace contents with: `pyvisa`, `pyvisa-py`, `numpy`
- [ ] Run `pip install -r requirements.txt`
- [ ] Commit

### Task 2: Rewrite oscope.py with PyVISA

- [ ] Replace entire file with PyVISA-based Oscilloscope class (usbtmc connection, auto-detect, context manager, IEEE 488.2 parser, send_command, send_query_raw, read_channel queries actual scales)
- [ ] Fix OscilloscopeSimulator channel mapping (CH1->senoidal via `(channel-1)%5`)
- [ ] Add send_command() to OscilloscopeSimulator for duck-type compatibility
- [ ] Run `python main.py --simulator -c 1` to verify
- [ ] Commit

### Task 3: Fix main.py bugs

- [ ] Fix fake simulator fallback: use `OscilloscopeSimulator()` instead of re-reading from same scope
- [ ] Remove redundant `if/else` in connect() (both branches identical)
- [ ] Fix `--recent` to not require scope connection (create WaveReader with simulator=True, skip connect)
- [ ] Fix typo: "lettura" -> "lectura"
- [ ] Fix bare `except:` -> `except Exception:`
- [ ] Run `python main.py --simulator -c 1` and `python main.py --recent 5`
- [ ] Commit

### Task 4: Clean up database.py

- [ ] Remove unused `from datetime import datetime`
- [ ] Verify: `python -c "from database import Database; db = Database(); print('DB OK')"`
- [ ] Commit