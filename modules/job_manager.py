"""
Background job manager for Google Reviews Scraper.
"""

import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from modules.config import load_config
from modules.scraper import GoogleReviewsScraper

log = logging.getLogger("scraper")


class JobStatus(str, Enum):
    """Job status enumeration"""
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ScrapingJob:
    """Scraping job data class"""
    job_id: str
    status: JobStatus
    url: str
    config: Dict[str, Any]
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    reviews_count: Optional[int] = None
    images_count: Optional[int] = None
    progress: Dict[str, Any] = None
    cancel_event: threading.Event = None
    _scraper: Optional[Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary for JSON serialization"""
        data = {
            "job_id": self.job_id,
            "status": self.status.value if isinstance(self.status, JobStatus) else self.status,
            "url": self.url,
            "config": self.config,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "reviews_count": self.reviews_count,
            "images_count": self.images_count,
            "progress": self.progress,
        }
        return data


class JobManager:
    """Manager for background scraping jobs"""
    
    def __init__(self, max_concurrent_jobs: int = 3):
        """Initialize job manager"""
        self.max_concurrent_jobs = max_concurrent_jobs
        self.jobs: Dict[str, ScrapingJob] = {}
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent_jobs)
        self.lock = threading.Lock()
        
    def create_job(self, url: str, config_overrides: Dict[str, Any] = None) -> str:
        """
        Create a new scraping job.
        
        Args:
            url: Google Maps URL to scrape
            config_overrides: Optional config overrides
            
        Returns:
            Job ID
        """
        job_id = str(uuid.uuid4())
        
        # Load base config
        config = load_config()
        
        # Apply URL
        config["url"] = url
        
        # Apply any overrides
        if config_overrides:
            config.update(config_overrides)
            
        job = ScrapingJob(
            job_id=job_id,
            status=JobStatus.PENDING,
            url=url,
            config=config,
            created_at=datetime.now(),
            progress={"stage": "created", "message": "Job created and queued"},
            cancel_event=threading.Event(),
        )
        
        with self.lock:
            self.jobs[job_id] = job
            
        log.info(f"Created scraping job {job_id} for URL: {url}")
        return job_id
    
    def start_job(self, job_id: str) -> bool:
        """
        Start a pending job.
        
        Args:
            job_id: Job ID to start
            
        Returns:
            True if job was started, False otherwise
        """
        with self.lock:
            if job_id not in self.jobs:
                return False
                
            job = self.jobs[job_id]
            if job.status != JobStatus.PENDING:
                return False
                
            # Check if we can start more jobs
            running_count = sum(1 for j in self.jobs.values() if j.status == JobStatus.RUNNING)
            if running_count >= self.max_concurrent_jobs:
                return False
                
            job.status = JobStatus.RUNNING
            job.started_at = datetime.now()
            job.progress = {"stage": "starting", "message": "Initializing scraper"}
            
        # Submit job to thread pool
        future = self.executor.submit(self._run_scraping_job, job_id)
        
        log.info(f"Started scraping job {job_id}")
        return True
    
    def _run_scraping_job(self, job_id: str):
        """
        Run the actual scraping job in background thread.
        
        Args:
            job_id: Job ID to run
        """
        try:
            with self.lock:
                job = self.jobs[job_id]
                job.progress = {"stage": "initializing", "message": "Setting up scraper"}
            
            # Create scraper with job config and cancel event
            scraper = GoogleReviewsScraper(job.config, cancel_event=job.cancel_event)

            with self.lock:
                job._scraper = scraper
                job.progress = {"stage": "scraping", "message": "Scraping reviews in progress"}

            # Run the scraping
            success = scraper.scrape()

            # Mark job based on scrape result — never overwrite CANCELLED
            with self.lock:
                if job.status == JobStatus.CANCELLED:
                    log.info(f"Job {job_id} was cancelled during execution")
                elif success:
                    job.status = JobStatus.COMPLETED
                    job.completed_at = datetime.now()
                    job.progress = {"stage": "completed", "message": "Scraping completed successfully"}
                else:
                    job.status = JobStatus.FAILED
                    job.completed_at = datetime.now()
                    job.error_message = "Scraper returned failure (no reviews found or navigation error)"
                    job.progress = {"stage": "failed", "message": "Scraping failed"}

                job.reviews_count = getattr(scraper, 'total_reviews', None)
                job.images_count = getattr(scraper, 'total_images', None)
                job._scraper = None

            log.info(f"Completed scraping job {job_id}")

        except Exception as e:
            log.error(f"Error in scraping job {job_id}: {e}")
            with self.lock:
                job = self.jobs.get(job_id)
                if job and job.status != JobStatus.CANCELLED:
                    job.status = JobStatus.FAILED
                    job.completed_at = datetime.now()
                    job.error_message = str(e)
                    job.progress = {"stage": "failed", "message": f"Job failed: {str(e)}"}
                if job:
                    job._scraper = None
    
    def get_job(self, job_id: str) -> Optional[ScrapingJob]:
        """
        Get job by ID.
        
        Args:
            job_id: Job ID
            
        Returns:
            Job object or None if not found
        """
        with self.lock:
            return self.jobs.get(job_id)
    
    def list_jobs(self, status: Optional[JobStatus] = None, limit: int = 100) -> List[ScrapingJob]:
        """
        List jobs, optionally filtered by status.
        
        Args:
            status: Optional status filter
            limit: Maximum number of jobs to return
            
        Returns:
            List of jobs
        """
        with self.lock:
            jobs = list(self.jobs.values())
            
        if status:
            jobs = [job for job in jobs if job.status == status]
            
        # Sort by creation time (newest first)
        jobs.sort(key=lambda x: x.created_at, reverse=True)
        
        return jobs[:limit]
    
    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a pending or running job.

        Sets the cancel event so the scraper's scroll loop exits early.
        """
        with self.lock:
            if job_id not in self.jobs:
                return False

            job = self.jobs[job_id]
            if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                return False

            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.now()
            job.progress = {"stage": "cancelled", "message": "Job was cancelled"}

            # Signal the scraper to stop
            if job.cancel_event:
                job.cancel_event.set()

        log.info(f"Cancelled scraping job {job_id}")
        return True
    
    def delete_job(self, job_id: str) -> bool:
        """
        Delete a job from the manager.

        Only terminal-state jobs (COMPLETED, FAILED, CANCELLED) can be deleted
        to avoid race conditions with running worker threads.
        """
        with self.lock:
            job = self.jobs.get(job_id)
            if not job:
                return False
            if job.status not in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
                return False
            del self.jobs[job_id]

        log.info(f"Deleted scraping job {job_id}")
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get job manager statistics.
        
        Returns:
            Statistics dictionary
        """
        with self.lock:
            jobs = list(self.jobs.values())
            
        stats = {
            "total_jobs": len(jobs),
            "by_status": {},
            "running_jobs": 0,
            "max_concurrent_jobs": self.max_concurrent_jobs
        }
        
        for status in JobStatus:
            count = sum(1 for job in jobs if job.status == status)
            stats["by_status"][status.value] = count
            
        stats["running_jobs"] = stats["by_status"].get(JobStatus.RUNNING.value, 0)
        
        return stats
    
    def cleanup_old_jobs(self, max_age_hours: int = 24):
        """
        Clean up old completed/failed jobs.
        
        Args:
            max_age_hours: Maximum age in hours before cleanup
        """
        cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)
        
        with self.lock:
            to_delete = []
            for job_id, job in self.jobs.items():
                if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                    if job.completed_at and job.completed_at.timestamp() < cutoff_time:
                        to_delete.append(job_id)
            
            for job_id in to_delete:
                del self.jobs[job_id]
                
        if to_delete:
            log.info(f"Cleaned up {len(to_delete)} old jobs")
    
    def shutdown(self):
        """Shutdown the job manager"""
        log.info("Shutting down job manager")
        self.executor.shutdown(wait=True)