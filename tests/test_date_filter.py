"""Tests for DateFilter (issue #19)."""

import pytest

from modules.date_filter import DateFilter


class TestDateFilterParsing:
    def test_no_config_disabled(self):
        df = DateFilter({})
        assert not df.enabled
        assert df.includes("anything")

    def test_empty_boundaries_disabled(self):
        df = DateFilter({"date_filter": {"after": "", "before": ""}})
        assert not df.enabled

    def test_after_only(self):
        df = DateFilter({"date_filter": {"after": "2025-06-01"}})
        assert df.enabled
        assert df.includes("2025-07-15T00:00:00+00:00")
        assert not df.includes("2025-05-15T00:00:00+00:00")

    def test_before_only(self):
        df = DateFilter({"date_filter": {"before": "2025-09-30"}})
        assert df.enabled
        assert df.includes("2025-05-15T00:00:00+00:00")
        assert not df.includes("2025-12-01T00:00:00+00:00")

    def test_after_and_before(self):
        df = DateFilter({"date_filter": {"after": "2025-06-01", "before": "2025-09-30"}})
        assert df.includes("2025-07-15T00:00:00+00:00")
        assert not df.includes("2025-05-15T00:00:00+00:00")
        assert not df.includes("2025-10-15T00:00:00+00:00")

    def test_full_datetime_boundary(self):
        df = DateFilter({"date_filter": {"after": "2025-06-01T12:00:00+00:00"}})
        assert df.includes("2025-06-01T13:00:00+00:00")
        assert not df.includes("2025-06-01T11:00:00+00:00")

    def test_unparseable_date_included_by_default(self):
        df = DateFilter({"date_filter": {"after": "2025-06-01"}})
        assert df.includes("")
        assert df.includes("not a date")

    def test_unparseable_date_excluded_when_configured(self):
        df = DateFilter({
            "date_filter": {
                "after": "2025-06-01",
                "on_unparseable_date": "exclude",
            }
        })
        assert not df.includes("")

    def test_invalid_boundary_logged_and_ignored(self):
        df = DateFilter({"date_filter": {"after": "garbage"}})
        assert not df.enabled


class TestEarlyStopMode:
    def test_early_stop_enabled_with_after(self):
        df = DateFilter({
            "date_filter": {"after": "2025-06-01", "mode": "early_stop"}
        })
        assert df.early_stop_enabled
        assert df.is_past_boundary("2025-05-15T00:00:00+00:00")
        assert not df.is_past_boundary("2025-07-15T00:00:00+00:00")

    def test_early_stop_disabled_without_after(self):
        df = DateFilter({
            "date_filter": {"before": "2025-09-30", "mode": "early_stop"}
        })
        assert not df.early_stop_enabled

    def test_post_filter_mode_no_early_stop(self):
        df = DateFilter({
            "date_filter": {"after": "2025-06-01", "mode": "post_filter"}
        })
        assert not df.early_stop_enabled

    def test_past_boundary_returns_false_for_unparseable(self):
        df = DateFilter({
            "date_filter": {"after": "2025-06-01", "mode": "early_stop"}
        })
        assert not df.is_past_boundary("")
        assert not df.is_past_boundary("not a date")
