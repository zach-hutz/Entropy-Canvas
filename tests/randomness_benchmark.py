from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import argparse
import csv
import math
import random
import secrets
from collections import Counter

import matplotlib.pyplot as plt

from entropy_canvas.generator import PRESETS, generate_secret


WIDTH = 1440
HEIGHT = 900

OUTPUT_DIR = Path("tests/artifacts")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ENTERPRISE_PRESET = PRESETS["enterprise"]
ENTERPRISE_CHARSET = ENTERPRISE_PRESET["charset"]
ENTERPRISE_LENGTH = int(ENTERPRISE_PRESET["length"])

HUMAN_ADJECTIVES = [
    "silent", "shadow", "rapid", "dark", "silver", "red", "blue", "gold",
    "winter", "summer", "iron", "storm", "pixel", "neon", "urban", "lunar",
    "solar", "frozen", "wild", "crimson", "icy", "dusty", "bright", "midnight",
]

HUMAN_NOUNS = [
    "fox", "wolf", "hawk", "tiger", "river", "stone", "ember", "falcon",
    "comet", "matrix", "cipher", "signal", "hunter", "dragon", "raven", "vault",
    "orbit", "phoenix", "blade", "forge", "ghost", "vertex", "echo", "crown",
]

HUMAN_SYMBOLS = list("!@#$")
HUMAN_RNG = random.Random(1337)
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


FIXED_EVENTS = synthetic_events()


def shannon_entropy_from_counts(counts: Counter[str]) -> float:
    total = sum(counts.values())
    if total == 0:
        return 0.0

    entropy = 0.0
    for count in counts.values():
        p = count / total
        entropy -= p * math.log2(p)
    return entropy


def average_position_entropy(samples: list[str]) -> float:
    if not samples:
        return 0.0

    max_len = max(len(sample) for sample in samples)
    entropies: list[float] = []

    for index in range(max_len):
        counts: Counter[str] = Counter()
        for sample in samples:
            if index < len(sample):
                counts[sample[index]] += 1
        entropies.append(shannon_entropy_from_counts(counts))

    return sum(entropies) / len(entropies)


def collision_count(samples: list[str]) -> int:
    return len(samples) - len(set(samples))


def observed_alphabet_size(samples: list[str]) -> int:
    alphabet = {ch for sample in samples for ch in sample}
    return len(alphabet)


def theoretical_bits(charset_size: int, length: int) -> float:
    return length * math.log2(charset_size)


def entropy_canvas_enterprise() -> tuple[str, float]:
    result = generate_secret(
        events=FIXED_EVENTS,
        width=WIDTH,
        height=HEIGHT,
        preset_name="enterprise",
    )
    return result.secret, float(result.approx_bits)


def python_secrets_enterprise() -> tuple[str, float]:
    secret_value = "".join(secrets.choice(ENTERPRISE_CHARSET) for _ in range(ENTERPRISE_LENGTH))
    return secret_value, theoretical_bits(len(ENTERPRISE_CHARSET), ENTERPRISE_LENGTH)


def python_random_enterprise() -> tuple[str, float]:
    secret_value = "".join(MT_RNG.choice(ENTERPRISE_CHARSET) for _ in range(ENTERPRISE_LENGTH))
    return secret_value, theoretical_bits(len(ENTERPRISE_CHARSET), ENTERPRISE_LENGTH)


def simulated_human_style() -> tuple[str, float]:
    adjective = HUMAN_RNG.choice(HUMAN_ADJECTIVES)
    noun = HUMAN_RNG.choice(HUMAN_NOUNS)
    number = f"{HUMAN_RNG.randrange(0, 100):02d}"
    symbol = HUMAN_RNG.choice(HUMAN_SYMBOLS)

    secret_value = f"{adjective}{noun}{number}{symbol}"
    approx = math.log2(len(HUMAN_ADJECTIVES) * len(HUMAN_NOUNS) * 100 * len(HUMAN_SYMBOLS))
    return secret_value, approx


METHODS = {
    "Entropy Canvas": {
        "generator": entropy_canvas_enterprise,
        "cryptographic_rng": "Yes",
        "notes": "Entropy Canvas enterprise preset",
    },
    "Python secrets": {
        "generator": python_secrets_enterprise,
        "cryptographic_rng": "Yes",
        "notes": "OS-backed CSPRNG baseline",
    },
    "Python random": {
        "generator": python_random_enterprise,
        "cryptographic_rng": "No",
        "notes": "Mersenne Twister baseline",
    },
    "Human-style pattern": {
        "generator": simulated_human_style,
        "cryptographic_rng": "No",
        "notes": "Simulated adjective+noun+2 digits+symbol",
    },
}


def benchmark(samples_per_method: int) -> list[dict[str, str | int | float]]:
    rows: list[dict[str, str | int | float]] = []

    for method_name, config in METHODS.items():
        samples: list[str] = []
        approx_bits_values: list[float] = []

        for _ in range(samples_per_method):
            secret_value, approx_bits_value = config["generator"]()
            samples.append(secret_value)
            approx_bits_values.append(approx_bits_value)

        avg_len = sum(len(sample) for sample in samples) / len(samples)
        avg_pos_entropy = average_position_entropy(samples)
        empirical_total_entropy = avg_pos_entropy * avg_len
        collisions = collision_count(samples)

        rows.append(
            {
                "method": method_name,
                "samples": samples_per_method,
                "avg_length": round(avg_len, 2),
                "theoretical_bits": round(sum(approx_bits_values) / len(approx_bits_values), 2),
                "avg_position_entropy_bits": round(avg_pos_entropy, 4),
                "empirical_total_entropy_bits": round(empirical_total_entropy, 2),
                "collisions": collisions,
                "unique_outputs": len(set(samples)),
                "observed_alphabet_size": observed_alphabet_size(samples),
                "cryptographic_rng": config["cryptographic_rng"],
                "notes": config["notes"],
            }
        )

    return rows


def write_csv(rows: list[dict[str, str | int | float]], path: Path) -> None:
    fieldnames = [
        "method",
        "samples",
        "avg_length",
        "theoretical_bits",
        "avg_position_entropy_bits",
        "empirical_total_entropy_bits",
        "collisions",
        "unique_outputs",
        "observed_alphabet_size",
        "cryptographic_rng",
        "notes",
    ]

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def add_bar_labels(ax, values: list[float | int]) -> None:
    ymax = max(values) if values else 1
    for index, value in enumerate(values):
        ax.text(index, value + (ymax * 0.02), f"{value}", ha="center", va="bottom", fontsize=9)


def render_chart(rows: list[dict[str, str | int | float]], path: Path) -> None:
    methods = [str(row["method"]) for row in rows]
    theoretical = [float(row["theoretical_bits"]) for row in rows]
    empirical = [float(row["empirical_total_entropy_bits"]) for row in rows]
    collisions = [int(row["collisions"]) for row in rows]

    figure, axes = plt.subplots(1, 3, figsize=(18, 6))

    axes[0].bar(methods, theoretical)
    axes[0].set_title("Theoretical search-space bits")
    axes[0].set_ylabel("Bits")
    axes[0].tick_params(axis="x", rotation=18)
    add_bar_labels(axes[0], [round(v, 2) for v in theoretical])

    axes[1].bar(methods, empirical)
    axes[1].set_title("Empirical position-entropy estimate")
    axes[1].set_ylabel("Estimated bits")
    axes[1].tick_params(axis="x", rotation=18)
    add_bar_labels(axes[1], [round(v, 2) for v in empirical])

    axes[2].bar(methods, collisions)
    axes[2].set_title("Exact collisions in sample batch")
    axes[2].set_ylabel("Count")
    axes[2].tick_params(axis="x", rotation=18)
    add_bar_labels(axes[2], collisions)

    figure.suptitle("Entropy Canvas randomness benchmark", fontsize=16)
    figure.tight_layout()
    figure.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(figure)


def print_table(rows: list[dict[str, str | int | float]]) -> None:
    headers = [
        "method",
        "theoretical_bits",
        "empirical_total_entropy_bits",
        "collisions",
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
    parser = argparse.ArgumentParser(description="Benchmark Entropy Canvas against other password-generation methods.")
    parser.add_argument("--samples", type=int, default=3000, help="Number of secrets to generate per method.")
    args = parser.parse_args()

    rows = benchmark(samples_per_method=args.samples)

    csv_path = OUTPUT_DIR / "randomness_benchmark.csv"
    png_path = OUTPUT_DIR / "randomness_benchmark.png"

    write_csv(rows, csv_path)
    render_chart(rows, png_path)
    print_table(rows)

    print()
    print(f"CSV written to:   {csv_path}")
    print(f"Chart written to: {png_path}")


if __name__ == "__main__":
    main()