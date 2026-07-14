from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import swisseph as swe

from services import western_calc
from services.western_core import WESTERN_CORE_VERSION
from services.yaml_exporter import build_product_yaml


def _payload(*, birth_time: str | None = "08:30") -> dict:
    return {
        "year": 1990,
        "month": 5,
        "day": 15,
        "hour": 8,
        "minute": 30,
        "birth_time": birth_time,
        "lat": 35.6895,
        "lng": 139.6917,
        "include_asteroids": False,
        "include_chiron": False,
        "include_lilith": False,
        "include_vertex": False,
    }


def test_real_western_result_contains_w0_fields():
    result = western_calc.calc_western_from_payload(_payload())

    assert result["planets"]
    assert all("speed" in planet for planet in result["planets"])
    assert result["aspects"]
    assert all("phase" in aspect for aspect in result["aspects"])
    assert result["calculation_rules"]["core_version"] == WESTERN_CORE_VERSION
    assert result["engine_version_western"] == "w0.1.0"


def test_freeastro_asteroids_have_unknown_speed_and_phase():
    def fake_calc_ut(_jd, body_id, _flags):
        lon = float((body_id * 31) % 360)
        return ([lon, 0.0, 0.0, 1.0, 0.0, 0.0], 0)

    fake_asteroids = {
        "planets": [
            {"name": "Ceres", "lon": 0.0},
            {"name": "Pallas", "lon": 0.0},
            {"name": "Juno", "lon": 60.0},
            {"name": "Vesta", "lon": 120.0},
        ]
    }
    payload = _payload()
    payload["include_asteroids"] = True

    with (
        patch.object(western_calc, "configure_ephemeris", return_value=swe.FLG_MOSEPH),
        patch.object(western_calc, "ephemeris_debug_info", return_value={}),
        patch.object(western_calc.swe, "calc_ut", side_effect=fake_calc_ut),
        patch.object(western_calc, "asteroid_api_configured", return_value=True),
        patch.object(western_calc, "fetch_asteroids", return_value=fake_asteroids),
    ):
        result = western_calc.calc_western_from_payload(payload)

    asteroids = [
        planet for planet in result["planets"]
        if planet["name"] in {"Ceres", "Pallas", "Juno", "Vesta"}
    ]
    assert len(asteroids) == 4
    assert all(planet["speed"] is None for planet in asteroids)
    asteroid_aspects = [
        aspect for aspect in result["aspects"]
        if aspect["planet1"] in {"Ceres", "Pallas", "Juno", "Vesta"}
        or aspect["planet2"] in {"Ceres", "Pallas", "Juno", "Vesta"}
    ]
    assert asteroid_aspects
    assert all(aspect["phase"] == "unknown" for aspect in asteroid_aspects)


def test_data_quality_uses_explicit_birth_time():
    known = western_calc.calc_western_from_payload(_payload(birth_time="08:30"))
    unknown = western_calc.calc_western_from_payload(_payload(birth_time=None))

    assert known["data_quality"] == {
        "birth_time": "known",
        "houses_available": True,
        "coordinates": "provided",
    }
    assert unknown["data_quality"] == {
        "birth_time": "unknown",
        "houses_available": False,
        "coordinates": "provided",
    }


def test_customer_yaml_does_not_expose_w0_calculation_fields():
    yaml_text, _prompt, _doc = build_product_yaml(
        title="W0 compatibility",
        birth_date="1990-05-15",
        birth_time="08:30",
        prefecture="東京都",
        birth_place_label="東京都",
        birth_lat=35.6895,
        birth_lng=139.6917,
        include_asteroids=False,
        include_transit=False,
    )

    for field in (
        "phase:",
        "signed_deviation:",
        "calculation_rules:",
        "data_quality:",
    ):
        assert field not in yaml_text


def test_sync_script_check_detects_changes_and_missing_source(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    source = tmp_path / "source"
    product = tmp_path / "product"
    script = product / "scripts" / "sync_western_core.py"
    script.parent.mkdir(parents=True)
    shutil.copyfile(repo_root / "scripts" / "sync_western_core.py", script)

    sync_files = (
        "services/western_core.py",
        "tests/test_western_core_golden.py",
        "tests/fixtures/western_core_golden.json",
    )
    for index, relative in enumerate(sync_files):
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"fixture-{index}\n", encoding="utf-8")

    command = [sys.executable, str(script), "--source", str(source)]
    synced = subprocess.run(command, capture_output=True, text=True, check=False)
    assert synced.returncode == 0, synced.stderr

    checked = subprocess.run(
        [sys.executable, str(script), "--check", "--source", str(source)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr

    changed_file = product / sync_files[0]
    changed_file.write_bytes(changed_file.read_bytes() + b"x")
    changed = subprocess.run(
        [sys.executable, str(script), "--check", "--source", str(source)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert changed.returncode == 1
    assert sync_files[0] in changed.stdout

    missing = subprocess.run(
        [
            sys.executable,
            str(script),
            "--check",
            "--source",
            str(tmp_path / "missing"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert missing.returncode == 2
