# Wave Classifier Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the rule-based heuristic classifier with template correlation on a single extracted cycle, and make the simulator use fixed configurable frequency.

**Architecture:** Extract one representative cycle via FFT frequency estimation, normalize it, then compute max Pearson correlation across all phase shifts against canonical wave templates. Highest correlation wins. Simulator generates at a fixed configurable frequency instead of random.

**Tech Stack:** Python 3.7+, NumPy, Flask (unchanged)

---

### Task 1: Add template correlation methods to Classifier

**Files:**
- Modify: `classifier.py` (add new methods, keep existing ones)

- [ ] **Step 1: Add `_extract_one_cycle` method**

Add after `_estimate_frequency_fft` (after line 45 in current file):

```python
def _extract_one_cycle(self, arr: np.ndarray, freq: float) -> Optional[np.ndarray]:
    period_samples = int(round(self.sample_rate / freq))
    if period_samples < 10 or period_samples > len(arr):
        return None
    centered = arr - np.mean(arr)
    peak_idx = int(np.argmax(centered))
    start = peak_idx
    end = start + period_samples
    if end > len(arr):
        start = len(arr) - period_samples
        end = len(arr)
    return arr[start:end]
```

- [ ] **Step 2: Add `_normalize_cycle` method**

```python
def _normalize_cycle(self, cycle: np.ndarray) -> np.ndarray:
    centered = cycle - np.mean(cycle)
    max_abs = np.max(np.abs(centered))
    if max_abs < 1e-10:
        return centered
    return centered / max_abs
```

- [ ] **Step 3: Add `_max_correlation` method**

Uses FFT-based circular cross-correlation for O(n log n) performance. Computes max|circular cross-correlation| normalized by signal norms, equivalent to trying all phase shifts and taking the best Pearson correlation:

```python
@staticmethod
def _max_correlation(signal: np.ndarray, template: np.ndarray) -> float:
    s = signal - np.mean(signal)
    t = template - np.mean(template)
    s_norm = np.sqrt(np.sum(s ** 2))
    t_norm = np.sqrt(np.sum(t ** 2))
    if s_norm < 1e-10 or t_norm < 1e-10:
        return 0.0
    fft_s = np.fft.fft(s)
    fft_t = np.fft.fft(t)
    corr = np.fft.ifft(fft_s * np.conj(fft_t)).real
    return float(np.max(np.abs(corr)) / (s_norm * t_norm))
```

- [ ] **Step 4: Add `_classify_by_template` method**

```python
def _classify_by_template(self, cycle: np.ndarray) -> WaveType:
    normalized = self._normalize_cycle(cycle)
    n = len(normalized)
    t = np.linspace(0, 1, n, endpoint=False)

    templates = {
        WaveType.SINUSOIDAL: np.sin(2 * np.pi * t),
        WaveType.CUADRADA: np.where(t < 0.5, 1.0, -1.0),
        WaveType.TRIANGULAR: 1.0 - 4.0 * np.abs(t - 0.5),
        WaveType.SIERRA: 2.0 * t - 1.0,
    }

    best_type = WaveType.RUIDO
    best_score = 0.0

    for wave_type, template in templates.items():
        score = self._max_correlation(normalized, template)
        if score > best_score:
            best_score = score
            best_type = wave_type

    if best_score < 0.5:
        return WaveType.RUIDO

    return best_type
```

---

### Task 2: Rewrite `classify()` method

**Files:**
- Modify: `classifier.py` (replace `classify` method, lines 99-159)

- [ ] **Step 1: Replace the `classify` method**

Replace the entire `classify` method with:

```python
def classify(self, data: List[float]) -> WaveType:
    if len(data) < 10:
        return WaveType.RUIDO

    arr = np.array(data)
    amplitude_range = np.max(arr) - np.min(arr)

    if amplitude_range < 0.01:
        return WaveType.RUIDO

    centered = arr - np.mean(arr)
    if np.std(centered) > 1e-10:
        autocorr = float(np.corrcoef(centered[:-1], centered[1:])[0, 1])
        if autocorr < 0.15:
            return WaveType.RUIDO

    freq = self._estimate_frequency_fft(arr)
    if freq < 1e-6:
        return WaveType.RUIDO

    cycle = self._extract_one_cycle(arr, freq)
    if cycle is not None and len(cycle) >= 10:
        return self._classify_by_template(cycle)

    return self._classify_by_template(arr)
```

Note: `analyze()`, `get_parameters()`, `classify_and_map()`, `map_to_sea()` all remain unchanged.

---

### Task 3: Update OscilloscopeSimulator with fixed frequency and wave_type

**Files:**
- Modify: `oscope.py` (OscilloscopeSimulator class)

- [ ] **Step 1: Update `__init__` to accept frequency, wave_type, sample_rate**

Replace the `OscilloscopeSimulator.__init__` method (lines 205-207):

```python
class OscilloscopeSimulator:
    def __init__(self, frequency: float = 50.0, wave_type: Optional[str] = None, sample_rate: int = 1000):
        self.connected = True
        self._last_wave_type = None
        self.frequency = frequency
        self.wave_type = wave_type
        self.sample_rate = sample_rate
```

Also add the import for `Optional` at the top of the file if not already present (it is — line 2 has `from typing import List, Optional, Tuple`).

- [ ] **Step 2: Rewrite `read_wave` to use fixed frequency and configurable wave type**

Replace `OscilloscopeSimulator.read_wave` (lines 223-242):

```python
def read_wave(self, channel: int = 1) -> List[float]:
    freq = self.frequency
    n_cycles = 5
    duration = n_cycles / freq
    n_samples = max(int(duration * self.sample_rate), 100)
    t = np.linspace(0, duration, n_samples, endpoint=False)

    if self.wave_type is not None:
        wave_type = self.wave_type
    else:
        wave_type = np.random.choice(["senoidal", "cuadrada", "triangular", "sierra", "ruido"])

    if wave_type == "senoidal":
        signal = np.sin(2 * np.pi * freq * t) * 0.5
    elif wave_type == "cuadrada":
        signal = np.sign(np.sin(2 * np.pi * freq * t)) * 0.5
    elif wave_type == "triangular":
        signal = (2 * np.abs(2 * (freq * t - np.floor(freq * t + 0.5))) - 1) * 0.5
    elif wave_type == "sierra":
        signal = (2 * (freq * t - np.floor(freq * t)) - 1) * 0.5
    else:
        signal = np.random.normal(0, 0.15, n_samples)

    self._last_wave_type = wave_type
    return list(signal)
```

Key changes:
- Frequency is `self.frequency` (fixed, not random)
- All wave amplitudes are consistent (`*0.5` — triangular and sierra were `*0.25` before)
- `n_samples` is computed from `duration * sample_rate` for correct FFT
- `wave_type` uses `self.wave_type` if set, otherwise random

- [ ] **Step 3: Update `read_channel` to pass sample_rate in params**

Replace `OscilloscopeSimulator.read_channel` (lines 244-250):

```python
def read_channel(self, channel: int = 1) -> Tuple[List[float], dict]:
    data = self.read_wave(channel)
    params = {
        "v_scale": 1.0,
        "h_scale": 1.0 / self.frequency,
        "sample_rate": self.sample_rate,
    }
    return data, params
```

---

### Task 4: Update main.py CLI flags

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Add `--frequency` and `--wave-type` arguments**

Add after the `--all` argument (after line 144 in the argparse section):

```python
parser.add_argument("--frequency", type=float, default=50.0,
                    help="Frecuencia del simulador en Hz (default: 50)")
parser.add_argument("--wave-type", type=str, default=None,
                    choices=["senoidal", "cuadrada", "triangular", "sierra", "ruido"],
                    help="Tipo de onda del simulador (default: aleatorio)")
```

- [ ] **Step 2: Pass frequency and wave_type to WaveReader/simulator**

Modify the `WaveReader.__init__` and `main()` to accept and pass these params.

In `WaveReader.__init__` (line 10-19), change to:

```python
def __init__(self, use_simulator: bool = False, frequency: float = 50.0, wave_type: Optional[str] = None):
    self.use_simulator = use_simulator

    if use_simulator:
        self.scope = OscilloscopeSimulator(frequency=frequency, wave_type=wave_type)
    else:
        self.scope = Oscilloscope()

    self.classifier = Classifier()
    self.db = Database()
```

Add the import for Optional at the top of main.py:

```python
from typing import Optional
```

In `main()`, update the WaveReader instantiation (line 152):

```python
reader = WaveReader(use_simulator=args.simulator, frequency=args.frequency, wave_type=args.wave_type)
```

---

### Task 5: Rewrite test_e2e.py as a proper validation test

**Files:**
- Modify: `test_e2e.py`

- [ ] **Step 1: Rewrite test_e2e.py**

Replace the entire file with a proper test that validates the new classifier against all wave types at multiple frequencies:

```python
import numpy as np
from classifier import Classifier, WaveType

c = Classifier()
all_ok = True

for sample_rate in [1000]:
    for freq in [10, 25, 50, 75, 100, 200]:
        duration = 5.0 / freq
        n_samples = int(duration * sample_rate)
        if n_samples < 50:
            continue
        t = np.linspace(0, duration, n_samples, endpoint=False)

        waves = {
            "senoidal": list(np.sin(2 * np.pi * freq * t) * 0.5),
            "cuadrada": list(np.sign(np.sin(2 * np.pi * freq * t)) * 0.5),
            "triangular": list((2 * np.abs(2 * (freq * t - np.floor(freq * t + 0.5))) - 1) * 0.5),
            "sierra": list((2 * (freq * t - np.floor(freq * t)) - 1) * 0.5),
            "ruido": list(np.random.normal(0, 0.15, n_samples)),
        }

        for name, wave in waves.items():
            result = c.classify(wave).value
            ok = result == name
            if not ok:
                all_ok = False
            status = "OK" if ok else "FAIL"
            print(f"  {name:12s} @ {freq:3d}Hz ({n_samples:4d} samples) -> {result:12s} {status}")

print(f"\n{'ALL CORRECT' if all_ok else 'SOME FAILURES'}")
```

- [ ] **Step 2: Run test and verify**

Run: `python test_e2e.py`
Expected: `ALL CORRECT` for most frequencies. Sierra and ruido may have edge cases.

- [ ] **Step 3: Commit**

```bash
git add classifier.py oscope.py main.py test_e2e.py
git commit -m "feat: replace rule-based classifier with template correlation on single cycle"
```

---

### Task 6: Update Classifier to use sample_rate from oscilloscope params

**Files:**
- Modify: `classifier.py` (Classifier constructor and classify method)
- Modify: `main.py` (WaveReader.read_and_save)

Currently, `Classifier(sample_rate=1000)` is hardcoded. The classifier should receive the correct sample rate from the oscilloscope. This is important because:
- Real oscilloscope: `sample_rate` comes from `:TIMebase:SCALe?` and ADC settings
- Simulator: `sample_rate` is configurable

- [ ] **Step 1: Update WaveReader to pass sample_rate to Classifier**

In `WaveReader.read_and_save`, after getting data from the scope:

```python
def read_and_save(self, channel: int = 1):
    print(f"\nLeyendo canal CH{channel}...")

    data, params = self.scope.read_channel(channel)

    if not data or len(data) < 10:
        print("Datos insuficientes, usando simulador...")
        simulator = OscilloscopeSimulator()
        data = simulator.read_wave(channel)
        params = {"v_scale": 1.0, "h_scale": 0.001, "sample_rate": 1000}

    sample_rate = params.get("sample_rate", 1000)
    self.classifier = Classifier(sample_rate=sample_rate)

    wave_type, sea_type = self.classifier.classify_and_map(data)
    params_report = self.classifier.get_parameters(data)
```

- [ ] **Step 2: Update Oscilloscope.read_channel to include sample_rate**

In `Oscilloscope.read_channel`, add sample_rate determination:

```python
def read_channel(self, channel: int = 1) -> Tuple[List[float], dict]:
    data = self.read_wave(channel)

    params = {}
    if data:
        try:
            scale_resp = self.send_command(f":CHANnel{channel}:SCALe?")
            v_scale = float(scale_resp.strip())
        except Exception:
            v_scale = 1.0

        try:
            time_resp = self.send_command(":TIMebase:SCALe?")
            h_scale = float(time_resp.strip())
        except Exception:
            h_scale = 0.001

        sample_rate = 1000
        try:
            sr_resp = self.send_command(":ACQuire:SRATe?")
            sample_rate = int(float(sr_resp.strip()))
        except Exception:
            pass

        params = {
            "v_scale": v_scale,
            "h_scale": h_scale,
            "sample_rate": sample_rate,
        }

    return data, params
```

- [ ] **Step 3: Run full integration test**

Run: `python main.py --simulator --wave-type senoidal --frequency 50`
Expected: Classifies as "senoidal" consistently.

Run: `python test_e2e.py`
Expected: ALL CORRECT or near-correct (a few edge case failures acceptable at extreme frequencies).

- [ ] **Step 4: Commit**

```bash
git add classifier.py oscope.py main.py
git commit -m "feat: pass sample_rate from oscilloscope to classifier"
```