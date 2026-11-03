"""One JSON object per log line. Cloud Run sends stdout to Cloud Logging, which
reads "severity" and "message" and keeps every other field searchable: that is
how the dashboard and the cost report count requests per version."""

import json
import logging
import sys
import time


class JsonFormatter(logging.Formatter):
    def format(self, record):
        line = {"severity": record.levelname, "message": record.getMessage(), "time": time.time()}
        line.update(getattr(record, "fields", {}))
        return json.dumps(line)


class StdoutHandler(logging.StreamHandler):
    """Always writes to the current sys.stdout (so test tools can capture it)."""

    def emit(self, record):
        self.stream = sys.stdout
        super().emit(record)


def get_logger(name):
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = StdoutHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger
