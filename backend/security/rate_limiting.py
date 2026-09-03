"""
Rate limiting middleware for MedScribe API
Prevents abuse and ensures fair usage
"""

import time
from collections import defaultdict
from typing import Dict, Tuple
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter
    Allows burst traffic while maintaining average rate
    """
    
    def __init__(
        self,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        requests_per_day: int = 10000
    ):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.requests_per_day = requests_per_day
        
        # Storage: {identifier: [(timestamp, count), ...]}
        self.minute_buckets: Dict[str, list] = defaultdict(list)
        self.hour_buckets: Dict[str, list] = defaultdict(list)
        self.day_buckets: Dict[str, list] = defaultdict(list)
    
    def _clean_old_requests(self, bucket: list, window_seconds: int):
        """Remove requests older than window"""
        current_time = time.time()
        cutoff_time = current_time - window_seconds
        
        # Remove old entries
        while bucket and bucket[0] < cutoff_time:
            bucket.pop(0)
    
    def check_rate_limit(self, identifier: str) -> Tuple[bool, str, int]:
        """
        Check if request is within rate limits
        
        Returns:
            (allowed, limit_type, retry_after_seconds)
        """
        current_time = time.time()
        
        # Check minute limit
        minute_bucket = self.minute_buckets[identifier]
        self._clean_old_requests(minute_bucket, 60)
        if len(minute_bucket) >= self.requests_per_minute:
            retry_after = int(60 - (current_time - minute_bucket[0]))
            return False, "minute", retry_after
        
        # Check hour limit
        hour_bucket = self.hour_buckets[identifier]
        self._clean_old_requests(hour_bucket, 3600)
        if len(hour_bucket) >= self.requests_per_hour:
            retry_after = int(3600 - (current_time - hour_bucket[0]))
            return False, "hour", retry_after
        
        # Check day limit
        day_bucket = self.day_buckets[identifier]
        self._clean_old_requests(day_bucket, 86400)
        if len(day_bucket) >= self.requests_per_day:
            retry_after = int(86400 - (current_time - day_bucket[0]))
            return False, "day", retry_after
        
        # Add current request
        minute_bucket.append(current_time)
        hour_bucket.append(current_time)
        day_bucket.append(current_time)
        
        return True, "", 0
    
    def get_remaining(self, identifier: str) -> Dict[str, int]:
        """Get remaining requests for each time window"""
        current_time = time.time()
        
        minute_bucket = self.minute_buckets[identifier]
        self._clean_old_requests(minute_bucket, 60)
        
        hour_bucket = self.hour_buckets[identifier]
        self._clean_old_requests(hour_bucket, 3600)
        
        day_bucket = self.day_buckets[identifier]
        self._clean_old_requests(day_bucket, 86400)
        
        return {
            "minute": self.requests_per_minute - len(minute_bucket),
            "hour": self.requests_per_hour - len(hour_bucket),
            "day": self.requests_per_day - len(day_bucket)
        }


# Global rate limiter instance
_rate_limiter = None


def get_rate_limiter() -> RateLimiter:
    """Get or create rate limiter instance"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(
            requests_per_minute=60,
            requests_per_hour=1000,
            requests_per_day=10000
        )
    return _rate_limiter


async def rate_limit_middleware(request: Request, call_next):
    """
    Middleware to enforce rate limiting
    Uses IP address or user ID as identifier
    """
    # Skip rate limiting for health checks
    if request.url.path in ["/health", "/", "/docs", "/openapi.json"]:
        return await call_next(request)
    
    # Get identifier (user ID if authenticated, otherwise IP)
    identifier = None
    
    # Try to get user from auth header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            from backend.auth.dependency import get_current_physician
            physician = await get_current_physician(auth_header.split(" ")[1])
            if physician:
                identifier = f"user:{physician['username']}"
        except:
            pass
    
    # Fall back to IP address
    if not identifier:
        client_ip = request.client.host if request.client else "unknown"
        identifier = f"ip:{client_ip}"
    
    # Check rate limit
    rate_limiter = get_rate_limiter()
    allowed, limit_type, retry_after = rate_limiter.check_rate_limit(identifier)
    
    if not allowed:
        logger.warning(
            f"Rate limit exceeded for {identifier}: {limit_type} limit reached"
        )
        
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": "Rate limit exceeded",
                "limit_type": limit_type,
                "retry_after_seconds": retry_after,
                "message": f"Too many requests. Please try again in {retry_after} seconds."
            },
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(getattr(rate_limiter, f"requests_per_{limit_type}")),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(time.time() + retry_after))
            }
        )
    
    # Add rate limit headers to response
    response = await call_next(request)
    
    remaining = rate_limiter.get_remaining(identifier)
    response.headers["X-RateLimit-Limit-Minute"] = str(rate_limiter.requests_per_minute)
    response.headers["X-RateLimit-Remaining-Minute"] = str(remaining["minute"])
    response.headers["X-RateLimit-Limit-Hour"] = str(rate_limiter.requests_per_hour)
    response.headers["X-RateLimit-Remaining-Hour"] = str(remaining["hour"])
    response.headers["X-RateLimit-Limit-Day"] = str(rate_limiter.requests_per_day)
    response.headers["X-RateLimit-Remaining-Day"] = str(remaining["day"])
    
    return response


class RateLimitConfig:
    """Configuration for different rate limit tiers"""
    
    FREE_TIER = {
        "requests_per_minute": 10,
        "requests_per_hour": 100,
        "requests_per_day": 500
    }
    
    BASIC_TIER = {
        "requests_per_minute": 30,
        "requests_per_hour": 500,
        "requests_per_day": 2000
    }
    
    PROFESSIONAL_TIER = {
        "requests_per_minute": 60,
        "requests_per_hour": 1000,
        "requests_per_day": 10000
    }
    
    ENTERPRISE_TIER = {
        "requests_per_minute": 120,
        "requests_per_hour": 5000,
        "requests_per_day": 50000
    }

# Made with Bob
