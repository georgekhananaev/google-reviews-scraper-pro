#!/usr/bin/env python3
"""
FastAPI server for Google Reviews Scraper.
Provides REST API endpoints to trigger and manage scraping jobs,
query reviews/places from SQLite, manage API keys, and view audit logs.
"""

import json
import logging
import asyncio
import os
import time
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, Depends, Security, Request, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, HttpUrl, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from modules.config import load_config
from modules.job_manager import JobManager, JobStatus

# --- Load config for API settings ---
_config = load_config()
_api_config = _config.get("api", {})

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(request: Request, key: Optional[str] = Security(_api_key_header)):
    """Authenticate via DB-managed API keys. Open access when no keys exist."""
    api_key_db = getattr(request.app.state, "api_key_db", None)

    # DB keys required when any active key exists
    if api_key_db and api_key_db.has_active_keys():
        if not key:
            raise HTTPException(status_code=401, detail="Missing API key")
        info = api_key_db.verify_key(key)
        if not info:
            raise HTTPException(status_code=401, detail="Invalid or revoked API key")
        request.state.api_key_info = info
        return

    # No keys configured — open access
    request.state.api_key_info = None


log = logging.getLogger("api_server")

# Global job manager instance
job_manager: Optional[JobManager] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown"""
    global job_manager

    # Startup — structured logging
    from modules.log_manager import setup_logging
    setup_logging(
        level=_config.get("log_level", "INFO"),
        log_dir=_config.get("log_dir", "logs"),
        log_file=_config.get("log_file", "scraper.log"),
    )
    log.info("Starting Google Reviews Scraper API Server")
    job_manager = JobManager(max_concurrent_jobs=3)

    db_path = _config.get("db_path", "reviews.db")

    # Initialize API key DB
    from modules.api_keys import ApiKeyDB
    app.state.api_key_db = ApiKeyDB(db_path)
    log.info("API key database initialized")

    # Initialize Review DB (read-only queries, safe with WAL mode)
    from modules.review_db import ReviewDB
    app.state.review_db = ReviewDB(db_path)
    log.info("Review database initialized")

    # Start auto-cleanup task
    asyncio.create_task(cleanup_jobs_periodically())

    yield

    # Shutdown
    log.info("Shutting down Google Reviews Scraper API Server")
    if hasattr(app.state, "review_db"):
        app.state.review_db.close()
    if hasattr(app.state, "api_key_db"):
        app.state.api_key_db.close()
    if job_manager:
        job_manager.shutdown()


# Initialize FastAPI app
app = FastAPI(
    title="Google Reviews Scraper API",
    description="REST API for triggering and managing Google Maps review scraping jobs",
    version="1.2.1",
    lifespan=lifespan
)


# --- Audit Middleware ---

class AuditMiddleware(BaseHTTPMiddleware):
    """Log every request to the API audit table."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.monotonic()
        response = await call_next(request)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        api_key_db = getattr(request.app.state, "api_key_db", None)
        if api_key_db is None:
            return response

        key_info = getattr(request.state, "api_key_info", None) if hasattr(request.state, "api_key_info") else None
        key_id = key_info["id"] if key_info else None
        key_name = key_info["name"] if key_info else None
        client_ip = request.client.host if request.client else None

        try:
            api_key_db.log_request(
                key_id=key_id,
                key_name=key_name,
                endpoint=request.url.path,
                method=request.method,
                client_ip=client_ip,
                status_code=response.status_code,
                response_time_ms=elapsed_ms,
            )
        except Exception:
            log.exception("Failed to write audit log entry")

        return response


app.add_middleware(AuditMiddleware)

# CORS — env var takes precedence, then config.yaml, then default "*".
_raw_origins = (
    os.environ.get("ALLOWED_ORIGINS", "")
    or _api_config.get("allowed_origins", "*")
)
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=_raw_origins != "*",
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Dependency helpers
# ---------------------------------------------------------------------------

def get_review_db(request: Request):
    """Get ReviewDB from app state."""
    db = getattr(request.app.state, "review_db", None)
    if db is None:
        raise HTTPException(status_code=500, detail="Review database not initialized")
    return db


def get_api_key_db(request: Request):
    """Get ApiKeyDB from app state."""
    db = getattr(request.app.state, "api_key_db", None)
    if db is None:
        raise HTTPException(status_code=500, detail="API key database not initialized")
    return db


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

# --- Jobs ---
class ScrapeRequest(BaseModel):
    """Request model for starting a scrape job"""
    url: HttpUrl = Field(..., description="Google Maps URL to scrape")
    headless: Optional[bool] = Field(None, description="Run Chrome in headless mode")
    sort_by: Optional[str] = Field(None, description="Sort order: newest, highest, lowest, relevance")
    scrape_mode: Optional[str] = Field(None, description="Scrape mode: new_only, update, or full")
    stop_threshold: Optional[int] = Field(None, description="Consecutive matched batches before stopping")
    max_reviews: Optional[int] = Field(None, description="Max reviews to scrape (0 = unlimited)")
    max_scroll_attempts: Optional[int] = Field(None, description="Max scroll iterations")
    scroll_idle_limit: Optional[int] = Field(None, description="Max idle iterations with zero new cards")
    download_images: Optional[bool] = Field(None, description="Download images from reviews")
    use_s3: Optional[bool] = Field(None, description="Upload images to S3")
    custom_params: Optional[Dict[str, Any]] = Field(None, description="Custom parameters to add to each document")


class JobResponse(BaseModel):
    """Response model for job information"""
    job_id: str
    status: JobStatus
    url: str
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    reviews_count: Optional[int] = None
    images_count: Optional[int] = None
    progress: Optional[Dict[str, Any]] = None


class JobStatsResponse(BaseModel):
    """Response model for job statistics"""
    total_jobs: int
    by_status: Dict[str, int]
    running_jobs: int
    max_concurrent_jobs: int


# --- Places ---
class PlaceResponse(BaseModel):
    place_id: str
    place_name: Optional[str] = None
    original_url: str
    resolved_url: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    first_seen: str
    last_scraped: Optional[str] = None
    total_reviews: int = 0


# --- Reviews ---
class ReviewResponse(BaseModel):
    review_id: str
    place_id: str
    author: Optional[str] = None
    rating: Optional[float] = None
    review_text: Optional[Any] = None
    review_date: Optional[str] = None
    raw_date: Optional[str] = None
    likes: int = 0
    user_images: Optional[Any] = None
    s3_images: Optional[Any] = None
    profile_url: Optional[str] = None
    profile_picture: Optional[str] = None
    s3_profile_picture: Optional[str] = None
    owner_responses: Optional[Any] = None
    created_date: str
    last_modified: str
    last_seen_session: Optional[int] = None
    last_changed_session: Optional[int] = None
    is_deleted: int = 0
    content_hash: Optional[str] = None
    engagement_hash: Optional[str] = None
    row_version: int = 1


class PaginatedReviewsResponse(BaseModel):
    place_id: str
    total: int
    limit: int
    offset: int
    reviews: List[ReviewResponse]


class ReviewHistoryEntry(BaseModel):
    history_id: int
    review_id: str
    place_id: str
    session_id: Optional[int] = None
    actor: str
    action: str
    changed_fields: Optional[Any] = None
    old_content_hash: Optional[str] = None
    new_content_hash: Optional[str] = None
    old_engagement_hash: Optional[str] = None
    new_engagement_hash: Optional[str] = None
    timestamp: str


# --- Audit ---
class AuditLogEntry(BaseModel):
    id: int
    timestamp: str
    key_id: Optional[int] = None
    key_name: Optional[str] = None
    endpoint: str
    method: str
    client_ip: Optional[str] = None
    status_code: Optional[int] = None
    response_time_ms: Optional[int] = None


# --- DB Stats ---
class PlaceStatRow(BaseModel):
    place_id: str
    place_name: Optional[str] = None
    total_reviews: int = 0
    last_scraped: Optional[str] = None


class DbStatsResponse(BaseModel):
    places_count: int = 0
    reviews_count: int = 0
    scrape_sessions_count: int = 0
    review_history_count: int = 0
    sync_checkpoints_count: int = 0
    place_aliases_count: int = 0
    db_size_bytes: int = 0
    places: List[PlaceStatRow] = []


# ---------------------------------------------------------------------------
# Background task for periodic cleanup
# ---------------------------------------------------------------------------

async def cleanup_jobs_periodically():
    """Periodically clean up old jobs"""
    while True:
        await asyncio.sleep(3600)  # Run every hour
        if job_manager:
            job_manager.cleanup_old_jobs(max_age_hours=24)


# ---------------------------------------------------------------------------
# Helper to strip internal keys from deserialized reviews
# ---------------------------------------------------------------------------

def _clean_review(row: Dict[str, Any]) -> Dict[str, Any]:
    """Strip _-prefixed internal keys added by _deserialize_review()."""
    return {k: v for k, v in row.items() if not k.startswith("_")}


# ===========================================================================
# Routers
# ===========================================================================

# --- System Router ---
system_router = APIRouter(tags=["System"])


@system_router.get("/", summary="API Health Check")
async def root():
    """Health check endpoint"""
    return {
        "message": "Google Reviews Scraper API is running",
        "status": "healthy",
        "version": "1.2.1"
    }


@system_router.get("/db-stats", response_model=DbStatsResponse, summary="Database Statistics",
                    dependencies=[Depends(require_api_key)])
async def get_db_stats(review_db=Depends(get_review_db)):
    """Get ReviewDB statistics (places, reviews, sessions, db size)."""
    stats = review_db.get_stats()
    place_rows = [
        PlaceStatRow(
            place_id=p["place_id"],
            place_name=p.get("place_name"),
            total_reviews=p.get("total_reviews", 0),
            last_scraped=p.get("last_scraped"),
        )
        for p in stats.get("places", [])
    ]
    return DbStatsResponse(
        places_count=stats.get("places_count", 0),
        reviews_count=stats.get("reviews_count", 0),
        scrape_sessions_count=stats.get("scrape_sessions_count", 0),
        review_history_count=stats.get("review_history_count", 0),
        sync_checkpoints_count=stats.get("sync_checkpoints_count", 0),
        place_aliases_count=stats.get("place_aliases_count", 0),
        db_size_bytes=stats.get("db_size_bytes", 0),
        places=place_rows,
    )


@system_router.post("/cleanup", summary="Manual Job Cleanup",
                     dependencies=[Depends(require_api_key)])
async def cleanup_jobs(max_age_hours: int = Query(24, description="Maximum age in hours", ge=1)):
    """Manually trigger cleanup of old completed/failed jobs"""
    if not job_manager:
        raise HTTPException(status_code=500, detail="Job manager not initialized")

    job_manager.cleanup_old_jobs(max_age_hours=max_age_hours)
    return {"message": f"Cleaned up jobs older than {max_age_hours} hours"}


# --- Jobs Router ---
jobs_router = APIRouter(tags=["Jobs"], dependencies=[Depends(require_api_key)])


@jobs_router.post("/scrape", response_model=Dict[str, str], summary="Start Scraping Job")
async def start_scrape(request: ScrapeRequest, background_tasks: BackgroundTasks):
    """
    Start a new scraping job in the background.

    Returns the job ID that can be used to check status.
    """
    if not job_manager:
        raise HTTPException(status_code=500, detail="Job manager not initialized")

    config_overrides = {}
    for field, value in request.dict().items():
        if value is not None and field != "url":
            config_overrides[field] = value

    url = str(request.url)

    try:
        job_id = job_manager.create_job(url, config_overrides)
        started = job_manager.start_job(job_id)
        log.info(f"Created scraping job {job_id} for URL: {url}")

        return {
            "job_id": job_id,
            "status": "started" if started else "queued",
            "message": f"Scraping job {'started' if started else 'queued'} successfully"
        }

    except Exception as e:
        log.error(f"Error creating scraping job: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create scraping job: {str(e)}")


@jobs_router.get("/jobs/{job_id}", response_model=JobResponse, summary="Get Job Status")
async def get_job(job_id: str):
    """Get detailed information about a specific job"""
    if not job_manager:
        raise HTTPException(status_code=500, detail="Job manager not initialized")

    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobResponse(**job.to_dict())


@jobs_router.get("/jobs", response_model=List[JobResponse], summary="List Jobs")
async def list_jobs(
    status: Optional[JobStatus] = Query(None, description="Filter by job status"),
    limit: int = Query(100, description="Maximum number of jobs to return", ge=1, le=1000)
):
    """List all jobs, optionally filtered by status"""
    if not job_manager:
        raise HTTPException(status_code=500, detail="Job manager not initialized")

    jobs = job_manager.list_jobs(status=status, limit=limit)
    return [JobResponse(**job.to_dict()) for job in jobs]


@jobs_router.post("/jobs/{job_id}/start", summary="Start Pending Job")
async def start_job(job_id: str):
    """Start a pending job manually"""
    if not job_manager:
        raise HTTPException(status_code=500, detail="Job manager not initialized")

    started = job_manager.start_job(job_id)
    if not started:
        job = job_manager.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        if job.status != JobStatus.PENDING:
            raise HTTPException(status_code=400, detail=f"Job is not pending (current status: {job.status})")

        raise HTTPException(status_code=429, detail="Maximum concurrent jobs reached")

    return {"message": "Job started successfully"}


@jobs_router.post("/jobs/{job_id}/cancel", summary="Cancel Job")
async def cancel_job(job_id: str):
    """Cancel a pending or running job"""
    if not job_manager:
        raise HTTPException(status_code=500, detail="Job manager not initialized")

    cancelled = job_manager.cancel_job(job_id)
    if not cancelled:
        job = job_manager.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        raise HTTPException(status_code=400, detail="Job cannot be cancelled (already completed, failed, or cancelled)")

    return {"message": "Job cancelled successfully"}


@jobs_router.delete("/jobs/{job_id}", summary="Delete Job")
async def delete_job(job_id: str):
    """Delete a job from the system (only terminal-state jobs)"""
    if not job_manager:
        raise HTTPException(status_code=500, detail="Job manager not initialized")

    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    deleted = job_manager.delete_job(job_id)
    if not deleted:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete job in '{job.status.value}' state. Cancel it first.",
        )

    return {"message": "Job deleted successfully"}


# --- Places Router ---
places_router = APIRouter(tags=["Places"], dependencies=[Depends(require_api_key)])


@places_router.get("/places", response_model=List[PlaceResponse], summary="List Places")
async def list_places(review_db=Depends(get_review_db)):
    """List all registered places from the database."""
    places = review_db.list_places()
    return [PlaceResponse(**p) for p in places]


@places_router.get("/places/{place_id}", response_model=PlaceResponse, summary="Get Place")
async def get_place(place_id: str, review_db=Depends(get_review_db)):
    """Get details for a specific place."""
    place = review_db.get_place(place_id)
    if not place:
        raise HTTPException(status_code=404, detail="Place not found")
    return PlaceResponse(**place)


# --- Reviews Router ---
reviews_router = APIRouter(tags=["Reviews"], dependencies=[Depends(require_api_key)])


@reviews_router.get("/reviews/{place_id}", response_model=PaginatedReviewsResponse,
                     summary="List Reviews for Place")
async def list_reviews(
    place_id: str,
    limit: int = Query(50, ge=1, le=1000, description="Reviews per page"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    include_deleted: bool = Query(False, description="Include soft-deleted reviews"),
    review_db=Depends(get_review_db),
):
    """Get paginated reviews for a place."""
    place = review_db.get_place(place_id)
    if not place:
        raise HTTPException(status_code=404, detail="Place not found")

    total = review_db.count_reviews(place_id, include_deleted=include_deleted)
    rows = review_db.get_reviews(place_id, limit=limit, offset=offset,
                                  include_deleted=include_deleted)
    reviews = [ReviewResponse(**_clean_review(r)) for r in rows]
    return PaginatedReviewsResponse(
        place_id=place_id, total=total, limit=limit, offset=offset, reviews=reviews,
    )


@reviews_router.get("/reviews/{place_id}/{review_id}", response_model=ReviewResponse,
                     summary="Get Single Review")
async def get_review(place_id: str, review_id: str, review_db=Depends(get_review_db)):
    """Get a single review by ID."""
    row = review_db.get_review(review_id, place_id)
    if not row:
        raise HTTPException(status_code=404, detail="Review not found")
    return ReviewResponse(**_clean_review(row))


@reviews_router.get("/reviews/{place_id}/{review_id}/history",
                     response_model=List[ReviewHistoryEntry],
                     summary="Get Review Change History")
async def get_review_history(place_id: str, review_id: str,
                              review_db=Depends(get_review_db)):
    """Get the full change history for a specific review."""
    row = review_db.get_review(review_id, place_id)
    if not row:
        raise HTTPException(status_code=404, detail="Review not found")

    history = review_db.get_review_history(review_id, place_id)
    entries = []
    for h in history:
        h = dict(h)
        # Deserialize changed_fields JSON string
        if isinstance(h.get("changed_fields"), str):
            try:
                h["changed_fields"] = json.loads(h["changed_fields"])
            except (json.JSONDecodeError, TypeError):
                pass
        entries.append(ReviewHistoryEntry(**h))
    return entries


# --- Audit Log Router ---
audit_router = APIRouter(tags=["Audit Log"], dependencies=[Depends(require_api_key)])


@audit_router.get("/audit-log", response_model=List[AuditLogEntry],
                   summary="Query Audit Log")
async def query_audit_log(
    key_id: Optional[int] = Query(None, description="Filter by API key ID"),
    limit: int = Query(50, ge=1, le=1000, description="Max entries to return"),
    since: Optional[str] = Query(None, description="Only entries after this ISO timestamp"),
    api_key_db=Depends(get_api_key_db),
):
    """Query the API request audit log."""
    entries = api_key_db.query_audit_log(key_id=key_id, limit=limit, since=since)
    return [AuditLogEntry(**e) for e in entries]


# ===========================================================================
# Register all routers
# ===========================================================================
app.include_router(system_router)
app.include_router(jobs_router)
app.include_router(places_router)
app.include_router(reviews_router)
app.include_router(audit_router)


if __name__ == "__main__":
    import uvicorn

    log.info("Starting FastAPI server...")
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
