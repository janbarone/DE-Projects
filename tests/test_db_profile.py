"""Unit tests for the Postgres memory profile definitions."""
import db_profile


def test_default_profile_is_safe_for_6gb_vm():
    p = db_profile.PROFILES["default"]
    assert p["work_mem"] == "64MB"
    assert p["maintenance_work_mem"] == "256MB"
    assert p["max_parallel_workers_per_gather"] == 2


def test_full_profile_is_larger_than_default():
    d = db_profile.PROFILES["default"]
    f = db_profile.PROFILES["full"]
    assert f["work_mem"] != d["work_mem"]
    assert f["max_parallel_workers_per_gather"] > d["max_parallel_workers_per_gather"]
    assert f["maintenance_work_mem"] != d["maintenance_work_mem"]
