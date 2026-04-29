# OWON SDS1202 - Lector de Ondas

Programa Python para leer ondas de un osciloscopio OWON SDS1202, clasificarlas y guardarlas en SQLite.

## Requisitos

- Python 3.7+
- Librerías: `pyvisa`, `pyvisa-py`, `numpy`, `flask`

```bash
python -m venv venv
.\venv\Scripts\Activate.ps1   # Windows
pip install -r requirements.txt
```

## Uso

### Modo simulador (pruebas, sin hardware)
```bash
python main.py --simulator
```

### Modo simulador en loop continuo
```bash
python main.py --simulator --loop --interval 5
```

### Con osciloscopio real
```bash
python main.py -c 1
```

### Dashboard web
```bash
python dashboard.py          # http://localhost:5000
```

### Captura + Dashboard juntos
```bash
python run.py --simulator
```

### Ver registros
```bash
python main.py --recent 10
```

## Clasificación

| Onda | Ola Marítima |
|------|--------------|
| Senoidal | Ola Suave |
| Cuadrada | Ola Rompiente |
| Triangular | Ola de Rebote |
| Sierra | Ola de Tormenta |
| Ruido | Mar Agitado |

## Conexión

La conexión usa **PyVISA** (USBTMC). No requiere drivers adicionales si se usa `pyvisa-py`.

Si hay problemas de conexión:
1. Verifica que el osciloscopio esté en modo **PC/USBTMC** (no UDisk)
2. Instala NI-VISA si pyvisa-py no detecta el dispositivo
3. Usa `--simulator` para probar sin hardware