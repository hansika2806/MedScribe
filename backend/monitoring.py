"""
Basic monitoring and metrics tracking
Tracks pipeline performance and outcomes
"""
import logging
import json
from pathlib import Path
from typing import Dict, Any
from datetime import datetime
import threading

logger = logging.getLogger(__name__)

# Metrics file path
METRICS_FILE = Path("data/metrics.json")

# Thread lock for concurrent access
_metrics_lock = threading.Lock()


class MetricsTracker:
    """Track pipeline metrics"""
    
    def __init__(self):
        self.metrics_file = METRICS_FILE
        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)
        self._load_metrics()
    
    def _load_metrics(self):
        """Load metrics from file or initialize"""
        try:
            if self.metrics_file.exists():
                with open(self.metrics_file, 'r') as f:
                    self.metrics = json.load(f)
                logger.info("Loaded existing metrics")
            else:
                self.metrics = self._initialize_metrics()
                self._save_metrics()
                logger.info("Initialized new metrics")
        except Exception as e:
            logger.error(f"Failed to load metrics: {e}")
            self.metrics = self._initialize_metrics()
    
    def _initialize_metrics(self) -> Dict[str, Any]:
        """Initialize empty metrics structure"""
        return {
            "total_consultations": 0,
            "successful_completions": 0,
            "pipeline_failures": {},
            "average_processing_time": 0.0,
            "diarization_method_used": {
                "pyannote": 0,
                "speechbrain": 0,
                "fallback": 0
            },
            "confidence_distribution": {
                "above_085": 0,
                "between_070_085": 0,
                "below_070": 0
            },
            "safety_flags_raised": 0,
            "qa_flags_raised": 0,
            "review_type_distribution": {
                "standard_approval": 0,
                "low_confidence": 0,
                "urgent_safety": 0
            },
            "last_updated": datetime.utcnow().isoformat()
        }
    
    def _save_metrics(self):
        """Save metrics to file"""
        try:
            with open(self.metrics_file, 'w') as f:
                json.dump(self.metrics, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")
    
    def record_consultation(
        self,
        success: bool,
        processing_time: float,
        diarization_method: str,
        confidence: float,
        safety_flags: int,
        qa_flags: int,
        review_type: str,
        error: str | None = None
    ):
        """
        Record metrics for a consultation
        
        Args:
            success: Whether consultation completed successfully
            processing_time: Time taken in seconds
            diarization_method: Method used (pyannote/speechbrain/fallback)
            confidence: Overall confidence score
            safety_flags: Number of safety flags raised
            qa_flags: Number of QA flags raised
            review_type: Type of review required
            error: Error message if failed
        """
        with _metrics_lock:
            try:
                # Total consultations
                self.metrics["total_consultations"] += 1
                
                if success:
                    self.metrics["successful_completions"] += 1
                    
                    # Update average processing time
                    total = self.metrics["total_consultations"]
                    current_avg = self.metrics["average_processing_time"]
                    self.metrics["average_processing_time"] = (
                        (current_avg * (total - 1) + processing_time) / total
                    )
                    
                    # Diarization method
                    if diarization_method in self.metrics["diarization_method_used"]:
                        self.metrics["diarization_method_used"][diarization_method] += 1
                    
                    # Confidence distribution
                    if confidence >= 0.85:
                        self.metrics["confidence_distribution"]["above_085"] += 1
                    elif confidence >= 0.70:
                        self.metrics["confidence_distribution"]["between_070_085"] += 1
                    else:
                        self.metrics["confidence_distribution"]["below_070"] += 1
                    
                    # Safety and QA flags
                    if safety_flags > 0:
                        self.metrics["safety_flags_raised"] += safety_flags
                    if qa_flags > 0:
                        self.metrics["qa_flags_raised"] += qa_flags
                    
                    # Review type
                    if review_type in self.metrics["review_type_distribution"]:
                        self.metrics["review_type_distribution"][review_type] += 1
                
                else:
                    # Record failure
                    error_type = error if error else "unknown_error"
                    if error_type not in self.metrics["pipeline_failures"]:
                        self.metrics["pipeline_failures"][error_type] = 0
                    self.metrics["pipeline_failures"][error_type] += 1
                
                # Update timestamp
                self.metrics["last_updated"] = datetime.utcnow().isoformat()
                
                # Save to file
                self._save_metrics()
                
                logger.info(f"Recorded consultation metrics: success={success}, time={processing_time:.2f}s")
                
            except Exception as e:
                logger.error(f"Failed to record metrics: {e}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        with _metrics_lock:
            return self.metrics.copy()
    
    def reset_metrics(self):
        """Reset all metrics"""
        with _metrics_lock:
            self.metrics = self._initialize_metrics()
            self._save_metrics()
            logger.info("Metrics reset")


# Global tracker instance
_tracker = None


def get_metrics_tracker() -> MetricsTracker:
    """Get or create metrics tracker instance"""
    global _tracker
    if _tracker is None:
        _tracker = MetricsTracker()
    return _tracker


def record_consultation_metrics(
    success: bool,
    processing_time: float,
    diarization_method: str = "fallback",
    confidence: float = 0.0,
    safety_flags: int = 0,
    qa_flags: int = 0,
    review_type: str = "standard_approval",
    error: str | None = None
):
    """
    Convenience function to record consultation metrics
    """
    tracker = get_metrics_tracker()
    tracker.record_consultation(
        success=success,
        processing_time=processing_time,
        diarization_method=diarization_method,
        confidence=confidence,
        safety_flags=safety_flags,
        qa_flags=qa_flags,
        review_type=review_type,
        error=error
    )


def get_current_metrics() -> Dict[str, Any]:
    """
    Convenience function to get current metrics
    """
    tracker = get_metrics_tracker()
    return tracker.get_metrics()


# Made with Bob