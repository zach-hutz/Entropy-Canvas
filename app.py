from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from entropy_canvas.generator import PRESETS, generate_secret

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / 'static'

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path='')


@app.get('/')
def index():
    return send_from_directory(STATIC_DIR, 'index.html')


@app.get('/api/health')
def health() -> tuple[dict[str, str], int]:
    return {'status': 'ok'}, 200


@app.get('/api/presets')
def presets() -> tuple[dict[str, list[dict[str, str]]], int]:
    payload = [
        {
            'id': preset_id,
            'label': preset['label'],
            'mode': preset['mode'],
        }
        for preset_id, preset in PRESETS.items()
    ]
    return {'presets': payload}, 200


@app.post('/api/generate')
def generate() -> tuple[dict[str, object], int]:
    body = request.get_json(silent=True) or {}
    events = body.get('events') or []
    width = int(body.get('width') or 1)
    height = int(body.get('height') or 1)
    preset = str(body.get('preset') or 'enterprise')
    site_label = str(body.get('siteLabel') or '')[:128]

    try:
        result = generate_secret(
            events=events,
            width=width,
            height=height,
            preset_name=preset,
            site_label=site_label,
        )
    except ValueError as exc:
        return {'error': str(exc)}, 400
    except Exception:
        return {'error': 'Unable to generate a secret from this session.'}, 500

    return (
        jsonify(
            {
                'secret': result.secret,
                'fingerprint': result.fingerprint,
                'interactionHashPreview': result.interaction_hash[:16],
                'approxBits': result.approx_bits,
                'strengthLabel': result.strength_label,
                'eventCount': result.event_count,
                'featureSummary': result.feature_summary,
                'presetLabel': result.preset_label,
            }
        ),
        200,
    )


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8000, debug=True)
