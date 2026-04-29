import numpy as np
from classifier import Classifier, WaveType

c = Classifier()
all_ok = True

for sample_rate in [1000]:
    for freq in [10, 25, 50, 75, 100, 200]:
        duration = 5.0 / freq
        n_samples = int(duration * sample_rate)
        if n_samples < 50:
            continue
        t = np.linspace(0, duration, n_samples, endpoint=False)

        waves = {
            "senoidal": list(np.sin(2 * np.pi * freq * t) * 0.5),
            "cuadrada": list(np.sign(np.sin(2 * np.pi * freq * t)) * 0.5),
            "triangular": list((2 * np.abs(2 * (freq * t - np.floor(freq * t + 0.5))) - 1) * 0.5),
            "sierra": list((2 * (freq * t - np.floor(freq * t)) - 1) * 0.5),
            "ruido": list(np.random.normal(0, 0.15, n_samples)),
        }

        for name, wave in waves.items():
            result = c.classify(wave).value
            ok = result == name
            if not ok:
                all_ok = False
            status = "OK" if ok else "FAIL"
            print(f"  {name:12s} @ {freq:3d}Hz ({n_samples:4d} samples) -> {result:12s} {status}")

print(f"\n{'ALL CORRECT' if all_ok else 'SOME FAILURES'}")