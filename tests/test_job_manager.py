"""
Tests for JobManager result fields (PR #27).

The scraper is replaced by a stub, so no browser is launched. The job runs
synchronously through _run_scraping_job() instead of the thread pool.
"""

import pytest

from modules import job_manager as jm
from modules.job_manager import JobManager, JobStatus


class StubScraper:
    """Sets the attributes the real scraper sets during a run."""

    result = True
    warning = None

    def __init__(self, config, cancel_event=None):
        self.place_id = None
        self.total_reviews = None

    def scrape(self):
        self.place_id = "0x882b21e060e098b7:0"
        self.total_reviews = None if self.result is False else 42
        return self.result


@pytest.fixture
def manager(monkeypatch):
    monkeypatch.setattr(jm, "load_config", lambda: {})
    monkeypatch.setattr(jm, "GoogleReviewsScraper", StubScraper)
    m = JobManager(max_concurrent_jobs=1)
    yield m
    m.executor.shutdown(wait=False)


def test_completed_job_reports_place_id_and_count(manager):
    StubScraper.result = True
    job_id = manager.create_job("https://maps.app.goo.gl/x")
    manager._run_scraping_job(job_id)

    data = manager.get_job(job_id).to_dict()
    assert data["status"] == JobStatus.COMPLETED.value
    assert data["place_id"] == "0x882b21e060e098b7:0"
    assert data["reviews_count"] == 42


def test_limited_view_warning_reaches_job(manager):
    StubScraper.result = True
    StubScraper.warning = "Google showed only 5 of about 746 reviews"
    try:
        job_id = manager.create_job("https://maps.app.goo.gl/x")
        manager._run_scraping_job(job_id)
    finally:
        StubScraper.warning = None

    data = manager.get_job(job_id).to_dict()
    assert data["status"] == JobStatus.COMPLETED.value
    assert data["warning"] == "Google showed only 5 of about 746 reviews"
    assert data["progress"]["message"] == data["warning"]


def test_failed_job_still_reports_place_id(manager):
    StubScraper.result = False
    job_id = manager.create_job("https://maps.app.goo.gl/x")
    manager._run_scraping_job(job_id)

    data = manager.get_job(job_id).to_dict()
    assert data["status"] == JobStatus.FAILED.value
    assert data["place_id"] == "0x882b21e060e098b7:0"
    assert data["reviews_count"] is None


def test_job_response_accepts_place_id(manager, tmp_path, monkeypatch):
    # Importing api_server loads config.yaml from the working directory and
    # writes a default one if missing, so import it from an empty temp dir.
    monkeypatch.chdir(tmp_path)
    from api_server import JobResponse

    StubScraper.result = True
    job_id = manager.create_job("https://maps.app.goo.gl/x")
    manager._run_scraping_job(job_id)

    response = JobResponse(**manager.get_job(job_id).to_dict())
    assert response.place_id == "0x882b21e060e098b7:0"
    assert response.reviews_count == 42
