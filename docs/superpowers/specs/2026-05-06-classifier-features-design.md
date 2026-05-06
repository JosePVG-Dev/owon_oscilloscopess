# Classifier: Feature-Based Wave Classification

## Problem

Template-matching via correlation (`_classify_by_template`) classifies all periodic
waves as SINUSOIDAL. The sine template acts as a universal matcher — the fundamental
frequency component of every periodic wave is a sine, so the sine correlation score
is always high (~0.85-0.95). The correct template only scores marginally higher and
often loses. Sawtooth is the exception because its asymmetry makes the sine score drop.

## Solution

Pre-filter wave types using time-domain features before falling back to template
matching. Decision tree in `classify()`:

```
noise check (autocorr < 0.15 or amplitude < 0.01) → RUIDO
  │
unique_ratio < 0.1  →  CUADRADA  (few unique values = flat with jumps)
  │
|positive_ratio - 0.5| > 0.3  →  SIERRA  (highly asymmetric = ramp + drop)
  │
template matching: SINUSOIDAL vs TRIANGULAR only
```

## Feature Definitions

| Feature | How it distinguishes |
|---------|---------------------|
| `unique_ratio` | Square waves have only 3 values (±amplitude, 0) = ~0.003 ratio. All others have many distinct values. |
| `positive_ratio` | Sawtooth ramps up for ~99% of cycle then drops in 1 sample → >0.9. Symmetric waves stay near 0.5. |
| Templates | With square and sawtooth resolved, templates only need to pick between SINE and TRIANGLE — much more reliable than 4-way competition. |

## Changes

**File: `classifier.py`**

1. In `classify()`, compute `unique_ratio` and `positive_ratio` from raw data (not from the extracted cycle, to avoid cycle-extraction edge cases).
2. Add decision tree before template matching.
3. Lower template noise threshold from 0.5 to 0.3 (templates are now only for 2 candidates).
4. `_classify_by_template()` remains unchanged, but templates dict may be filtered to only SINUSOIDAL and TRIANGULAR when called for that branch.

## What stays the same

- `analyze()` — unchanged
- `_estimate_frequency_fft()` — unchanged
- `_extract_one_cycle()` — unchanged
- `_classify_by_template()` — logic unchanged, just called with fewer candidates
- `WaveType`, `SeaType`, `WAVE_TO_SEA` — unchanged

## Risks

- Thresholds (`<0.1`, `>0.3`) are calibrated for the AWG/simulator synthesis at
  typical frequencies. Real oscilloscope data with noise might need tuning.
- Very high noise could randomize `unique_ratio`, but noise is already pre-filtered
  by the autocorrelation check.
