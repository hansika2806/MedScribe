"""Structured performance logging for MedScribe pipeline nodes."""

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class NodePerformanceLogger:
    def __init__(self):
        self.log_file = Path("data/performance_logs.jsonl")
        self.log_file.parent.mkdir(exist_ok=True)

    def log_node(
        self,
        session_id: str,
        node_name: str,
        status: str,
        duration_seconds: float,
        input_size: int = 0,
        output_size: int = 0,
        error: str = None,
        metadata: dict = None,
    ):
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "session_id": session_id,
            "node": node_name,
            "status": status,
            "duration_seconds": round(duration_seconds, 3),
            "input_size": input_size,
            "output_size": output_size,
            "error": error,
            "metadata": metadata or {},
        }

        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    def log_session(
        self,
        session_id: str,
        total_duration: float,
        review_type: str,
        diarization_method: str,
        ocr_method: str,
        node_count: int,
        success: bool,
    ):
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "session_id": session_id,
            "type": "session_summary",
            "total_duration_seconds": round(total_duration, 3),
            "review_type": review_type,
            "diarization_method": diarization_method,
            "ocr_method": ocr_method,
            "nodes_executed": node_count,
            "success": success,
        }

        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    def get_session_stats(self, session_id: str) -> list:
        records = []
        if self.log_file.exists():
            with open(self.log_file, encoding="utf-8") as f:
                for line in f:
                    try:
                        record = json.loads(line)
                        if record.get("session_id") == session_id:
                            records.append(record)
                    except Exception:
                        logger.debug("Skipping malformed performance log line")
                        continue
        return records


_perf_logger = None


def get_performance_logger() -> NodePerformanceLogger:
    global _perf_logger
    if _perf_logger is None:
        _perf_logger = NodePerformanceLogger()
    return _perf_logger
