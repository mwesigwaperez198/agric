"""Biosensor mock data generator (Phase 1).

Produces realistic multi-threat payloads for mycotoxins, pesticide residues and
moisture so the threat-evaluation pipeline can be tested without hardware.
"""

import json
import random
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

CROPS = ("coffee", "maize", "vanilla", "cocoa")

THRESHOLDS = {
    "coffee": {"ochratoxin_a_ppb": 2.0, "moisture_pct": 12.5},
    "maize": {"aflatoxin_b1_ppb": 10.0, "moisture_pct": 13.5},
    "vanilla": {"moisture_pct": 25.0},
    "cocoa": {"ochratoxin_a_ppb": 2.0, "moisture_pct": 7.5},
}


@dataclass
class MockReading:
    device_id: str
    crop_name: str
    batch_id: str
    farm_id: int | None
    payload: dict
    read_at: str


def _noise(base: float, spread: float) -> float:
    return round(random.uniform(base - spread, base + spread), 2)


def generate_payload(crop: str = "coffee", contamination: str = "low") -> dict:
    """contamination: low | moderate | severe — shifts values above thresholds."""
    t = THRESHOLDS.get(crop, THRESHOLDS["coffee"])
    factor = {"low": 0.6, "moderate": 1.3, "severe": 2.4}[contamination]

    payload: dict = {
        "temperature_c": _noise(22, 4),
        "humidity_pct": _noise(60, 15),
        "moisture_pct": _noise(t["moisture_pct"] * factor, t["moisture_pct"] * 0.15),
    }
    if "ochratoxin_a_ppb" in t:
        payload["ochratoxin_A_ppb"] = round(t["ochratoxin_a_ppb"] * factor * random.uniform(0.8, 1.2), 2)
    if "aflatoxin_b1_ppb" in t:
        payload["aflatoxin_B1_ppb"] = round(t["aflatoxin_b1_ppb"] * factor * random.uniform(0.8, 1.2), 2)
    payload["pesticide_residues_ppb"] = round(random.uniform(5, 40) * factor, 2)
    payload["pesticide_residues_ok"] = payload["pesticide_residues_ppb"] <= 30
    return payload


def generate_reading(
    device_id: str | None = None,
    crop: str = "coffee",
    contamination: str = "low",
    farm_id: int | None = 1,
) -> MockReading:
    return MockReading(
        device_id=device_id or f"sensor-{uuid.uuid4().hex[:8]}",
        crop_name=crop,
        batch_id=f"batch-{datetime.now(UTC):%Y%m%d}-{uuid.uuid4().hex[:6]}",
        farm_id=farm_id,
        payload=generate_payload(crop, contamination),
        read_at=datetime.now(UTC).isoformat(),
    )


def to_json(reading: MockReading) -> str:
    return json.dumps(asdict(reading), indent=2)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Emit mock biosensor readings as JSON lines.")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--crop", choices=CROPS, default="coffee")
    parser.add_argument("--contamination", choices=("low", "moderate", "severe"), default="low")
    parser.add_argument("--file", help="Optional output file (defaults to stdout)")
    args = parser.parse_args()

    def emit():
        for _ in range(args.count):
            yield to_json(generate_reading(crop=args.crop, contamination=args.contamination))

    if args.file:
        with open(args.file, "w", encoding="utf-8") as fh:
            for line in emit():
                fh.write(line + "\n")
        print(f"Wrote {args.count} readings to {args.file}")
    else:
        for line in emit():
            print(line)
