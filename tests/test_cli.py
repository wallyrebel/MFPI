from __future__ import annotations

import json

import pytest

from mfpi.cli import main


def test_skip_existing_returns_success_without_fetching(tmp_path, monkeypatch, capsys) -> None:
    archive = tmp_path / "2026" / "week-01"
    archive.mkdir(parents=True)

    class UnexpectedProvider:
        def __init__(self) -> None:
            raise AssertionError("live providers must not run for an existing snapshot")

    monkeypatch.setattr("mfpi.cli.MHSAAClassificationProvider", UnexpectedProvider)

    result = main(
        [
            "--live",
            "--week",
            "1",
            "--data-root",
            str(tmp_path),
            "--skip-existing",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert result == 0
    assert output["status"] == "ALREADY_PUBLISHED"
    assert output["archive"] == str(archive)


@pytest.mark.parametrize("conflicting_flag", ["--corrected", "--no-publish"])
def test_skip_existing_rejects_conflicting_modes(conflicting_flag: str) -> None:
    with pytest.raises(SystemExit) as error:
        main(["--live", "--skip-existing", conflicting_flag])

    assert error.value.code == 2
