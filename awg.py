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
    """Driver for OWON AG051 Arbitrary Waveform Generator via PyUSB.

    The AG051 uses a simplified SCPI dialect over USB bulk endpoints.
    Commands terminate with \\r; responses end with \\n->.
    PyUSB is required because the device does not expose a standard
    USBTMC/VISA interface.
    """

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

    CONFIG_CACHE_TTL = 2.0  # segundos

    def __init__(self, vid: int = 0x5345, pid: int = 0x1234,
                 serial: str = 'AG0512117060',
                 endpoint_out: int = 3, endpoint_in: int = 0x81):
        self.vid = vid
        self.pid = pid
        self.serial = serial
        self.endpoint_out = endpoint_out
        self.endpoint_in = endpoint_in
        self.dev = None
        self.connected = False
        self._last_config: Optional[dict] = None
        self._last_config_time: float = 0.0

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def connect(self) -> bool:
        try:
            self.dev = usb.core.find(
                idVendor=self.vid,
                idProduct=self.pid,
                serial_number=self.serial
            )
            if self.dev is None:
                print("AWG no encontrado")
                return False
            self.dev.set_configuration()
            # Limpiar buffer residual del dispositivo
            self._clear_buffer()
            idn = self._query('*IDN?')
            print(f"Conectado a: {idn}")
            self.connected = True
            return True
        except usb.core.USBError as e:
            print(f"Error de USB conectando AWG: {e}")
            self.connected = False
            return False
        except Exception as e:
            print(f"Error conectando AWG: {e}")
            self.connected = False
            return False

    def disconnect(self):
        self.dev = None
        self.connected = False
        print("Desconectado")

    def _clear_buffer(self):
        """Lee y descarta cualquier dato residual en el endpoint IN."""
        if not self.dev:
            return
        for _ in range(5):
            try:
                self.dev.read(self.endpoint_in, 10000, 200)
            except Exception:
                break

    def _reconnect(self) -> bool:
        """Intenta reconectar silenciosamente."""
        try:
            self.dev = usb.core.find(
                idVendor=self.vid,
                idProduct=self.pid,
                serial_number=self.serial
            )
            if self.dev is None:
                return False
            self.dev.set_configuration()
            self.connected = True
            return True
        except Exception:
            return False

    def _query(self, cmd: str, delay: float = 0.4, timeout: int = 800,
               retries: int = 3) -> str:
        if not self.dev:
            raise RuntimeError("No conectado")

        last_error = None
        for attempt in range(retries):
            try:
                self.dev.write(self.endpoint_out, (cmd + '\r').encode())
                time.sleep(delay)
                raw = self.dev.read(self.endpoint_in, 10000, timeout)
                text = raw.tobytes().decode('utf-8', errors='ignore')
                return text.replace('->', '').strip()
            except usb.core.USBError as e:
                last_error = e
                if attempt < retries - 1:
                    # Intentar reconectar antes del siguiente retry
                    time.sleep(0.5)
                    if not self._reconnect():
                        time.sleep(0.5)
                else:
                    raise

        raise last_error if last_error else RuntimeError("Query fallo tras reintentos")

    def send_command(self, command: str) -> str:
        if not self.connected or not self.dev:
            raise RuntimeError("No conectado")
        try:
            if command.strip().endswith("?"):
                return self._query(command)
            else:
                self._query(command)
                return ""
        except usb.core.USBError as e:
            print(f"Error en comando '{command}': {e}")
            raise

    def get_config(self, use_cache: bool = True) -> dict:
        """Read current AWG configuration. Uses cache if recent."""
        now = time.time()
        if use_cache and self._last_config is not None:
            if (now - self._last_config_time) < self.CONFIG_CACHE_TTL:
                return self._last_config

        func_raw = self._query(':FUNC?')
        freq_raw = self._query(':FREQ?')
        per_raw = self._query(':PER?')

        try:
            frequency = float(freq_raw)
        except ValueError:
            frequency = 1000.0

        try:
            period = float(per_raw)
        except ValueError:
            period = 1.0 / frequency if frequency > 0 else 0.001

        wave_type = self.WAVE_MAP.get(func_raw.upper(), 'senoidal')

        cfg = {
            'wave_type': wave_type,
            'func_raw': func_raw,
            'frequency': frequency,
            'period': period,
            'sample_rate': 10000,
        }
        self._last_config = cfg
        self._last_config_time = now
        return cfg

    def _synthesize(self, cfg: dict, n_cycles: int = 5) -> List[float]:
        """Generate waveform from config dict."""
        freq = cfg['frequency']
        wave_type = cfg['wave_type']
        sample_rate = cfg['sample_rate']

        if freq <= 0:
            return []

        duration = n_cycles / freq
        n_samples = max(int(duration * sample_rate), 100)
        t = np.linspace(0, duration, n_samples, endpoint=False)

        if wave_type == 'senoidal':
            signal = np.sin(2 * np.pi * freq * t)
        elif wave_type == 'cuadrada':
            signal = np.sign(np.sin(2 * np.pi * freq * t))
        elif wave_type == 'triangular':
            signal = (2 * np.abs(2 * (freq * t - np.floor(freq * t + 0.5))) - 1)
        elif wave_type == 'sierra':
            signal = (2 * (freq * t - np.floor(freq * t)) - 1)
        elif wave_type == 'ruido':
            signal = np.random.normal(0, 0.15, n_samples)
        else:
            signal = np.sin(2 * np.pi * freq * t)

        return list(signal * 0.5)

    def read_wave(self, n_cycles: int = 5) -> List[float]:
        """Synthesize a waveform matching the current AWG config.
        
        If the AWG is unreachable, uses the last known config (cache).
        If no cache exists, uses a sensible default (1 kHz sine).
        Never returns empty data.
        """
        cfg = None
        try:
            cfg = self.get_config(use_cache=False)
        except Exception as e:
            if self._last_config is not None:
                print(f"AWG no responde, usando config cacheada: {self._last_config['wave_type']} @ {self._last_config['frequency']} Hz")
                cfg = self._last_config
            else:
                print(f"AWG config error: {e}, intentando reconectar...")
                if self._reconnect():
                    try:
                        cfg = self.get_config(use_cache=False)
                    except Exception as e2:
                        print(f"AWG reconnexion fallo: {e2}")

        if cfg is None and self._last_config is not None:
            cfg = self._last_config

        if cfg is None:
            # Default fallback — nunca devolvemos vacio
            cfg = {
                'wave_type': 'senoidal',
                'func_raw': 'SINE',
                'frequency': 1000.0,
                'period': 0.001,
                'sample_rate': 10000,
            }
            print("AWG sin config conocida, usando default: senoidal @ 1000 Hz")

        freq = cfg['frequency']
        if freq <= 0:
            if self._last_config is not None and self._last_config['frequency'] > 0:
                print(f"AWG freq=0, usando cache: {self._last_config['frequency']} Hz")
                cfg = self._last_config
                freq = cfg['frequency']
            else:
                freq = 1000.0
                cfg['frequency'] = freq
                cfg['period'] = 0.001
                print("AWG frecuencia <= 0, usando default 1000 Hz")

        return self._synthesize(cfg, n_cycles)

    def read_channel(self, channel: int = 1) -> Tuple[List[float], dict]:
        data = self.read_wave()
        if not data:
            return [], {}

        cfg = self.get_config(use_cache=True)
        params = {
            'v_scale': 1.0,
            'h_scale': cfg['period'] / 10,
            'sample_rate': cfg['sample_rate'],
        }
        return data, params

    def get_id(self) -> str:
        try:
            return self._query('*IDN?')
        except Exception:
            return "Unknown"

    def is_connected(self) -> bool:
        return self.connected
