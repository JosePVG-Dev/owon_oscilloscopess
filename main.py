from oscope import Oscilloscope, OscilloscopeSimulator
from classifier import Classifier, WaveType, SeaType
from database import Database
import time
import argparse
import sys


class WaveReader:
    def __init__(self, use_simulator: bool = False):
        self.use_simulator = use_simulator
        
        if use_simulator:
            self.scope = OscilloscopeSimulator()
        else:
            self.scope = Oscilloscope()
        
        self.classifier = Classifier()
        self.db = Database()

    def connect(self) -> bool:
        print("Conectando al osciloscopio...")
        
        if self.use_simulator:
            connected = self.scope.connect()
        else:
            connected = self.scope.connect()
        
        if connected:
            print("Conexión exitosa!")
            if self.use_simulator:
                print(f"ID: {self.scope.get_id()}")
            else:
                try:
                    print(f"ID: {self.scope.get_id()}")
                except:
                    print("Osciloscopio conectado (ID no disponible)")
            return True
        else:
            print("Error: No se pudo conectar")
            print("Sugerencias:")
            print("  1. Verifica que el osciloscopio esté conectado por USB")
            print("  2. Verifica que esté encendido")
            print("  3. En Windows, puede requerir driver WinUSB (usar Zadig)")
            return False

    def read_and_save(self, channel: int = 1):
        print(f"\nLeyendo canal CH{channel}...")
        
        data = self.scope.read_wave(channel)
        
        if not data or len(data) < 10:
            print("Datos insuficientes, usando simulador...")
            data = self.scope.read_wave(channel)
        
        wave_type, sea_type = self.classifier.classify_and_map(data)
        params = self.classifier.get_parameters(data)
        
        print(f"  Tipo de onda: {wave_type.value}")
        print(f"  Tipo de ola: {sea_type.value}")
        
        if params:
            print(f"  Amplitud: {params.get('amplitude', 0):.4f} V")
            print(f"  Frecuencia: {params.get('frequency', 0):.2f} Hz")
            print(f"  Período: {params.get('period', 0):.6f} s")
        
        db_id = self.db.save_waveform(
            wave_type=wave_type.value,
            sea_type=sea_type.value,
            channel=f"CH{channel}",
            amplitude=params.get("amplitude") if params else None,
            frequency=params.get("frequency") if params else None,
            period=params.get("period") if params else None
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
        
        print(f"\nIniciando lettura automática cada {interval} segundos...")
        print("Presiona Ctrl+C para detener\n")
        
        try:
            iteration = 0
            while True:
                iteration += 1
                print(f"\n{'='*50}")
                print(f"Iteración #{iteration}")
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
        
        print(f"\nÚltimas {limit} lecturas:")
        print("-" * 70)
        
        for row in records:
            print(f"ID: {row['id']} | {row['timestamp']} | {row['channel']}")
            print(f"  Onda: {row['wave_type']} => Ola: {row['sea_type']}")
            if row['frequency']:
                print(f"  Frecuencia: {row['frequency']:.2f} Hz | Período: {row['period']:.6f} s")
            print()

    def disconnect(self):
        if not self.use_simulator:
            self.scope.disconnect()
        print("Desconectado")


def main():
    parser = argparse.ArgumentParser(description="Lector de ondas OWON SDS1202")
    parser.add_argument("--simulator", "-s", action="store_true",
                        help="Usar simulador en lugar de osciloscopio real")
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
    
    args = parser.parse_args()
    
    reader = WaveReader(use_simulator=args.simulator)
    
    if not reader.connect():
        sys.exit(1)
    
    try:
        if args.recent > 0:
            reader.show_recent(args.recent)
        elif args.loop:
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