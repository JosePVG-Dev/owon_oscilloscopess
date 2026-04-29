import numpy as np
from enum import Enum
from typing import List, Tuple, Optional


class WaveType(Enum):
    SINUSOIDAL = "senoidal"
    CUADRADA = "cuadrada"
    TRIANGULAR = "triangular"
    SIERRA = "sierra"
    RUIDO = "ruido"


class SeaType(Enum):
    SUAVE = "ola suave"
    ROMPIENTE = "ola rompiente"
    REBOTE = "ola de rebote"
    TORMENTA = "ola de tormenta"
    AGITADO = "mar agitado"


WAVE_TO_SEA = {
    WaveType.SINUSOIDAL: SeaType.SUAVE,
    WaveType.CUADRADA: SeaType.ROMPIENTE,
    WaveType.TRIANGULAR: SeaType.REBOTE,
    WaveType.SIERRA: SeaType.TORMENTA,
    WaveType.RUIDO: SeaType.AGITADO,
}


class Classifier:
    def __init__(self, sample_rate: int = 1000):
        self.sample_rate = sample_rate

    def _estimate_frequency_fft(self, arr: np.ndarray) -> float:
        centered = arr - np.mean(arr)
        if np.std(centered) < 1e-10:
            return 0.0
        fft_vals = np.fft.rfft(centered)
        freqs = np.fft.rfftfreq(len(centered), d=1.0 / self.sample_rate)
        magnitude = np.abs(fft_vals)
        if len(magnitude) < 2:
            return 0.0
        peak_idx = np.argmax(magnitude[1:]) + 1
        return float(freqs[peak_idx])

    def _extract_one_cycle(self, arr: np.ndarray, freq: float) -> Optional[np.ndarray]:
        period_samples = int(round(self.sample_rate / freq))
        if period_samples < 10 or period_samples > len(arr):
            return None
        centered = arr - np.mean(arr)
        peak_idx = int(np.argmax(centered))
        start = peak_idx
        end = start + period_samples
        if end > len(arr):
            start = len(arr) - period_samples
            end = len(arr)
        return arr[start:end]

    def _normalize_cycle(self, cycle: np.ndarray) -> np.ndarray:
        centered = cycle - np.mean(cycle)
        max_abs = np.max(np.abs(centered))
        if max_abs < 1e-10:
            return centered
        return centered / max_abs

    @staticmethod
    def _max_correlation(signal: np.ndarray, template: np.ndarray) -> float:
        s = signal - np.mean(signal)
        t = template - np.mean(template)
        s_norm = np.sqrt(np.sum(s ** 2))
        t_norm = np.sqrt(np.sum(t ** 2))
        if s_norm < 1e-10 or t_norm < 1e-10:
            return 0.0
        fft_s = np.fft.fft(s)
        fft_t = np.fft.fft(t)
        corr = np.fft.ifft(fft_s * np.conj(fft_t)).real
        return float(np.max(np.abs(corr)) / (s_norm * t_norm))

    def _classify_by_template(self, cycle: np.ndarray) -> WaveType:
        normalized = self._normalize_cycle(cycle)
        n = len(normalized)
        t = np.linspace(0, 1, n, endpoint=False)

        templates = {
            WaveType.SINUSOIDAL: np.sin(2 * np.pi * t),
            WaveType.CUADRADA: np.where(t < 0.5, 1.0, -1.0),
            WaveType.TRIANGULAR: 1.0 - 4.0 * np.abs(t - 0.5),
            WaveType.SIERRA: 2.0 * t - 1.0,
        }

        best_type = WaveType.RUIDO
        best_score = 0.0

        for wave_type, template in templates.items():
            score = self._max_correlation(normalized, template)
            if score > best_score:
                best_score = score
                best_type = wave_type

        if best_score < 0.5:
            return WaveType.RUIDO

        return best_type

    def analyze(self, data: List[float]) -> dict:
        arr = np.array(data)

        amplitude = (np.max(arr) - np.min(arr)) / 2

        centered = arr - np.mean(arr)
        zero_crossings = np.sum(np.diff(np.sign(centered)) != 0)

        diffs = np.diff(arr)

        abs_diffs = np.abs(diffs)
        mean_diff = np.mean(abs_diffs) if len(abs_diffs) > 0 else 0
        std_diff = np.std(abs_diffs) if len(abs_diffs) > 0 else 0

        positive_ratio = np.sum(diffs > 0) / len(diffs) if len(diffs) > 0 else 0
        negative_ratio = np.sum(diffs < 0) / len(diffs) if len(diffs) > 0 else 0

        peak_positions = np.where((diffs[:-1] > 0) & (diffs[1:] < 0))[0]
        valley_positions = np.where((diffs[:-1] < 0) & (diffs[1:] > 0))[0]

        estimated_freq = self._estimate_frequency_fft(arr)
        estimated_period = 1 / estimated_freq if estimated_freq > 0 else 0

        amplitude_range = np.max(arr) - np.min(arr)

        autocorr = 0.0
        if np.std(centered) > 1e-10:
            autocorr = float(np.corrcoef(centered[:-1], centered[1:])[0, 1])

        unique_values = len(np.unique(np.round(arr, 3)))
        unique_ratio = unique_values / len(arr) if len(arr) > 0 else 1.0

        std_ratio = std_diff / (mean_diff + 1e-10)

        return {
            "amplitude": amplitude,
            "amplitude_range": amplitude_range,
            "zero_crossings": zero_crossings,
            "mean_diff": mean_diff,
            "std_diff": std_diff,
            "std_ratio": std_ratio,
            "positive_ratio": positive_ratio,
            "negative_ratio": negative_ratio,
            "peaks": len(peak_positions),
            "valleys": len(valley_positions),
            "estimated_freq": estimated_freq,
            "estimated_period": estimated_period,
            "autocorr": autocorr,
            "unique_ratio": unique_ratio,
            "unique_values": unique_values,
        }

    def classify(self, data: List[float]) -> WaveType:
        if len(data) < 10:
            return WaveType.RUIDO

        arr = np.array(data)
        amplitude_range = np.max(arr) - np.min(arr)

        if amplitude_range < 0.01:
            return WaveType.RUIDO

        centered = arr - np.mean(arr)
        if np.std(centered) > 1e-10:
            autocorr = float(np.corrcoef(centered[:-1], centered[1:])[0, 1])
            if autocorr < 0.15:
                return WaveType.RUIDO

        freq = self._estimate_frequency_fft(arr)
        if freq < 1e-6:
            return WaveType.RUIDO

        cycle = self._extract_one_cycle(arr, freq)
        if cycle is not None and len(cycle) >= 10:
            return self._classify_by_template(cycle)

        return self._classify_by_template(arr)

    def map_to_sea(self, wave_type: WaveType) -> SeaType:
        return WAVE_TO_SEA.get(wave_type, SeaType.AGITADO)

    def classify_and_map(self, data: List[float]) -> Tuple[WaveType, SeaType]:
        wave_type = self.classify(data)
        sea_type = self.map_to_sea(wave_type)
        return wave_type, sea_type

    def get_parameters(self, data: List[float]) -> Optional[dict]:
        if len(data) < 10:
            return None

        analysis = self.analyze(data)
        amplitude_range = np.max(data) - np.min(data)

        return {
            "amplitude": amplitude_range / 2,
            "frequency": analysis["estimated_freq"],
            "period": analysis["estimated_period"]
        }