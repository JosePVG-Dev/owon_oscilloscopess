from flask import Flask, render_template, jsonify, request
from database import Database

app = Flask(__name__)
db = Database()

WAVE_LABELS = {
    "senoidal": "Senoidal",
    "cuadrada": "Cuadrada",
    "triangular": "Triangular",
    "sierra": "Sierra",
    "ruido": "Ruido",
}

SEA_LABELS = {
    "ola suave": "Ola Suave",
    "ola rompiente": "Ola Rompiente",
    "ola de rebote": "Ola de Rebote",
    "ola de tormenta": "Ola de Tormenta",
    "mar agitado": "Mar Agitado",
}

WAVE_COLORS = {
    "senoidal": "#36a2eb",
    "cuadrada": "#ff6384",
    "triangular": "#ffce56",
    "sierra": "#4bc0c0",
    "ruido": "#9966ff",
}

SEA_COLORS = {
    "ola suave": "#36a2eb",
    "ola rompiente": "#ff6384",
    "ola de rebote": "#ffce56",
    "ola de tormenta": "#4bc0c0",
    "mar agitado": "#9966ff",
}


@app.route("/")
def index():
    records = db.get_recent(100)
    stats = _compute_stats(records)
    return render_template("index.html", stats=stats, records=records)


@app.route("/api/readings")
def api_readings():
    since_id = request.args.get("since_id", type=int)
    if since_id is not None:
        records = db.get_since_id(since_id)
    else:
        records = db.get_recent(500)
    data = []
    for r in records:
        data.append({
            "id": r["id"],
            "timestamp": r["timestamp"],
            "wave_type": r["wave_type"],
            "sea_type": r["sea_type"],
            "channel": r["channel"],
            "amplitude": r["amplitude"],
            "frequency": r["frequency"],
            "period": r["period"],
        })
    return jsonify(data)


@app.route("/api/latest")
def api_latest():
    records = db.get_recent(1)
    if not records:
        return jsonify(None)
    r = records[0]
    return jsonify({
        "id": r["id"],
        "timestamp": r["timestamp"],
        "wave_type": r["wave_type"],
        "sea_type": r["sea_type"],
        "channel": r["channel"],
        "amplitude": r["amplitude"],
        "frequency": r["frequency"],
        "period": r["period"],
    })


@app.route("/api/clear", methods=["POST"])
def api_clear():
    db.clear()
    return jsonify({"status": "ok"})


@app.route("/api/stats")
def api_stats():
    records = db.get_recent(500)
    return jsonify(_compute_stats(records))


def _compute_stats(records):
    total = len(records)
    if total == 0:
        return {
            "total": 0,
            "last_reading": None,
            "most_common_wave": None,
            "most_common_sea": None,
            "wave_distribution": {},
            "sea_distribution": {},
            "avg_frequency": 0,
            "avg_amplitude": 0,
            "channel_counts": {},
        }

    wave_counts = {}
    sea_counts = {}
    channel_counts = {}
    freqs = []
    amps = []

    for r in records:
        wt = r["wave_type"]
        st = r["sea_type"]
        ch = r["channel"]
        wave_counts[wt] = wave_counts.get(wt, 0) + 1
        sea_counts[st] = sea_counts.get(st, 0) + 1
        channel_counts[ch] = channel_counts.get(ch, 0) + 1
        if r["frequency"]:
            freqs.append(r["frequency"])
        if r["amplitude"]:
            amps.append(r["amplitude"])

    most_common_wave = max(wave_counts, key=wave_counts.get) if wave_counts else None
    most_common_sea = max(sea_counts, key=sea_counts.get) if sea_counts else None

    return {
        "total": total,
        "last_reading": records[0]["timestamp"] if records else None,
        "most_common_wave": WAVE_LABELS.get(most_common_wave, most_common_wave),
        "most_common_sea": SEA_LABELS.get(most_common_sea, most_common_sea),
        "wave_distribution": wave_counts,
        "sea_distribution": sea_counts,
        "avg_frequency": sum(freqs) / len(freqs) if freqs else 0,
        "avg_amplitude": sum(amps) / len(amps) if amps else 0,
        "channel_counts": channel_counts,
    }


if __name__ == "__main__":
    app.run(debug=True, port=5000)