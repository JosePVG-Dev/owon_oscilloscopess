# PyVISA Refactor Design

## Problem

The OWON SDS1202 oscilloscope cannot connect because `oscope.py` uses `pywinusb.hid` (HID protocol), but the SDS1202 communicates via USBTMC or serial — not HID. Additional bugs exist across the codebase.

## Chosen Approach

**Full refactoring (Approach B):** Replace `pywinusb` with `pyvisa`, fix all identified bugs.

## Changes

### oscope.py — Complete rewrite

**Connection:**
- Replace `import pywinusb.hid as hid` with `import pyvisa`
- Use `pyvisa.ResourceManager('@py')` (pyvisa-py backend, no NI-VISA required)
- Auto-detect resource via `rm.list_resources()` filtering VID `0x5345`
- `connect()`: open USBTMC resource, verify with `*IDN?`
- Add context manager (`__enter__`/`__exit__`)
- Error handling: catch `pyvisa.errors.VisaIOError`, no bare `except:`

**SCPI Communication:**
- `send_command()`: use `instrument.query()` for queries, `instrument.write()` for commands
- `read_wave()`: send `:DATA:WAVE:SCREen:CH{ch}?`, read binary with `read_raw()`
- `_parse_wave_data()`: parse IEEE 488.2 definite-length block header (`#<n><count>`) instead of skipping fixed 4 bytes

**Simulator:**
- Fix channel index bug: CH1 → senoidal (index 0), CH2 → cuadrada (index 1)
- Add `send_command()` method for duck-type compatibility

### main.py — Bug fixes

- Fix fake simulator fallback: instantiate `OscilloscopeSimulator()` when real scope fails, not re-read from same scope
- Remove redundant `if/else` in `connect()` (both branches identical)
- `--recent` mode: skip scope connection, only query database
- Fix typo: "lettura" → "lectura"

### requirements.txt — Correct dependencies

```
pyvisa
pyvisa-py
numpy
```

### database.py — Cleanup

- Remove unused `from datetime import datetime`

### classifier.py — No changes

Classification logic works correctly with normalized data from the new parser.

## Architecture

```
main.py (WaveReader)
    ├── oscope.py (Oscilloscope → pyvisa USBTMC)
    │   └── OscilloscopeSimulator (unchanged logic, fixed channel mapping)
    ├── classifier.py (unchanged)
    └── database.py (minor cleanup)
```

## Error Handling Strategy

- `Oscilloscope.connect()`: catch `VisaIOError`, return `False` with descriptive message
- `send_command()`: catch timeouts, raise custom exception
- `read_wave()`: catch parse errors, return empty list with warning
- `main.py`: fallback to `OscilloscopeSimulator` when real device fails
- No bare `except:` anywhere

## Data Flow

```
Oscilloscope.read_wave(ch) → List[float]
    1. instrument.query(f':DATA:WAVE:SCREen:CH{ch}?')
    2. Parse IEEE 488.2 binary block header
    3. Decode 16-bit signed LE samples
    4. Normalize (ADC range / sample values)
    5. Return List[float]

Classifier.classify_and_map(data) → (WaveType, SeaType)
Database.save_waveform(...) → int
```

## Testing Strategy

- Test with `--simulator` flag first (no hardware needed)
- Test with real device: `python main.py --simulator` then `python main.py -c 1`
- Verify `*IDN?` response
- Verify waveform data parsing with real samples