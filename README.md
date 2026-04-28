# OWON SDS1202 - Lector de Ondas

Programa Python para leer ondas de un osciloscopio OWON SDS1202, clasificarlas y guardarlas en SQLite.

## Requisitos

- Python 3.7+
- Librerías: `pyusb`, `numpy`

```bash
pip install -r requirements.txt
```

## Estructura

```
owon_oscilloscope/
├── main.py       # Punto de entrada
├── oscope.py    # Conexión USB/SCPI
├── classifier.py # Clasificación ondas → olas
├── database.py  # SQLite
├── requirements.txt
└── waveforms.db # Base de datos (se crea automáticamente)
```

## Uso

### Modo simulador (pruebas)
```bash
python main.py --simulator
```

### Leer canal específico
```bash
python main.py --channel 1
python main.py -c 2
```

### Leer ambos canales
```bash
python main.py --all
```

### Modo continuo
```bash
python main.py --loop --interval 10
```

### Mostrar últimos registros
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

## Problemas Windows

Si hay error de conexión en Windows, instalar driver WinUSB:

1. Descargar [Zadig](https://zadig.akeo.ie/)
2. Conectar osciloscopio
3. En Zadig: seleccionar OWON → instalar WinUSB

## Ver También

```bash
# Ver registros
python main.py --recent 20

# Modo interactivo
python main.py --loop
```