from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import secrets
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from entropy_canvas.generator import PRESETS, _build_password, _normalize_events, generate_secret

WIDTH = 1440
HEIGHT = 900
PRESET_NAME = "enterprise"
PRESET = PRESETS[PRESET_NAME]
OUTPUT_DIR = PROJECT_ROOT / "tests" / "artifacts"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass(slots=True)
class ModeResult:
    secret: str
    approx_bits: int


CHARSET = PRESET["charset"]
LENGTH = int(PRESET["length"])
MT_RNG = random.Random(7331)


def synthetic_events(points: int = 220) -> list[dict[str, int | str]]:
    events: list[dict[str, int | str]] = []
    center_x = WIDTH / 2
    center_y = HEIGHT / 2

    for i in range(points):
        angle = i * 0.19
        radius = 120 + (i * 2.35)

        x = center_x + math.cos(angle) * radius
        y = center_y + math.sin(angle * 1.27) * (radius * 0.62)

        x = max(0, min(WIDTH - 1, int(round(x))))
        y = max(0, min(HEIGHT - 1, int(round(y))))

        if i == 0:
            event_type = "down"
        elif i % 31 == 0:
            event_type = "click"
        elif i % 17 == 0:
            event_type = "wheel"
        elif i % 9 == 0:
            event_type = "drag"
        else:
            event_type = "move"

        dt = 24 + ((i * 37) % 180)
        pressure = 250 + ((i * 91) % 700)

        events.append(
            {
                "type": event_type,
                "x": x,
                "y": y,
                "dt": dt,
                "pressure": pressure,
            }
        )

    events.append(
        {
            "type": "up",
            "x": events[-1]["x"],
            "y": events[-1]["y"],
            "dt": 48,
            "pressure": 180,
        }
    )
    return events


BASE_EVENTS = synthetic_events()


def serialized_interaction_digest(events: list[dict[str, int | str]]) -> bytes:
    normalized = _normalize_events(events, WIDTH, HEIGHT)
    payload = json.dumps(normalized, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).digest()


def deterministic_bytes(label: str, length: int) -> bytes:
    material = bytearray()
    counter = 0
    while len(material) < length:
        material.extend(hashlib.sha256(f"{label}:{counter}".encode("utf-8")).digest())
        counter += 1
    return bytes(material[:length])


def derive_seed(ikm: bytes, *, salt: bytes, info: bytes) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=64,
        salt=salt,
        info=info,
    ).derive(ikm)


def build_from_seed(seed: bytes) -> ModeResult:
    secret, approx_bits = _build_password(seed, PRESET)
    return ModeResult(secret=secret, approx_bits=approx_bits)


def generate_mixed(events: list[dict[str, int | str]]) -> ModeResult:
    result = generate_secret(events=events, width=WIDTH, height=HEIGHT, preset_name=PRESET_NAME)
    return ModeResult(secret=result.secret, approx_bits=result.approx_bits)


def generate_mixed_deterministic(events: list[dict[str, int | str]], label: str) -> ModeResult:
    interaction_digest = serialized_interaction_digest(events)
    os_random = deterministic_bytes(f"mixed-os:{label}", 32)
    salt = deterministic_bytes(f"mixed-salt:{label}", 16)
    seed = derive_seed(
        interaction_digest + hashlib.sha256(b"").digest() + os_random,
        salt=salt,
        info=b"entropy-canvas:benchmark:mixed:enterprise",
    )
    return build_from_seed(seed)


def generate_secrets_only(_: list[dict[str, int | str]]) -> ModeResult:
    secret = "".join(secrets.choice(CHARSET) for _ in range(LENGTH))
    approx_bits = int(round(LENGTH * math.log2(len(CHARSET))))
    return ModeResult(secret=secret, approx_bits=approx_bits)


def generate_secrets_only_deterministic(_: list[dict[str, int | str]], label: str) -> ModeResult:
    os_random = deterministic_bytes(f"secrets-os:{label}", 32)
    salt = deterministic_bytes(f"secrets-salt:{label}", 16)
    seed = derive_seed(
        os_random,
        salt=salt,
        info=b"entropy-canvas:benchmark:secrets-only:enterprise",
    )
    return build_from_seed(seed)


def generate_interaction_only(events: list[dict[str, int | str]]) -> ModeResult:
    interaction_digest = serialized_interaction_digest(events)
    seed = derive_seed(
        interaction_digest + hashlib.sha256(b"").digest(),
        salt=b"\x00" * 16,
        info=b"entropy-canvas:benchmark:interaction-only:enterprise",
    )
    return build_from_seed(seed)


def generate_random_only(_: list[dict[str, int | str]]) -> ModeResult:
    secret = "".join(MT_RNG.choice(CHARSET) for _ in range(LENGTH))
    approx_bits = int(round(LENGTH * math.log2(len(CHARSET))))
    return ModeResult(secret=secret, approx_bits=approx_bits)


def generate_random_only_deterministic(_: list[dict[str, int | str]], label: str) -> ModeResult:
    seed_int = int.from_bytes(hashlib.sha256(f"random:{label}".encode("utf-8")).digest()[:8], "big")
    rng = random.Random(seed_int)
    secret = "".join(rng.choice(CHARSET) for _ in range(LENGTH))
    approx_bits = int(round(LENGTH * math.log2(len(CHARSET))))
    return ModeResult(secret=secret, approx_bits=approx_bits)


MODE_CONFIG = {
    "mixed": {
        "display": "Mixed",
        "runtime": generate_mixed,
        "deterministic": generate_mixed_deterministic,
        "cryptographic": "Yes",
        "uses_interaction": "Yes",
        "notes": "Current Entropy Canvas design (interaction + OS randomness)",
    },
    "secrets_only": {
        "display": "Secrets only",
        "runtime": generate_secrets_only,
        "deterministic": generate_secrets_only_deterministic,
        "cryptographic": "Yes",
        "uses_interaction": "No",
        "notes": "OS-backed randomness only",
    },
    "interaction_only": {
        "display": "Interaction only",
        "runtime": generate_interaction_only,
        "deterministic": lambda events, label: generate_interaction_only(events),
        "cryptographic": "No",
        "uses_interaction": "Yes",
        "notes": "No OS randomness; deterministic from interaction path",
    },
    "random_only": {
        "display": "Random only",
        "runtime": generate_random_only,
        "deterministic": generate_random_only_deterministic,
        "cryptographic": "No",
        "uses_interaction": "No",
        "notes": "Python random / Mersenne Twister",
    },
}


def hamming_ratio(a: str, b: str) -> float:
    max_len = max(len(a), len(b))
    if max_len == 0:
        return 0.0
    a = a.ljust(max_len, "\0")
    b = b.ljust(max_len, "\0")
    return sum(ch1 != ch2 for ch1, ch2 in zip(a, b)) / max_len


def jitter_events(base_events: list[dict[str, int | str]], sample_index: int) -> list[dict[str, int | str]]:
    rng = random.Random(1009 * (sample_index + 1))
    mutated: list[dict[str, int | str]] = []

    for idx, event in enumerate(base_events):
        item = dict(event)
        if item["type"] in {"move", "drag", "click", "down", "up", "wheel"}:
            x_jitter = rng.randint(-10, 10)
            y_jitter = rng.randint(-10, 10)
            dt_jitter = rng.randint(-30, 30)
            pressure_jitter = rng.randint(-60, 60)

            if idx % 7 == 0:
                x_jitter += rng.randint(-18, 18)
            if idx % 11 == 0:
                y_jitter += rng.randint(-18, 18)

            item["x"] = max(0, min(WIDTH - 1, int(item["x"]) + x_jitter))
            item["y"] = max(0, min(HEIGHT - 1, int(item["y"]) + y_jitter))
            item["dt"] = max(0, min(2000, int(item["dt"]) + dt_jitter))
            item["pressure"] = max(0, min(1024, int(item["pressure"]) + pressure_jitter))
        mutated.append(item)

    return mutated


def tiny_mutation(base_events: list[dict[str, int | str]], sample_index: int) -> list[dict[str, int | str]]:
    mutated = [dict(event) for event in base_events]
    target = 1 + (sample_index % (len(mutated) - 2))
    mutated[target]["x"] = max(0, min(WIDTH - 1, int(mutated[target]["x"]) + 1))
    mutated[target]["dt"] = max(0, min(2000, int(mutated[target]["dt"]) + 1))
    return mutated


def fixed_input_uniqueness(mode_key: str, samples: int) -> tuple[int, int]:
    generator = MODE_CONFIG[mode_key]["runtime"]
    outputs = [generator(BASE_EVENTS).secret for _ in range(samples)]
    unique = len(set(outputs))
    collisions = len(outputs) - unique
    return unique, collisions


def varied_input_with_fixed_randomness(mode_key: str, samples: int) -> int:
    generator = MODE_CONFIG[mode_key]["deterministic"]
    outputs = []

    for index in range(samples):
        events = jitter_events(BASE_EVENTS, index)
        if mode_key == "interaction_only":
            outputs.append(generator(events, "ignored").secret)
        else:
            outputs.append(generator(events, "stable-randomness").secret)

    return len(set(outputs))


def varied_input_uniqueness_runtime(mode_key: str, samples: int) -> tuple[int, int]:
    generator = MODE_CONFIG[mode_key]["runtime"]
    outputs = [generator(jitter_events(BASE_EVENTS, index)).secret for index in range(samples)]
    unique = len(set(outputs))
    collisions = len(outputs) - unique
    return unique, collisions


def avalanche_score(mode_key: str, samples: int) -> float:
    generator = MODE_CONFIG[mode_key]["deterministic"]

    if mode_key == "interaction_only":
        baseline = generator(BASE_EVENTS, "ignored").secret
    else:
        baseline = generator(BASE_EVENTS, "avalanche-baseline").secret

    ratios: list[float] = []

    for index in range(samples):
        mutated = tiny_mutation(BASE_EVENTS, index)
        if mode_key == "interaction_only":
            candidate = generator(mutated, "ignored").secret
        else:
            candidate = generator(mutated, "avalanche-baseline").secret
        ratios.append(hamming_ratio(baseline, candidate))

    return round((sum(ratios) / len(ratios)) * 100, 2)


def build_rows(samples: int, avalanche_samples: int) -> list[dict[str, str | int | float]]:
    rows: list[dict[str, str | int | float]] = []

    for mode_key, config in MODE_CONFIG.items():
        fixed_unique, fixed_collisions = fixed_input_uniqueness(mode_key, samples)
        varied_unique_runtime, varied_collisions_runtime = varied_input_uniqueness_runtime(mode_key, samples)
        input_contribution_unique = varied_input_with_fixed_randomness(mode_key, samples)
        avalanche_pct = avalanche_score(mode_key, avalanche_samples)
        approx_bits = int(round(LENGTH * math.log2(len(CHARSET))))

        rows.append(
            {
                "mode": config["display"],
                "samples": samples,
                "theoretical_bits": approx_bits,
                "fixed_input_unique_outputs": fixed_unique,
                "fixed_input_collisions": fixed_collisions,
                "varied_input_unique_outputs": varied_unique_runtime,
                "varied_input_collisions": varied_collisions_runtime,
                "input_contribution_unique_outputs": input_contribution_unique,
                "avalanche_percent": avalanche_pct,
                "cryptographic_rng": config["cryptographic"],
                "uses_interaction": config["uses_interaction"],
                "notes": config["notes"],
            }
        )

    return rows


def write_csv(rows: list[dict[str, str | int | float]], path: Path) -> None:
    fieldnames = [
        "mode",
        "samples",
        "theoretical_bits",
        "fixed_input_unique_outputs",
        "fixed_input_collisions",
        "varied_input_unique_outputs",
        "varied_input_collisions",
        "input_contribution_unique_outputs",
        "avalanche_percent",
        "cryptographic_rng",
        "uses_interaction",
        "notes",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def add_bar_labels(ax, values: list[float | int]) -> None:
    ymax = max(values) if values else 1
    pad = max(ymax * 0.015, 0.6)
    for index, value in enumerate(values):
        ax.text(index, value + pad, str(value), ha="center", va="bottom", fontsize=9)


def render_chart(rows: list[dict[str, str | int | float]], path: Path) -> None:
    labels = [str(row["mode"]) for row in rows]
    fixed_unique = [int(row["fixed_input_unique_outputs"]) for row in rows]
    input_contrib = [int(row["input_contribution_unique_outputs"]) for row in rows]
    avalanche = [float(row["avalanche_percent"]) for row in rows]

    figure, axes = plt.subplots(1, 3, figsize=(19, 6))

    axes[0].bar(labels, fixed_unique)
    axes[0].set_title("Identical input repeated")
    axes[0].set_ylabel("Unique outputs out of N")
    axes[0].tick_params(axis="x", rotation=18)
    add_bar_labels(axes[0], fixed_unique)

    axes[1].bar(labels, input_contrib)
    axes[1].set_title("Input contribution with fixed randomness")
    axes[1].set_ylabel("Unique outputs out of N")
    axes[1].tick_params(axis="x", rotation=18)
    add_bar_labels(axes[1], input_contrib)

    axes[2].bar(labels, avalanche)
    axes[2].set_title("Avalanche from tiny input change")
    axes[2].set_ylabel("Changed characters (%)")
    axes[2].tick_params(axis="x", rotation=18)
    add_bar_labels(axes[2], [round(v, 2) for v in avalanche])

    figure.suptitle("Entropy Canvas source benchmark", fontsize=16)
    figure.tight_layout()
    figure.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(figure)


def print_table(rows: list[dict[str, str | int | float]]) -> None:
    headers = [
        "mode",
        "fixed_input_unique_outputs",
        "input_contribution_unique_outputs",
        "avalanche_percent",
        "cryptographic_rng",
    ]

    widths = {
        header: max(len(header), max(len(str(row[header])) for row in rows))
        for header in headers
    }

    line = " | ".join(header.ljust(widths[header]) for header in headers)
    divider = "-+-".join("-" * widths[header] for header in headers)

    print(line)
    print(divider)
    for row in rows:
        print(" | ".join(str(row[header]).ljust(widths[header]) for header in headers))


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Entropy Canvas modes against each other.")
    parser.add_argument("--samples", type=int, default=1000, help="Number of samples per mode.")
    parser.add_argument("--avalanche-samples", type=int, default=256, help="Number of tiny mutations for avalanche testing.")
    args = parser.parse_args()

    rows = build_rows(samples=args.samples, avalanche_samples=args.avalanche_samples)

    csv_path = OUTPUT_DIR / "mode_benchmark.csv"
    png_path = OUTPUT_DIR / "mode_benchmark.png"

    write_csv(rows, csv_path)
    render_chart(rows, png_path)
    print_table(rows)
    print()
    print(f"CSV written to:   {csv_path}")
    print(f"Chart written to: {png_path}")


if __name__ == "__main__":
    main()