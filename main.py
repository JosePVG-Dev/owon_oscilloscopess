from oscope import Oscilloscope, OscilloscopeSimulator
from awg import AWG
from classifier import Classifier, WaveType, SeaType
from database import Database
from typing import Optional
import time
import argparse
import sys


class WaveReader:
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
        
        self.classifier = Classifier()
        self.db = Database()

    def connect(self) -> bool:
        device_name = "AWG" if self.use_awg else "osciloscopio"
        print(f"Conectando al {device_name}...")
        
        connected = self.scope.connect()
        
        if connected:
            print("Conexion exitosa!")
            try:
                print(f"ID: {self.scope.get_id()}")
            except Exception:
                print(f"{device_name.capitalize()} conectado (ID no disponible)")
            return True
        else:
            print("Error: No se pudo conectar")
            print("Sugerencias:")
            if self.use_awg:
                print("  1. Verifica que el AWG este conectado por USB")
                print("  2. Verifica que este encendido")
                print("  3. Usa --simulator para probar sin hardware")
            else:
                print("  1. Verifica que el osciloscopio este conectado por USB")
                print("  2. Verifica que este encendido y en modo PC/USBTMC")
                print("  3. Usa --simulator para probar sin hardware")
            return False

    def read_and_save(self, channel: int = 1):
        print(f"\nLeyendo canal CH{channel}...")

        try:
            data, params = self.scope.read_channel(channel)
        except Exception as e:
            print(f"Error leyendo del dispositivo: {e}")
            data, params = [], {}

        if not data or len(data) < 10:
            if self.use_awg:
                print("AWG no responde, no se pueden obtener datos")
            else:
                print("Datos insuficientes, usando simulador...")
                simulator = OscilloscopeSimulator()
                data = simulator.read_wave(channel)
                params = {"v_scale": 1.0, "h_scale": 0.001, "sample_rate": 1000}

        sample_rate = params.get("sample_rate", 1000)
        self.classifier = Classifier(sample_rate=sample_rate)

        print(f"  Muestras: {len(data)} | Sample rate: {sample_rate} Hz | V/div: {params.get('v_scale', '?')} | T/div: {params.get('h_scale', '?')}s")

        wave_type, sea_type = self.classifier.classify_and_map(data)
        params_report = self.classifier.get_parameters(data)
        
        print(f"  Tipo de onda: {wave_type.value}")
        print(f"  Tipo de ola: {sea_type.value}")
        
        if params_report:
            print(f"  Amplitud: {params_report.get('amplitude', 0):.4f} V")
            print(f"  Frecuencia: {params_report.get('frequency', 0):.2f} Hz")
            print(f"  Periodo: {params_report.get('period', 0):.6f} s")
        
        db_id = self.db.save_waveform(
            wave_type=wave_type.value,
            sea_type=sea_type.value,
            channel=f"CH{channel}",
            amplitude=params_report.get("amplitude") if params_report else None,
            frequency=params_report.get("frequency") if params_report else None,
            period=params_report.get("period") if params_report else None
        )
        
        print(f"  Guardado en BD (ID: {db_id})")
        
        return {
            "id": db_id,
            "channel": f"CH{channel}",
            "wave_type": wave_type.value,
            "sea_type": sea_type.value,
            "data": data
        }

    def read_both_channels(self):
        result_ch1 = self.read_and_save(channel=1)
        result_ch2 = self.read_and_save(channel=2)
        
        return [result_ch1, result_ch2]

    def loop(self, interval: float = 5.0, channels: list = None):
        if channels is None:
            channels = [1, 2]
        
        print(f"\nIniciando lectura automatica cada {interval} segundos...")
        print("Presiona Ctrl+C para detener\n")
        
        try:
            iteration = 0
            while True:
                iteration += 1
                print(f"\n{'='*50}")
                print(f"Iteracion #{iteration}")
                print(f"{'='*50}")
                
                for ch in channels:
                    try:
                        self.read_and_save(channel=ch)
                    except Exception as e:
                        print(f"Error leyendo CH{ch}: {e}")
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n\nDetenido por usuario")

    def show_recent(self, limit: int = 10):
        records = self.db.get_recent(limit)
        
        print(f"\nUltimas {limit} lecturas:")
        print("-" * 70)
        
        for row in records:
            print(f"ID: {row['id']} | {row['timestamp']} | {row['channel']}")
            print(f"  Onda: {row['wave_type']} => Ola: {row['sea_type']}")
            if row['frequency']:
                print(f"  Frecuencia: {row['frequency']:.2f} Hz | Periodo: {row['period']:.6f} s")
            print()

    def disconnect(self):
        self.scope.disconnect()


def main():
    parser = argparse.ArgumentParser(description="Lector de ondas OWON SDS1202")
    parser.add_argument("--simulator", "-s", action="store_true",
                        help="Usar simulador en lugar de osciloscopio real")
    parser.add_argument("--awg", action="store_true",
                        help="Usar AWG AG051 en lugar de osciloscopio")
    parser.add_argument("--channel", "-c", type=int, default=1,
                        help="Canal a leer (1 o 2, default: 1)")
    parser.add_argument("--loop", "-l", action="store_true",
                        help="Modo loop continuo")
    parser.add_argument("--interval", type=float, default=5.0,
                        help="Intervalo entre lecturas en segundos (default: 5)")
    parser.add_argument("--recent", "-r", type=int, default=0,
                        help="Mostrar recent N registros y salir")
    parser.add_argument("--all", "-a", action="store_true",
                        help="Leer todos los canales (CH1 y CH2)")
    parser.add_argument("--frequency", type=float, default=50.0,
                        help="Frecuencia del simulador en Hz (default: 50)")
    parser.add_argument("--wave-type", type=str, default=None,
                        choices=["senoidal", "cuadrada", "triangular", "sierra", "ruido"],
                        help="Tipo de onda del simulador (default: aleatorio)")
    
    args = parser.parse_args()

    if args.simulator and args.awg:
        parser.error("--simulator y --awg son mutuamente excluyentes")
    
    if args.recent > 0:
        reader = WaveReader(use_simulator=True)
        reader.show_recent(args.recent)
        return
    
    reader = WaveReader(use_simulator=args.simulator, use_awg=args.awg,
                        frequency=args.frequency, wave_type=args.wave_type)
    
    if not reader.connect():
        sys.exit(1)
    
    try:
        if args.loop:
            channels = [1, 2] if args.all else [args.channel]
            reader.loop(interval=args.interval, channels=channels)
        elif args.all:
            reader.read_both_channels()
        else:
            reader.read_and_save(channel=args.channel)
            reader.show_recent(5)
    
    finally:
        reader.disconnect()


if __name__ == "__main__":
    main()