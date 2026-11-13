"""Every test gets its own empty integrations folder and audit folder: tests never touch data/integrations
or data/runs."""
import pytest


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    from src.pipeline import handoff
    from src.pipeline.context import _customers

    data, runs = tmp_path / "integrations", tmp_path / "runs"
    runs.mkdir()
    monkeypatch.setenv("TRIAGE_DATA_DIR", str(data))
    monkeypatch.setattr(handoff, "runs_dir", lambda: runs)
    _customers.cache_clear()
    yield {"data": data, "runs": runs}
