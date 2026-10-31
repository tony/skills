"""Tests for plan_rules.py."""

# ruff: noqa: S101, INP001, PLR2004
import io
import json
import typing as t

import plan_rules
import pytest


def _lapse(capsys: pytest.CaptureFixture[str], *args: str) -> dict[str, object]:
    assert plan_rules.main(["lapse", *args]) == 0
    result: object = json.loads(capsys.readouterr().out)
    assert isinstance(result, dict)
    return t.cast("dict[str, object]", result)


@pytest.mark.parametrize(
    ("unit", "window", "visible_at"),
    [
        ("minutes", "90", "2026-01-01T13:30:00+00:00"),
        ("hours", "36", "2026-01-03T00:00:00+00:00"),
        ("days", "7", "2026-01-08T12:00:00+00:00"),
        ("weeks", "2", "2026-01-15T12:00:00+00:00"),
    ],
)
def test_window_units_convert_to_the_visible_instant(
    capsys: pytest.CaptureFixture[str], unit: str, window: str, visible_at: str
) -> None:
    """Each unit adds its own length to the publication instant."""
    out = _lapse(
        capsys,
        *["--published", "2026-01-01T12:00:00Z", "--window", window, "--unit", unit],
        *["--now", "2026-01-01T12:00:00Z"],
    )

    assert out["visible_at"] == visible_at
    assert out["visible"] is False


def test_boundary_instant_is_visible_and_one_second_before_is_not(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A release is visible from published + window onward, not one second earlier."""
    base = ["--published", "2026-01-01T12:00:00Z", "--window", "7", "--unit", "days"]

    assert _lapse(capsys, *base, "--now", "2026-01-08T11:59:59Z")["visible"] is False
    on_boundary = _lapse(capsys, *base, "--now", "2026-01-08T12:00:00Z")
    assert on_boundary["visible"] is True
    assert on_boundary["visible_day"] == "2026-01-08"


def test_bare_date_counts_as_end_of_day(capsys: pytest.CaptureFixture[str]) -> None:
    """A date with no time of day errs toward waiting: 23:59 UTC."""
    out = _lapse(
        capsys,
        *["--published", "2026-01-01", "--window", "1", "--unit", "days"],
        *["--now", "2026-01-02T23:58:00Z"],
    )

    assert out["visible_at"] == "2026-01-02T23:59:00+00:00"
    assert out["visible"] is False


def test_fixed_cutoff_never_lapses_by_waiting(capsys: pytest.CaptureFixture[str]) -> None:
    """A release after the cutoff stays hidden however late it is."""
    out = _lapse(
        capsys,
        *["--published", "2026-01-10T00:00:00Z", "--cutoff", "2026-01-05T00:00:00Z"],
        *["--now", "2030-01-01T00:00:00Z"],
    )

    assert out == {"kind": "cutoff", "visible_at": None, "visible": False, "waiting_helps": False}


def test_bad_lapse_arguments_exit_2(capsys: pytest.CaptureFixture[str]) -> None:
    """An unknown unit or a zone-less time is refused with a reason."""
    args = ["lapse", "--published", "2026-01-01T12:00:00", "--window", "1", "--unit", "days"]
    assert plan_rules.main(args) == 2
    assert "lapse needs valid arguments" in capsys.readouterr().err
    assert (
        plan_rules.main(["lapse", "--published", "2026-01-01", "--window", "1", "--unit", "years"])
        == 2
    )
    assert plan_rules.main(["bogus"]) == 2


def test_tracks_split_majors_bulk_and_by_hand(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Majors are named bumps, in-range moves are bulk, the rest is read by hand."""
    diff = {
        "path": "/r",
        "uv.lock": {
            "majors": [{"name": "pydantic", "from": ["1.10.0"], "to": ["2.0.0"]}],
            "in_range": [{"name": "requests", "from": ["2.31.0"], "to": ["2.32.0"]}],
        },
        "poetry.lock": {"error": "not readable"},
        "package.json": {
            "majors": [],
            "in_range": [],
            "unclassified": [{"name": "c", "to": "latest"}],
        },
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(diff)))

    assert plan_rules.main(["track"]) == 0
    out = json.loads(capsys.readouterr().out)

    assert [(e["name"], e["track"]) for e in out["entries"]] == [
        ("pydantic", "named"),
        ("requests", "bulk"),
    ]
    assert [b["file"] for b in out["by_hand"]] == ["poetry.lock", "package.json"]


def test_pin_files_classify_by_name(capsys: pytest.CaptureFixture[str]) -> None:
    """Version files are toolchain; package.json and go.mod hold both kinds."""
    assert (
        plan_rules.main(["track", "--pin", ".tool-versions", "sub/.nvmrc", "package.json", "x"])
        == 0
    )
    out = json.loads(capsys.readouterr().out)

    assert out[".tool-versions"] == out["sub/.nvmrc"] == "toolchain"
    assert out["package.json"].startswith("mixed")
    assert out["x"] == "unknown"


@pytest.mark.parametrize("window", ["-3", "0"])
def test_non_positive_window_exits_2(capsys: pytest.CaptureFixture[str], window: str) -> None:
    """A window that would put the date before publication is refused."""
    args = ["lapse", "--published", "2026-01-01T12:00:00Z", "--window", window, "--unit", "days"]

    assert plan_rules.main(args) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "positive window" in captured.err
