from __future__ import annotations

import hashlib
import json
import math
import secrets
from dataclasses import dataclass
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .word_material import PASSPHRASE_WORDS, SEPARATORS, SYMBOLS

UPPER = 'ABCDEFGHJKLMNPQRSTUVWXYZ'
LOWER = 'abcdefghijkmnopqrstuvwxyz'
DIGITS = '23456789'
SYMBOL_SET = '!@#$%^&*+=?'

PRESETS: dict[str, dict[str, Any]] = {
    'website': {
        'mode': 'password',
        'length': 20,
        'groups': [UPPER, LOWER, DIGITS],
        'charset': UPPER + LOWER + DIGITS,
        'label': 'Website',
    },
    'enterprise': {
        'mode': 'password',
        'length': 24,
        'groups': [UPPER, LOWER, DIGITS, SYMBOL_SET],
        'charset': UPPER + LOWER + DIGITS + SYMBOL_SET,
        'label': 'Enterprise',
    },
    'developer': {
        'mode': 'password',
        'length': 28,
        'groups': [UPPER, LOWER, DIGITS, SYMBOL_SET],
        'charset': UPPER + LOWER + DIGITS + SYMBOL_SET,
        'label': 'Developer',
    },
    'passphrase': {
        'mode': 'passphrase',
        'word_count': 7,
        'label': 'Passphrase',
    },
}


@dataclass(slots=True)
class GenerationResult:
    secret: str
    fingerprint: str
    interaction_hash: str
    approx_bits: int
    strength_label: str
    event_count: int
    feature_summary: dict[str, int]
    preset_label: str


def _byte_stream(seed: bytes, blocks: int = 8) -> bytes:
    material = bytearray()
    counter = 0
    while len(material) < blocks * 32:
        counter_bytes = counter.to_bytes(4, 'big')
        material.extend(hashlib.sha256(seed + counter_bytes).digest())
        counter += 1
    return bytes(material)


def _take(stream: bytes, cursor: int, modulo: int) -> tuple[int, int]:
    chunk = stream[cursor:cursor + 4]
    if len(chunk) < 4:
        stream += hashlib.sha256(stream).digest()
        chunk = stream[cursor:cursor + 4]
    value = int.from_bytes(chunk, 'big')
    return value % modulo, cursor + 4


def _normalize_events(events: list[dict[str, Any]], width: int, height: int) -> list[dict[str, int | str]]:
    normalized: list[dict[str, int | str]] = []
    max_x = max(width, 1)
    max_y = max(height, 1)

    for raw in events[:4096]:
        event_type = str(raw.get('type', 'move'))
        x = float(raw.get('x', 0))
        y = float(raw.get('y', 0))
        dt = int(max(0, min(int(raw.get('dt', 0)), 2_000)))
        pressure = int(max(0, min(int(raw.get('pressure', 0)), 1024)))

        normalized.append(
            {
                't': event_type[:8],
                'x': int(round((max(0.0, min(x, max_x)) / max_x) * 4095)),
                'y': int(round((max(0.0, min(y, max_y)) / max_y) * 4095)),
                'dt': dt,
                'p': pressure,
            }
        )
    return normalized


def _feature_summary(normalized_events: list[dict[str, Any]]) -> dict[str, int]:
    unique_cells: set[tuple[int, int]] = set()
    direction_changes = 0
    click_count = 0
    pauses = 0
    last_dx = 0
    last_dy = 0

    for index, event in enumerate(normalized_events):
        unique_cells.add((event['x'] // 96, event['y'] // 96))
        if event['t'] in {'down', 'click'}:
            click_count += 1
        if event['dt'] > 120:
            pauses += 1
        if index == 0:
            continue
        prev = normalized_events[index - 1]
        dx = event['x'] - prev['x']
        dy = event['y'] - prev['y']
        if (dx == 0 and dy == 0) or (last_dx == 0 and last_dy == 0):
            last_dx, last_dy = dx, dy
            continue
        dot = (dx * last_dx) + (dy * last_dy)
        if dot < 0:
            direction_changes += 1
        last_dx, last_dy = dx, dy

    return {
        'unique_cells': len(unique_cells),
        'direction_changes': direction_changes,
        'clicks': click_count,
        'pauses': pauses,
    }


def _strength_label(bits: int) -> str:
    if bits >= 120:
        return 'Extremely strong'
    if bits >= 90:
        return 'Very strong'
    if bits >= 72:
        return 'Strong'
    if bits >= 56:
        return 'Solid'
    return 'Moderate'


def _build_password(seed: bytes, preset: dict[str, Any]) -> tuple[str, int]:
    charset = preset['charset']
    groups = preset['groups']
    length = int(preset['length'])
    stream = _byte_stream(seed, blocks=16)
    cursor = 0

    chars: list[str] = []
    for group in groups:
        index, cursor = _take(stream, cursor, len(group))
        chars.append(group[index])

    while len(chars) < length:
        index, cursor = _take(stream, cursor, len(charset))
        chars.append(charset[index])

    for swap_index in range(len(chars) - 1, 0, -1):
        pick, cursor = _take(stream, cursor, swap_index + 1)
        chars[swap_index], chars[pick] = chars[pick], chars[swap_index]

    approx_bits = int(round(length * math.log2(len(charset))))
    return ''.join(chars), approx_bits


def _build_passphrase(seed: bytes, preset: dict[str, Any]) -> tuple[str, int]:
    word_count = int(preset['word_count'])
    stream = _byte_stream(seed, blocks=16)
    cursor = 0
    words: list[str] = []

    for _ in range(word_count):
        word_idx, cursor = _take(stream, cursor, len(PASSPHRASE_WORDS))
        words.append(PASSPHRASE_WORDS[word_idx])

    separator_idx, cursor = _take(stream, cursor, len(SEPARATORS))
    digit_a, cursor = _take(stream, cursor, len(DIGITS))
    digit_b, cursor = _take(stream, cursor, len(DIGITS))
    symbol_idx, cursor = _take(stream, cursor, len(SYMBOLS))

    separator = SEPARATORS[separator_idx]
    suffix = f"{DIGITS[digit_a]}{DIGITS[digit_b]}{SYMBOLS[symbol_idx]}"
    secret = separator.join(words) + separator + suffix

    approx_bits = int(round(word_count * math.log2(len(PASSPHRASE_WORDS)) + math.log2(len(SEPARATORS) * len(DIGITS) * len(DIGITS) * len(SYMBOLS))))
    return secret, approx_bits


def generate_secret(
    *,
    events: list[dict[str, Any]],
    width: int,
    height: int,
    preset_name: str,
    site_label: str = '',
) -> GenerationResult:
    if preset_name not in PRESETS:
        raise ValueError('Unsupported preset.')
    if len(events) < 40:
        raise ValueError('Not enough interaction data collected yet.')

    normalized_events = _normalize_events(events, width, height)
    serialized = json.dumps(normalized_events, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    interaction_digest = hashlib.sha256(serialized).digest()
    metadata_digest = hashlib.sha256(site_label.strip().lower().encode('utf-8')).digest()
    os_random = secrets.token_bytes(32)
    hkdf_salt = secrets.token_bytes(16)

    seed = HKDF(
        algorithm=hashes.SHA256(),
        length=64,
        salt=hkdf_salt,
        info=b'entropy-canvas:v1:' + preset_name.encode('utf-8'),
    ).derive(interaction_digest + metadata_digest + os_random)

    preset = PRESETS[preset_name]
    if preset['mode'] == 'password':
        secret, approx_bits = _build_password(seed, preset)
    else:
        secret, approx_bits = _build_passphrase(seed, preset)

    feature_summary = _feature_summary(normalized_events)
    fingerprint = hashlib.sha256(interaction_digest + metadata_digest).hexdigest()[:16].upper()

    return GenerationResult(
        secret=secret,
        fingerprint=fingerprint,
        interaction_hash=interaction_digest.hex(),
        approx_bits=approx_bits,
        strength_label=_strength_label(approx_bits),
        event_count=len(normalized_events),
        feature_summary=feature_summary,
        preset_label=preset['label'],
    )
