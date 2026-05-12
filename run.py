import subprocess
import sys
import signal
import argparse


def main():
    parser = argparse.ArgumentParser(description="OWON SDS1202 - Captura + Dashboard")
    parser.add_argument("--simulator", "-s", action="store_true",
                        help="Usar simulador en lugar de osciloscopio real")
    parser.add_argument("--awg", action="store_true",
                        help="Usar AWG AG051 en lugar de osciloscopio")
    parser.add_argument("--interval", type=float, default=2.0,
                        help="Intervalo entre lecturas en segundos (default: 2)")
    parser.add_argument("--port", type=int, default=5000,
                        help="Puerto del dashboard (default: 5000)")
    parser.add_argument("--channel", "-c", type=int, default=1,
                        help="Canal a leer (default: 1)")
    parser.add_argument("--all", "-a", action="store_true",
                        help="Leer todos los canales")
    parser.add_argument("--frequency", type=float, default=50.0,
                        help="Frecuencia del simulador en Hz (default: 50)")
    parser.add_argument("--wave-type", type=str, default=None,
                        choices=["senoidal", "cuadrada", "triangular", "sierra", "ruido"],
                        help="Tipo de onda del simulador (default: aleatorio)")
    args = parser.parse_args()

    capture_cmd = [sys.executable, "main.py", "--loop"]
    if args.simulator:
        capture_cmd.append("--simulator")
    elif args.awg:
        capture_cmd.append("--awg")
    capture_cmd.extend(["--interval", str(args.interval)])
    capture_cmd.extend(["--frequency", str(args.frequency)])
    if args.wave_type:
        capture_cmd.extend(["--wave-type", args.wave_type])
    if args.all:
        capture_cmd.append("--all")
    else:
        capture_cmd.extend(["--channel", str(args.channel)])

    dashboard_cmd = [sys.executable, "dashboard.py"]

    mode_str = ""
    if args.simulator:
        mode_str = " (simulador)"
    elif args.awg:
        mode_str = " (AWG)"

    print("=" * 50)
    print("  OWON SDS1202 - Captura + Dashboard")
    print("=" * 50)
    print(f"  Captura: cada {args.interval}s{mode_str}")
    print(f"  Dashboard: http://localhost:{args.port}")
    print("  Presiona Ctrl+C para detener ambos")
    print("=" * 50)

    procs = []
    try:
        cap_proc = subprocess.Popen(capture_cmd)
        procs.append(cap_proc)
        print(f"  [OK] Captura iniciada (PID {cap_proc.pid})")

        dash_proc = subprocess.Popen(dashboard_cmd)
        procs.append(dash_proc)
        print(f"  [OK] Dashboard iniciado (PID {dash_proc.pid})")

        for p in procs:
            p.wait()
    except KeyboardInterrupt:
        print("\n\nDeteniendo procesos...")
    finally:
        for p in procs:
            try:
                p.terminate()
                p.wait(timeout=5)
            except Exception:
                p.kill()
        print("Todos los procesos detenidos.")


if __name__ == "__main__":
    main()