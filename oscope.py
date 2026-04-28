import pywinusb.hid as hid
from typing import List, Optional, Tuple
import numpy as np
import time


class Oscilloscope:
    VID = 0x5345
    PID = 0x1234

    def __init__(self):
        self.device = None
        self.connected = False

    def connect(self) -> bool:
        try:
            all_devices = hid.find_all_hid_devices()
            
            device = None
            for d in all_devices:
                if d.vendor_id == self.VID and d.product_id == self.PID:
                    device = d
                    break
            
            if device is None:
                print("Dispositivo no encontrado")
                print(f"Buscando VID={hex(self.VID)}, PID={hex(self.PID)}")
                return False
            
            try:
                device.open()
                self.device = device
                self.connected = True
                
                print(f"Conectado a: {device.product_name}")
                return True
                
            except Exception as e:
                print(f"Error abriendo dispositivo: {e}")
                return False

        except Exception as e:
            print(f"Error conectando: {e}")
            import traceback
            traceback.print_exc()
            self.connected = False
            return False

    def disconnect(self):
        if self.device:
            try:
                self.device.close()
            except:
                pass
        self.connected = False

    def send_command(self, command: str) -> bytes:
        if not self.connected:
            raise RuntimeError("No conectado")
        
        command_bytes = (command + "\n").encode('utf-8')
        
        try:
            self.device.send_feature_report(command_bytes)
            time.sleep(0.1)
            
            data = self.device.get_input_report()
            if data:
                return bytes(data)
            
            return b""
            
        except Exception as e:
            print(f"Error send_command: {e}")
            raise

    def get_id(self) -> str:
        try:
            response = self.send_command("*IDN?")
            return response.decode('utf-8').strip('\x00 \n')
        except:
            return "Unknown"

    def read_wave(self, channel: int = 1) -> List[float]:
        if not self.connected:
            raise RuntimeError("No conectado")
        
        command = f":DATA:WAVE:SCREen:CH{channel}?"
        
        try:
            response = self.send_command(command)
            data = self._parse_wave_data(response)
            return data
        except Exception as e:
            print(f"Error leyendo onda CH{channel}: {e}")
            return []

    def _parse_wave_data(self, response: bytes) -> List[float]:
        if len(response) < 4:
            return []
        
        data = []
        raw = response
        
        for i in range(4, len(raw), 2):
            if i + 1 < len(raw):
                try:
                    value = int.from_bytes([raw[i], raw[i+1]], 'little', signed=True)
                    normalized = value / 4096.0
                    data.append(normalized)
                except:
                    pass
        
        return data

    def read_channel(self, channel: int = 1) -> Tuple[List[float], dict]:
        data = self.read_wave(channel)
        
        params = {}
        if data:
            params = {
                "v_scale": 1.0,
                "h_scale": 0.001,
            }
        
        return data, params

    def is_connected(self) -> bool:
        return self.connected


class OscilloscopeSimulator:
    def __init__(self):
        self.connected = True

    def connect(self) -> bool:
        return True

    def disconnect(self):
        pass

    def get_id(self) -> str:
        return "OWON,SDS1202,1234567,V2.4.0"

    def read_wave(self, channel: int = 1) -> List[float]:
        t = np.linspace(0, 0.01, 1000)
        
        wave_types = ["senoidal", "cuadrada", "triangular", "sierra", "ruido"]
        wave_type = wave_types[channel % len(wave_types)]
        
        if wave_type == "senoidal":
            return list(np.sin(2 * np.pi * 50 * t) * 0.5 + 0.5)
        elif wave_type == "cuadrada":
            return list((np.sin(2 * np.pi * 50 * t) > 0).astype(float))
        elif wave_type == "triangular":
            return list(np.abs((t * 100) % 2 - 1) * 0.5)
        elif wave_type == "sierra":
            return list((t * 200) % 1 * 0.5)
        else:
            noise = np.random.normal(0.5, 0.1, 1000)
            return list(noise)

    def read_channel(self, channel: int = 1) -> Tuple[List[float], dict]:
        data = self.read_wave(channel)
        params = {
            "v_scale": 1.0,
            "h_scale": 0.001,
        }
        return data, params

    def is_connected(self) -> bool:
        return self.connected