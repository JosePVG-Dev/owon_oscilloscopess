# AGENTS.md

## Project

OWON SDS1202 oscilloscope waveform reader, classifier, and dashboard. Python 3.7+.
Supports three data sources: simulator, AWG AG051, and real oscilloscope (SDS1202).

## Commands

```bash
# Setup
python -m venv venv
.\venv\Scripts\Activate.ps1   # Windows PowerShell
pip install -r requirements.txt

# === Simulator (no hardware needed) ===
python main.py --simulator
python main.py --simulator --loop --interval 2
python main.py --simulator --frequency 50 --wave-type senoidal

# === AWG AG051 (reads config from real device) ===
python main.py --awg
python main.py --awg --frequency 500              # specify frequency
python main.py --awg --loop --interval 3           # continuous mode

# === Real oscilloscope (SDS1202, REQUIRES firmware > 1.5.0) ===
python main.py -c 1
python main.py -c 1 --all                          # both channels

# Dashboard (must run separately)
python dashboard.py          # http://localhost:5000

# Both at once (capture + dashboard)
python run.py --simulator
python run.py --awg --frequency 500
python run.py -c 1
```

## Architecture

- `oscope.py` — Oscilloscope via **PyVISA** (USBTMC). SCPI commands: `:CH1:SCAL?`, `:HOR:SCAL?`, `:TRIG:STAT?`, `:ACQ:MODE?`. Includes `OscilloscopeSimulator` (random wave per call).
- `awg.py` — AWG AG051 via **PyUSB** raw bulk endpoints (NOT USBTMC). Reads `:FUNC?` for wave type. Uses `\r` terminator, responses end with `->\n`.
- `classifier.py` — Rule-based heuristic using FFT, autocorrelation, ramp symmetry, edge detection. Maps `WaveType` → `SeaType`.
- `database.py` — SQLite persistence, auto-creates `waveforms.db`. No UPDATE/DELETE.
- `main.py` — CLI entry point. `WaveReader` orchestrates: scope/AWG/sim → classify → save. `--recent` does NOT require device connection.
- `dashboard.py` — Flask web app, polls DB every 2s via JS. Templates in `templates/index.html`.
- `run.py` — Launches capture loop + dashboard simultaneously.

## Data Sources

| Mode | Flag | Hardware | How it works |
|------|------|----------|--------------|
| Simulator | `--simulator` | None | Generates random waves in software |
| AWG | `--awg` | AG051 (USB) | Reads `:FUNC?` config from device, synthesizes waveform in software |
| Oscilloscope | `-c 1` | SDS1202 (USB, USBTMC) | Reads `:DATA:WAVE:SCREen:CH1?` binary waveform |

**IMPORTANT: SDS1202 firmware 1.5.0 does NOT return waveform data** (`:DATA:WAVE:SCREen:CH1?` returns 4 null bytes = 0 samples). SCPI write commands also don't work on this firmware. Only read queries succeed. Use `--awg` or `--simulator` instead.

## AWG AG051 Details

- **Connection:** PyUSB raw bulk endpoints (OUT 0x03, IN 0x81). NOT USBTMC/VISA. VID 0x5345, PID 0x1234.
- **Terminator:** Commands end with `\r`, responses end with `\n->`.
- **Working command:** Only `:FUNC?` is reliable (returns `SINE`, `SQU`, `TRI`, `RAMP`, etc.).
- **NOT working:** `:FREQ?` and `:PER?` return garbage on firmware V3.0.0 (they echo the wave type). Frequency is taken from the `--frequency` CLI parameter instead (default 1000 Hz).
- **Wave type mapping:** `SINE`→senoidal, `SQU`→cuadrada, `TRI`→triangular, `RAMP`→sierra, `NOISE`→ruido.
- **Synthesis:** 5 cycles at 10000 samples/sec, normalized to ±0.5V amplitude.
- **Buffer:** `_clear_buffer()` is called before each `_query()` to flush stale USB data. Uses `continue` on timeout (not `break`) to retry all 5 clear attempts.

## Oscilloscope SCPI Commands (SDS1202 firmware 1.5.0)

Commands that WORK (read-only):
- `*IDN?` → device identity
- `:STOP`, `:RUN` → acquisition control
- `:CH1:SCAL?`, `:CH2:SCAL?` → vertical scale
- `:CH1:COUP?`, `:CH1:DISP?` → coupling, display state
- `:HOR:SCAL?` → horizontal timebase
- `:ACQ:MODE?` → acquisition mode
- `:TRIG:STAT?` → trigger status

Commands that DO NOT work (timeout or return null):
- `:CHANnel1:SCALe?`, `:TIMebase:SCALe?` → use `:CH1:SCAL?`, `:HOR:SCAL?` instead
- `:ACQuire:SRATe?` → sample rate unavailable
- `:WAV:DATA?`, any `:WAV:*` commands → timeout
- `:DATA:WAVE:SCREen:CH1?` → returns 4 null bytes (0 samples) regardless of scope state
- SCPI write commands → not accepted (device is read-only via SCPI)

Terminator: `\r` for writes, `\n` for reads. Response format: `VALUE->\n`.

## Key Gotchas

- **`oscope.py` uses PyVISA** (USBTMC), **`awg.py` uses PyUSB** (raw bulk). Two different USB libraries for two devices.
- **Only one PyVISA session can be open** at a time for the SDS1202. Opening a second ResourceManager fails with libusb assertion error.
- **SDS1202 is read-only via SCPI.** You can't change timebase or trigger settings programmatically. Configure manually on the front panel.
- **Waveform data can't be read from SDS1202 firmware 1.5.0.** The `:DATA:WAVE:SCREen:CH1?` response is always 4 null bytes. Use `--awg` or `--simulator`.
- **The `:SDSLSCPI#` handshake** (serial/LAN only) breaks USBTMC sessions. Don't use it.
- **`Classifier` uses FFT for frequency estimation** (not zero-crossing). Signal is mean-centered before analysis.
- **`OscilloscopeSimulator.read_wave()` returns a random wave type each call.** Signals are centered at zero.
- **No test suite exists.**
- **Dashboard auto-refreshes** via JS `setInterval(2000)`.

## Dependencies

```
flask          # dashboard
pyvisa         # VISA abstraction layer (oscope.py)
pyvisa-py      # pure-Python VISA backend
pyusb          # USB communication (awg.py)
libusb-package # libusb1 backend for pyusb on Windows
numpy          # waveform analysis + synthesis
```

## Language

UI strings and code comments are in Spanish. Variable names and class names are in English.