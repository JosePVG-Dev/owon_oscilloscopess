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

    def analyze(self, data: List[float]) -> dict:
        arr = np.array(data)
        
        amplitude = (np.max(arr) - np.min(arr)) / 2
        
        zero_crossings = np.sum(np.diff(np.sign(arr)) != 0)
        
        diffs = np.diff(arr)
        sign_changes = np.sum(np.diff(np.sign(diffs)) != 0)
        
        abs_diffs = np.abs(diffs)
        mean_diff = np.mean(abs_diffs)
        std_diff = np.std(abs_diffs)
        
        positive_diffs = np.sum(diffs > 0)
        negative_diffs = np.sum(diffs < 0)
        
        peak_positions = np.where((diffs[:-1] > 0) & (diffs[1:] < 0))[0]
        valley_positions = np.where((diffs[:-1] < 0) & (diffs[1:] > 0))[0]
        
        estimated_freq = zero_crossings * self.sample_rate / (2 * len(arr))
        estimated_period = 1 / estimated_freq if estimated_freq > 0 else 0
        
        return {
            "amplitude": amplitude,
            "zero_crossings": zero_crossings,
            "sign_changes": sign_changes,
            "mean_diff": mean_diff,
            "std_diff": std_diff,
            "positive_ratio": positive_diffs / len(diffs) if len(diffs) > 0 else 0,
            "negative_ratio": negative_diffs / len(diffs) if len(diffs) > 0 else 0,
            "peaks": len(peak_positions),
            "valleys": len(valley_positions),
            "estimated_freq": estimated_freq,
            "estimated_period": estimated_period,
        }

    def classify(self, data: List[float]) -> WaveType:
        if len(data) < 10:
            return WaveType.RUIDO
        
        analysis = self.analyze(data)
        
        std_ratio = analysis["std_diff"] / (analysis["mean_diff"] + 1e-10)
        
        positive_ratio = analysis["positive_ratio"]
        negative_ratio = analysis["negative_ratio"]
        
        amplitude_range = np.max(data) - np.min(data)
        normalized_std = analysis["std_diff"] / (amplitude_range + 1e-10)
        
        if normalized_std < 0.05:
            return WaveType.RUIDO
        
        if std_ratio < 0.15 and std_ratio > 0.02:
            return WaveType.SINUSOIDAL
        
        if std_ratio > 0.8 or (positive_ratio > 0.4 and positive_ratio < 0.6):
            if analysis["std_diff"] > 0.1:
                return WaveType.CUADRADA
        
        diffs = np.diff(np.array(data))
        edges = np.sum(np.abs(np.diff(diffs)) > 0.1)
        
        if edges > len(data) * 0.3:
            return WaveType.SIERRA
        
        if (positive_ratio > 0.45 and positive_ratio < 0.55) and \
           (negative_ratio > 0.45 and negative_ratio < 0.55):
            return WaveType.TRIANGULAR
        
        return WaveType.RUIDO

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