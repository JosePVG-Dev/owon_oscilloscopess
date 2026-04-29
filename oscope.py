import pyvisa
from typing import List, Optional, Tuple
import numpy as np


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
        try:
            rm = pyvisa.ResourceManager('@py')
            resources = rm.list_resources()
            rm.close()
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

        command = f":DATA:WAVE:SCREen:CH{channel}?"

        try:
            raw = self.send_query_raw(command)
            data = self._parse_wave_data(raw)
            return data
        except Exception as e:
            print(f"Error leyendo onda CH{channel}: {e}")
            return []

    def _parse_wave_data(self, raw: bytes) -> List[float]:
        if len(raw) < 2:
            return []

        try:
            header_pos = raw.find(b'#')
            if header_pos >= 0:
                num_digits = int(chr(raw[header_pos + 1]))
                data_length = int(raw[header_pos + 2:header_pos + 2 + num_digits])
                data_start = header_pos + 2 + num_digits
            else:
                data_start = 4
                data_length = len(raw) - data_start

            data_bytes = raw[data_start:data_start + data_length]
        except (ValueError, IndexError):
            data_start = 4
            data_bytes = raw[data_start:]

        values = []
        for i in range(0, len(data_bytes) - 1, 2):
            try:
                value = int.from_bytes(data_bytes[i:i+2], 'little', signed=True)
                normalized = value / 128.0
                values.append(normalized)
            except Exception:
                continue

        return values

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