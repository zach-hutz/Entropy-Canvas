# Entropy Canvas

Entropy Canvas is a local-first visual password forge built with Python and a canvas-based frontend. It uses user interaction as one input, combines that with cryptographic OS randomness, and derives a strong password or passphrase without persisting raw interaction data beyond the active session.

## Features

- Local-first password and passphrase generation
- Interactive animated canvas with multiple visual themes:
  - Default (Nebula)
  - Forest Roots
  - Prism Bloom
  - Volcanic Ember
- Interaction-driven entropy meter and session telemetry
- Password presets for:
  - Website
  - Enterprise
  - Developer
  - Passphrase
- HKDF-based derivation pipeline
- Clipboard copy and clear actions
- Session fingerprint and interaction summary for demo/reporting
- Benchmark scripts for comparing generation modes and output behavior

## How It Works

Entropy Canvas does **not** treat the visual pattern as the password itself.

Instead, it:

1. Captures local interaction data from the canvas
2. Normalizes the interaction stream
3. Mixes the interaction-derived material with cryptographic OS randomness
4. Derives a final seed through HKDF
5. Produces a password or passphrase based on the selected preset

This keeps the visual interaction meaningful without relying on it as the sole source of unpredictability.

## Project Structure

```text
entropy-canvas/
├── app.py
├── entropy_canvas/
│   ├── generator.py
│   └── word_material.py
├── static/
│   ├── app.js
│   ├── index.html
│   └── styles.css
├── tests/
│   ├── mode_benchmark.py
│   ├── randomness_benchmark.py
│   └── artifacts/
└── requirements.txt
```

## Run Locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open:

```text
http://127.0.0.1:8000
```

## Benchmarks

The included benchmark scripts compare:

- mixed mode (interaction + OS randomness)
- secrets-only mode
- interaction-only mode
- random-only mode

In testing, the mixed mode showed:

- fresh outputs across repeated runs
- meaningful contribution from user interaction
- strong sensitivity to small input changes

These benchmarks are intended to evaluate output behavior and design properties. They are **not** a formal proof of cryptographic security.

## Security Notes

- The visual interaction is **not** the password.
- Interaction data is only one input into generation.
- Final secrets are derived from normalized interaction data plus cryptographic OS randomness.
- The mixed design is intended to preserve strong unpredictability while allowing the visual interaction to meaningfully influence the result.
- This project is a portfolio/demo build and should be reviewed, tested, and hardened further before any production use.

## Why I Built It

Most security projects are technically useful but visually forgettable. Entropy Canvas was built to explore whether password generation could be both security-focused and visually distinctive, while still using a defensible local generation model.
