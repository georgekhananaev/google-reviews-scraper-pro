#!/usr/bin/env python3
"""
FastAPI server for Google Reviews Scraper.
Provides REST API endpoints to trigger and manage scraping jobs.
"""

import logging
import asyncio
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl, Field

from modules.job_manager import JobManager, JobStatus, ScrapingJob

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger("api_server")

# Global job manager instance
job_manager: Optional[JobManager] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown"""
    global job_manager
    
    # Startup
    log.info("Starting Google Reviews Scraper API Server")
    job_manager = JobManager(max_concurrent_jobs=3)
    
    # Start auto-cleanup task
    asyncio.create_task(cleanup_jobs_periodically())
    
    yield
    
    # Shutdown
    log.info("Shutting down Google Reviews Scraper API Server")
    if job_manager:
        job_manager.shutdown()


# Initialize FastAPI app
app = FastAPI(
    title="Google Reviews Scraper API",
    description="REST API for triggering and managing Google Maps review scraping jobs",
    version="1.0.3",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models for API
class ScrapeRequest(BaseModel):
    """Request model for starting a scrape job"""
    url: HttpUrl = Field(..., description="Google Maps URL to scrape")
    headless: Optional[bool] = Field(None, description="Run Chrome in headless mode")
    sort_by: Optional[str] = Field(None, description="Sort order: newest, highest, lowest, relevance")
    stop_on_match: Optional[bool] = Field(None, description="Stop when first already-seen review is encountered")
    overwrite_existing: Optional[bool] = Field(None, description="Overwrite existing reviews instead of appending")
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


# Background task for periodic cleanup
async def cleanup_jobs_periodically():
    """Periodically clean up old jobs"""
    while True:
        await asyncio.sleep(3600)  # Run every hour
        if job_manager:
            job_manager.cleanup_old_jobs(max_age_hours=24)


# API Endpoints

@app.get("/", summary="API Health Check")
async def root():
    """Health check endpoint"""
    return {
        "message": "Google Reviews Scraper API is running",
        "status": "healthy",
        "version": "1.0.3"
    }


@app.post("/scrape", response_model=Dict[str, str], summary="Start Scraping Job")
async def start_scrape(request: ScrapeRequest, background_tasks: BackgroundTasks):
    """
    Start a new scraping job in the background.
    
    Returns the job ID that can be used to check status.
    """
    if not job_manager:
        raise HTTPException(status_code=500, detail="Job manager not initialized")
    
    # Prepare config overrides
    config_overrides = {}
    
    # Only include non-None values
    for field, value in request.dict().items():
        if value is not None and field != "url":
            config_overrides[field] = value
    
    # Convert URL to string
    url = str(request.url)
    
    try:
        # Create job
        job_id = job_manager.create_job(url, config_overrides)
        
        # Start job immediately if possible
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


@app.get("/jobs/{job_id}", response_model=JobResponse, summary="Get Job Status")
async def get_job(job_id: str):
    """Get detailed information about a specific job"""
    if not job_manager:
        raise HTTPException(status_code=500, detail="Job manager not initialized")
    
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobResponse(**job.to_dict())


@app.get("/jobs", response_model=List[JobResponse], summary="List Jobs")
async def list_jobs(
    status: Optional[JobStatus] = Query(None, description="Filter by job status"),
    limit: int = Query(100, description="Maximum number of jobs to return", ge=1, le=1000)
):
    """List all jobs, optionally filtered by status"""
    if not job_manager:
        raise HTTPException(status_code=500, detail="Job manager not initialized")
    
    jobs = job_manager.list_jobs(status=status, limit=limit)
    return [JobResponse(**job.to_dict()) for job in jobs]


@app.post("/jobs/{job_id}/start", summary="Start Pending Job")
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


@app.post("/jobs/{job_id}/cancel", summary="Cancel Job")
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


@app.delete("/jobs/{job_id}", summary="Delete Job")
async def delete_job(job_id: str):
    """Delete a job from the system"""
    if not job_manager:
        raise HTTPException(status_code=500, detail="Job manager not initialized")
    
    deleted = job_manager.delete_job(job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {"message": "Job deleted successfully"}


@app.get("/stats", response_model=JobStatsResponse, summary="Get Job Statistics")
async def get_stats():
    """Get job manager statistics"""
    if not job_manager:
        raise HTTPException(status_code=500, detail="Job manager not initialized")
    
    stats = job_manager.get_stats()
    return JobStatsResponse(**stats)


@app.post("/cleanup", summary="Manual Job Cleanup")
async def cleanup_jobs(max_age_hours: int = Query(24, description="Maximum age in hours", ge=1)):
    """Manually trigger cleanup of old completed/failed jobs"""
    if not job_manager:
        raise HTTPException(status_code=500, detail="Job manager not initialized")
    
    job_manager.cleanup_old_jobs(max_age_hours=max_age_hours)
    return {"message": f"Cleaned up jobs older than {max_age_hours} hours"}


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