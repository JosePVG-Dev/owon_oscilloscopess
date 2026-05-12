# Excel Export — Design Spec

## Summary

Add "Exportar a Excel" button to dashboard that downloads all DB records as `.xlsx`
with two sheets: "Resumen" (summary per capture) and "Muestras" (raw waveform
samples).

## Architecture

```
dashboard.html button → GET /api/export → Database.get_all() → openpyxl
  → .xlsx in memory → Flask send_file (attachment download)
```

## Changes

| File | Change |
|------|--------|
| `requirements.txt` | Add `openpyxl` |
| `dashboard.py` | New endpoint `GET /api/export` |
| `templates/index.html` | New button "Exportar a Excel" |

## Sheet 1: "Resumen"

Columns: `ID | Fecha/Hora | Canal | Onda | Mar | Amplitud (V) | Frecuencia (Hz) | Periodo (s)`

- Bold headers, light blue background
- Wave/sea names in Spanish title case (Senoidal, Ola Suave)
- Numeric columns with 4 decimal places
- Auto-adjusted column widths

## Sheet 2: "Muestras"

- Row 1 headers: `ID | t_0 (s) | t_1 (s) | t_2 (s) | ...`
- Time step = period / (len(data) - 1), derived from stored period
- Each row: waveform ID + voltaje values
- Skip rows with null data
- Same header style as Sheet 1

## Error Handling

- Empty DB → file with headers only
- Corrupt JSON in `data` column → skip row in Sheet 2, log warning

## Testing

```bash
python main.py --simulator --loop --interval 2  # wait ~30s for ~15 records
# Open dashboard, click "Exportar a Excel", verify both sheets
```
