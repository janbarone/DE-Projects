"""Safety tests for scripts/make_sample.py target handling."""
import make_sample
import pytest


def test_ensure_safe_target_accepts_sibling(tmp_path):
    source = tmp_path / "data"
    target = tmp_path / "sample_data"
    source.mkdir()
    make_sample.ensure_safe_target(source, target)


def test_ensure_safe_target_rejects_same_directory(tmp_path):
    source = tmp_path / "data"
    source.mkdir()
    with pytest.raises(SystemExit):
        make_sample.ensure_safe_target(source, source)


def test_ensure_safe_target_rejects_target_inside_source(tmp_path):
    source = tmp_path / "data"
    target = source / "sample_data"
    source.mkdir()
    with pytest.raises(SystemExit):
        make_sample.ensure_safe_target(source, target)
