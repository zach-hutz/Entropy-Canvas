from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from entropy_canvas.generator import generate_secret


def build_events(count: int = 120):
    events = []
    x, y = 100, 80
    for index in range(count):
        x = (x + 17 + (index % 11)) % 900
        y = (y + 13 + (index % 7)) % 600
        events.append(
            {
                'type': 'move' if index % 9 else 'click',
                'x': x,
                'y': y,
                'dt': 16 + (index % 7) * 8,
                'pressure': 220 + (index % 5) * 20,
            }
        )
    return events


if __name__ == '__main__':
    result = generate_secret(
        events=build_events(),
        width=1280,
        height=720,
        preset_name='enterprise',
        site_label='linkedin-demo',
    )
    print(result.secret)
    print(result.approx_bits)
    print(result.fingerprint)
