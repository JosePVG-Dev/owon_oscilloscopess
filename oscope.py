import os
import pyvisa
from typing import List, Optional, Tuple
import numpy as np

try:
    import libusb_package
    _libusb_dir = os.path.dirname(libusb_package.get_library_path())
    if _libusb_dir not in os.environ.get('PATH', ''):
        os.environ['PATH'] = _libusb_dir + os.pathsep + os.environ.get('PATH', '')
except Exception:
    pass


class Oscilloscope:
    VID = 0x5345
    PID = 0x1234

    def __init__(self):
        self.resource = None
        self.rm = None
        self.connected = False

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def _find_resource(self) -> Optional[str]:
        if self.rm is None:
            return None
        try:
            resources = self.rm.list_resources()
        except Exception:
            return None

        for resource in resources:
            if f'0x{self.VID:04x}' in resource.lower() or f'{self.VID}' in resource:
                return resource

        for resource in resources:
            if 'USB' in resource.upper() and 'INSTR' in resource.upper():
                return resource

        return None

    def connect(self) -> bool:
        try:
            self.rm = pyvisa.ResourceManager('@py')
            resource = self._find_resource()

            if resource is None:
                print("Dispositivo no encontrado")
                print("Recursos disponibles:")
                try:
                    for r in self.rm.list_resources():
                        print(f"  {r}")
                except Exception:
                    pass
                print("\nSugerencias:")
                print("  1. Verifica que el osciloscopio este conectado por USB y encendido")
                print("  2. Verifica que este en modo PC/USBTMC (no UDisk)")
                print("  3. Instala pyvisa-py: pip install pyvisa-py")
                print("  4. En Linux: sudo apt-get install libusb-1.0-0-dev")
                self._cleanup()
                return False

            self.resource = self.rm.open_resource(resource)
            self.resource.timeout = 5000
            self.resource.chunk_size = 102400
            self.resource.write_termination = '\r'
            self.resource.read_termination = '\n'

            idn = self.resource.query("*IDN?")
            print(f"Conectado a: {idn.strip()}")
            self.connected = True
            return True

        except pyvisa.errors.VisaIOError as e:
            print(f"Error de conexion VISA: {e}")
            print("\nSugerencias:")
            print("  1. Verifica que el osciloscopio este conectado y encendido")
            print("  2. Verifica modo USB en el osciloscopio (PC/USBTMC)")
            print("  3. En Windows: instalar NI-VISA o usar pyvisa-py backend")
            print("  4. En Linux: sudo apt-get install libusb-1.0-0-dev")
            self._cleanup()
            return False
        except Exception as e:
            print(f"Error conectando: {e}")
            self._cleanup()
            return False

    def _cleanup(self):
        if self.resource:
            try:
                self.resource.close()
            except Exception:
                pass
            self.resource = None
        if self.rm:
            try:
                self.rm.close()
            except Exception:
                pass
            self.rm = None
        self.connected = False

    def disconnect(self):
        self._cleanup()
        print("Desconectado")

    def send_command(self, command: str) -> str:
        if not self.connected or not self.resource:
            raise RuntimeError("No conectado")
        try:
            if command.strip().endswith("?"):
                return self.resource.query(command)
            else:
                self.resource.write(command)
                return ""
        except pyvisa.errors.VisaIOError as e:
            print(f"Error en comando '{command}': {e}")
            raise

    def send_query_raw(self, command: str) -> bytes:
        if not self.connected or not self.resource:
            raise RuntimeError("No conectado")
        try:
            self.resource.write(command)
            return self.resource.read_raw()
        except pyvisa.errors.VisaIOError as e:
            print(f"Error en consulta raw '{command}': {e}")
            raise

    def get_id(self) -> str:
        try:
            return self.send_command("*IDN?").strip()
        except Exception:
            return "Unknown"

    def read_wave(self, channel: int = 1) -> List[float]:
        if not self.connected or not self.resource:
            raise RuntimeError("No conectado")

        try:
            raw = self.send_query_raw(f":DATA:WAVE:SCREen:CH{channel}?")
            return self._parse_wave_data(raw)
        except pyvisa.errors.VisaIOError as e:
            print(f"Error leyendo onda CH{channel}: {e}")
            return []

    def _parse_wave_data(self, raw: bytes) -> List[float]:
        if len(raw) < 2:
            return []

        # Format 1: IEEE 488.2 definite-length block (#NXXXXX...data...)
        header_pos = raw.find(b'#')
        if header_pos >= 0 and header_pos + 1 < len(raw):
            try:
                n_digits = int(chr(raw[header_pos + 1]))
                if header_pos + 1 + n_digits < len(raw):
                    skip = header_pos + 2 + n_digits
                    data_bytes = raw[skip:skip + int(raw[header_pos + 2:skip])]
                    return self._decode_int16_samples(data_bytes)
            except (ValueError, IndexError):
                pass

        # Format 2: OWON raw format: [4 bytes LE: byte_count][int16 LE samples...]
        if len(raw) >= 4:
            byte_count = int.from_bytes(raw[:4], 'little', signed=False)
            if byte_count > 0 and byte_count <= len(raw) - 4:
                data_bytes = raw[4:4 + byte_count]
                return self._decode_int16_samples(data_bytes)
            # byte_count == 0 means no data available
            if byte_count == 0:
                return []

        # Format 3: Raw int16 samples (no header, fallback)
        return self._decode_int16_samples(raw)

    def _decode_int16_samples(self, data_bytes: bytes) -> List[float]:
        values = []
        # OWON uses 8-bit ADC values packed as bytes, or could be int16
        # Each sample is 1-2 bytes depending on format
        # Try parsing as 2-byte int16 LE first
        for i in range(0, len(data_bytes) - 1, 2):
            try:
                value = int.from_bytes(data_bytes[i:i+2], 'little', signed=True)
                normalized = value / 128.0
                values.append(normalized)
            except Exception:
                continue

        # If no values parsed (odd length or single byte), try as uint8
        if len(values) == 0 and len(data_bytes) > 0:
            for b in data_bytes:
                normalized = (b - 128) / 128.0
                values.append(normalized)

        return values

    def read_channel(self, channel: int = 1) -> Tuple[List[float], dict]:
        data = self.read_wave(channel)

        params = {}
        if data:
            try:
                scale_resp = self.send_command(f":CH{channel}:SCAL?")
                v_scale = float(scale_resp.strip().replace('->', ''))
            except Exception:
                v_scale = 1.0

            try:
                time_resp = self.send_command(":HOR:SCAL?")
                h_scale = float(time_resp.strip().replace('->', ''))
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

    def is_connected(self) -> bool:
        return self.connected


class OscilloscopeSimulator:
    def __init__(self, frequency: float = 50.0, wave_type: Optional[str] = None, sample_rate: int = 1000):
        self.connected = True
        self._last_wave_type = None
        self.frequency = frequency
        self.wave_type = wave_type
        self.sample_rate = sample_rate

    def connect(self) -> bool:
        return True

    def disconnect(self):
        pass

    def get_id(self) -> str:
        return "OWON,SDS1202,SIMULATOR,V1.0.0"

    def send_command(self, command: str) -> str:
        if command.strip() == "*IDN?":
            return "OWON,SDS1202,SIMULATOR,V1.0.0"
        return ""

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

    def read_channel(self, channel: int = 1) -> Tuple[List[float], dict]:
        data = self.read_wave(channel)
        params = {
            "v_scale": 1.0,
            "h_scale": 1.0 / self.frequency,
            "sample_rate": self.sample_rate,
        }
        return data, params

    def is_connected(self) -> bool:
        return self.connected