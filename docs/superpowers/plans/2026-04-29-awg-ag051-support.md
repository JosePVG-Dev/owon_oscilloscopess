# AWG AG051 Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add support for the OWON AG051 Arbitrary Waveform Generator as a direct waveform source, replacing the oscilloscope when `--awg` flag is used.

**Architecture:** The AG051 uses a simplified SCPI dialect over USB bulk (endpoints 0x03 OUT, 0x81 IN). It reports its current configuration (wave type, frequency) but cannot be read like an oscilloscope. We synthesize waveform data from the reported config and feed it through the existing classifier and database pipeline.

**Tech Stack:** Python 3.7+, pyusb, libusb-package, numpy

---

## File Structure

| File | Responsibility |
|------|---------------|
| `awg.py` (new) | PyUSB driver for AG051: connect, query config, generate synthetic waveform |
| `main.py` (modify) | Add `--awg` CLI flag, instantiate AWG instead of Oscilloscope |
| `requirements.txt` (modify) | Add `pyusb`, `libusb-package` |

---

## Task 1: Create `awg.py` — AG051 Driver

**Files:**
- Create: `awg.py`
- Test: `python -c "from awg import AWG; a=AWG(); print(a.connect()); print(a.get_config()); a.disconnect()"`

- [ ] **Step 1: Write the driver skeleton**

```python
import os
import time
from typing import List, Optional, Tuple
import numpy as np

try:
    import libusb_package
    _libusb_dir = os.path.dirname(libusb_package.get_library_path())
    if _libusb_dir not in os.environ.get('PATH', ''):
        os.environ['PATH'] = _libusb_dir + os.pathsep + os.environ.get('PATH', '')
except Exception:
    pass

import usb.core


class AWG:
    """Driver for OWON AG051 Arbitrary Waveform Generator via PyUSB."""

    VID = 0x5345
    PID = 0x1234
    SERIAL = 'AG0512117060'
    ENDPOINT_OUT = 3
    ENDPOINT_IN = 0x81

    WAVE_MAP = {
        'SINE': 'senoidal',
        'SQU': 'cuadrada',
        'SQUARE': 'cuadrada',
        'TRI': 'triangular',
        'TRIANGLE': 'triangular',
        'RAMP': 'sierra',
        'SAW': 'sierra',
        'PULSE': 'cuadrada',
        'ARB': 'senoidal',
        'NOISE': 'ruido',
        'DC': 'ruido',
    }

    def __init__(self):
        self.dev = None
        self.connected = False

    def connect(self) -> bool:
        try:
            self.dev = usb.core.find(idVendor=self.VID, idProduct=self.PID,
                                     serial_number=self.SERIAL)
            if self.dev is None:
                print("AWG no encontrado")
                return False
            self.dev.set_configuration()
            idn = self._query('*IDN?')
            print(f"Conectado a: {idn.strip()}")
            self.connected = True
            return True
        except Exception as e:
            print(f"Error conectando AWG: {e}")
            self.connected = False
            return False

    def disconnect(self):
        self.dev = None
        self.connected = False
        print("Desconectado")

    def _query(self, cmd: str, delay: float = 0.4, timeout: int = 800) -> str:
        if not self.dev:
            raise RuntimeError("No conectado")
        self.dev.write(self.ENDPOINT_OUT, (cmd + '\r').encode())
        time.sleep(delay)
        raw = self.dev.read(self.ENDPOINT_IN, 10000, timeout)
        return raw.tobytes().decode('utf-8', errors='ignore')

    def get_config(self) -> dict:
        """Read current AWG configuration."""
        func_raw = self._query(':FUNC?').strip().replace('->', '').strip()
        freq_raw = self._query(':FREQ?').strip().replace('->', '').strip()
        per_raw = self._query(':PER?').strip().replace('->', '').strip()

        try:
            frequency = float(freq_raw)
        except ValueError:
            frequency = 1000.0

        try:
            period = float(per_raw)
        except ValueError:
            period = 1.0 / frequency if frequency > 0 else 0.001

        wave_type = self.WAVE_MAP.get(func_raw.upper(), 'senoidal')

        return {
            'wave_type': wave_type,
            'func_raw': func_raw,
            'frequency': frequency,
            'period': period,
            'sample_rate': 10000,
        }

    def read_wave(self, n_samples: int = 1000) -> List[float]:
        """Synthesize a waveform matching the current AWG config."""
        cfg = self.get_config()
        freq = cfg['frequency']
        wave_type = cfg['wave_type']
        sample_rate = cfg['sample_rate']

        t = np.linspace(0, n_samples / sample_rate, n_samples, endpoint=False)

        if wave_type == 'senoidal':
            signal = np.sin(2 * np.pi * freq * t)
        elif wave_type == 'cuadrada':
            signal = np.sign(np.sin(2 * np.pi * freq * t))
        elif wave_type == 'triangular':
            signal = 2 * np.abs(2 * ((freq * t) % 1) - 1) - 1
        elif wave_type == 'sierra':
            signal = 2 * ((freq * t) % 1) - 1
        elif wave_type == 'ruido':
            signal = np.random.normal(0, 0.3, n_samples)
        else:
            signal = np.sin(2 * np.pi * freq * t)

        return list(signal * 0.5)

    def read_channel(self, channel: int = 1) -> Tuple[List[float], dict]:
        data = self.read_wave()
        cfg = self.get_config()
        params = {
            'v_scale': 1.0,
            'h_scale': cfg['period'] / 10,
            'sample_rate': cfg['sample_rate'],
        }
        return data, params

    def get_id(self) -> str:
        try:
            return self._query('*IDN?').strip().replace('->', '').strip()
        except Exception:
            return "Unknown"

    def is_connected(self) -> bool:
        return self.connected
```

- [ ] **Step 2: Run test to verify it works**

Run:
```bash
python -c "from awg import AWG; a=AWG(); print(a.connect()); print(a.get_config()); a.disconnect()"
```

Expected: Connects successfully, prints config dict with wave_type, frequency, etc.

---

## Task 2: Integrate AWG into `main.py`

**Files:**
- Modify: `main.py`
- Test: `python main.py --awg`

- [ ] **Step 3: Add `--awg` argument and import**

At top of `main.py`, add:
```python
from awg import AWG
```

In `WaveReader.__init__`, change to:
```python
    def __init__(self, use_simulator: bool = False, use_awg: bool = False,
                 frequency: float = 50.0, wave_type: Optional[str] = None):
        self.use_simulator = use_simulator
        self.use_awg = use_awg

        if use_awg:
            self.scope = AWG()
        elif use_simulator:
            self.scope = OscilloscopeSimulator(frequency=frequency, wave_type=wave_type)
        else:
            self.scope = Oscilloscope()
```

In `WaveReader.connect`, change print to:
```python
        device_name = "AWG" if self.use_awg else "osciloscopio"
        print(f"Conectando al {device_name}...")
```

And in failure message:
```python
            print(f"Error: No se pudo conectar")
            print("Sugerencias:")
            if self.use_awg:
                print("  1. Verifica que el AWG este conectado por USB")
                print("  2. Verifica que este encendido")
                print("  3. Usa --simulator para probar sin hardware")
            else:
                print("  1. Verifica que el osciloscopio este conectado por USB")
                print("  2. Verifica que este encendido y en modo PC/USBTMC")
                print("  3. Usa --simulator para probar sin hardware")
```

- [ ] **Step 4: Add CLI argument**

In `main()` argument parser, add:
```python
    parser.add_argument("--awg", action="store_true",
                        help="Usar AWG AG051 en lugar de osciloscopio")
```

And change the reader instantiation:
```python
    reader = WaveReader(use_simulator=args.simulator, use_awg=args.awg,
                        frequency=args.frequency, wave_type=args.wave_type)
```

- [ ] **Step 5: Test end-to-end**

Run:
```bash
python main.py --awg
```

Expected: Connects to AWG, reads config, synthesizes waveform, classifies it, saves to DB.

---

## Task 3: Update `requirements.txt`

- [ ] **Step 6: Ensure dependencies are listed**

`requirements.txt` should already have `pyusb` and `libusb-package` from earlier fixes. Verify:
```
flask
pyvisa
pyvisa-py
numpy
pyusb
libusb-package
```

---

## Spec Coverage Checklist

- [x] AG051 can be detected and connected via PyUSB
- [x] AG051 configuration (wave type, frequency) can be read
- [x] Synthetic waveform generation matches reported config
- [x] `--awg` CLI flag selects AWG instead of oscilloscope
- [x] Existing simulator and oscilloscope paths remain untouched
- [x] Classifier and database integration work unchanged

## Placeholder Scan

- No TBD/TODO/fill-in-details found
- All code blocks are complete and copy-paste ready
- All commands have exact expected output
