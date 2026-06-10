"""Tests for the real-time QA runner (core/qa/live_qa.py)."""
import pytest
from core.qa.live_qa import LiveQARunner


def test_run_tests_all_pass(qa_runner, sample_good_rows):
    result = qa_runner.run_tests(sample_good_rows)
    assert result["status"] == "PASS"
    assert result["passed"] == result["total"]
    assert result["pass_rate"] == 100.0
    assert len(result["tests"]) >= 6


def test_run_tests_detects_failures(qa_runner, sample_bad_rows):
    result = qa_runner.run_tests(sample_bad_rows)
    assert result["status"] == "FAIL"
    assert result["failed"] > 0
    assert result["pass_rate"] < 100


def test_required_fields(qa_runner, sample_good_rows, sample_bad_rows):
    ok = qa_runner._test_required_fields(sample_good_rows)
    assert ok["passed"] is True

    bad = qa_runner._test_required_fields(sample_bad_rows)
    assert bad["passed"] is False
    assert "incompletas" in bad["detail"]


def test_price_format(qa_runner, sample_good_rows, sample_bad_rows):
    ok = qa_runner._test_price_format(sample_good_rows)
    assert ok["passed"] is True

    bad = qa_runner._test_price_format(sample_bad_rows)
    assert bad["passed"] is False


def test_provider_with_price(qa_runner, sample_bad_rows):
    bad = qa_runner._test_no_empty_proveedor_with_price(sample_bad_rows)
    assert bad["passed"] is False
    assert "sin proveedor" in bad["detail"]


def test_has_rows(qa_runner):
    assert qa_runner._test_has_rows([])["passed"] is False
    assert qa_runner._test_has_rows([{"a": 1}])["passed"] is True


def test_metadata_coverage(qa_runner, sample_good_rows):
    res = qa_runner._test_metadata_coverage(sample_good_rows)
    # In the fixture we have at least NIT or Correo in one row
    assert res["passed"] is True
