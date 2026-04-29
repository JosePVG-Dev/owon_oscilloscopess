# AGENTS.md

## Project

OWON SDS1202 oscilloscope waveform reader, classifier, and dashboard. Python 3.7+.

## Commands

```bash
# Setup
python -m venv venv
.\venv\Scripts\Activate.ps1   # Windows PowerShell
pip install -r requirements.txt

# Run simulator (no hardware needed)
python main.py --simulator

# Run simulator in continuous loop
python main.py --simulator --loop --interval 5

# Run with real oscilloscope
python main.py -c 1

# Dashboard (must run separately)
python dashboard.py          # http://localhost:5000

# Both at once (capture + dashboard)
python run.py --simulator
```

## Architecture

- `oscope.py` — Hardware connection via **PyVISA** (USBTMC). `Oscilloscope` (real) + `OscilloscopeSimulator` (random wave each read). The simulator randomly picks a wave type per call.
- `classifier.py` — Rule-based heuristic using FFT frequency estimation, autocorrelation, ramp symmetry, and edge detection. Maps waveforms to `WaveType` → `SeaType`.
- `database.py` — SQLite persistence, auto-creates `waveforms.db`. No UPDATE/DELETE.
- `main.py` — CLI entry point. `WaveReader` orchestrates scope → classify → save. `--recent` does NOT require scope connection.
- `dashboard.py` — Flask web app, polls DB every 5s via JS. Templates in `templates/index.html`.
- `run.py` — Launches capture loop + dashboard simultaneously.

## Key Gotchas

- **Connection library is `pyvisa`/`pyvisa-py`**, NOT `pyusb` or `pywinusb`. The old README mentions WinUSB/Zadig — that's outdated and wrong for PyVISA.
- **`Classifier` uses FFT for frequency estimation** (not zero-crossing). The signal is mean-centered before analysis. `sample_rate` default is 1000 but should match the actual acquisition rate.
- **`OscilloscopeSimulator.read_wave()` returns a random wave type each call** (simulating an AWG like the OWON AG051 changing waveforms). Signals are centered at zero, not offset.
- **No test suite exists.** `test_e2e.py` is ad-hoc and should be deleted before commits.
- **SQLite uses per-call connections** (`with sqlite3.connect(...)` in every method). Not a problem for single-process use.
- **The OWON SDS1202 requires `:SDSLSCPI#` handshake** when connected via serial/LAN. The current code uses USBTMC only.
- **Waveform data binary parsing** in `Oscilloscope._parse_wave_data()` tries IEEE 488.2 `#<n><count>` header first, falls back to skipping 4 bytes.
- **Dashboard auto-refreshes** via JS `setInterval(5000)` calling `/api/stats` and `/api/readings?since_id=N`.

## Classifier Design Notes

Classification uses these metrics in order:
1. `amplitude_range < 0.01` → noise (flat signal)
2. `autocorr < 0.3` → noise (no structure)
3. `std_ratio < 0.05 && autocorr > 0.8` → triangular (constant slope)
4. Asymmetric ramps + edge detection → sierra
5. `unique_values ≤ 5` → cuadrada (few discrete levels)
6. `ramp_symmetry > 0.7` → triangular (fallback for low-resolution)
7. `0.35 < positive_ratio < 0.65 && autocorr > 0.9` → senoidal
8. `std_ratio < 0.8 && autocorr > 0.5` → senoidal (fallback)

## Dependencies

```
flask          # dashboard
pyvisa         # VISA abstraction layer
pyvisa-py      # pure-Python VISA backend (no NI-VISA required)
numpy          # waveform analysis + simulator generation
```

## Language

UI strings and code comments are in Spanish. Variable names and class names are in English.