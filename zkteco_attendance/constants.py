# Copyright (c) 2024 Eslam Zedan
# MIT License

"""
Application constants for ZKTeco Attendance Integration.
"""

from enum import Enum
from typing import Final


class SyncStatus(str, Enum):
    """Sync operation status values."""
    PENDING = "Pending"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    FAILED = "Failed"
    PARTIALLY_COMPLETED = "Partially Completed"
    CANCELLED = "Cancelled"


class DeviceStatus(str, Enum):
    """Biometric device status values."""
    ACTIVE = "Active"
    INACTIVE = "Inactive"
    OFFLINE = "Offline"
    ERROR = "Error"
    MAINTENANCE = "Maintenance"


class PunchType(str, Enum):
    """Punch type classification."""
    CHECK_IN = "IN"
    CHECK_OUT = "OUT"
    UNKNOWN = "Unknown"


class LogProcessStatus(str, Enum):
    """Attendance log processing status."""
    PENDING = "Pending"
    PROCESSED = "Processed"
    FAILED = "Failed"
    SKIPPED = "Skipped"
    REPROCESSED = "Reprocessed"


class SyncFrequency(str, Enum):
    """Configurable sync frequencies."""
    EVERY_5_MIN = "Every 5 Minutes"
    EVERY_15_MIN = "Every 15 Minutes"
    EVERY_30_MIN = "Every 30 Minutes"
    EVERY_HOUR = "Every Hour"
    MANUAL_ONLY = "Manual Only"


class ErrorCodes(str, Enum):
    """Standardized error codes."""
    CONNECTION_FAILED = "E001"
    AUTH_FAILED = "E002"
    TIMEOUT = "E003"
    NETWORK_ERROR = "E004"
    DEVICE_ERROR = "E005"
    INVALID_DATA = "E006"
    MAPPING_NOT_FOUND = "E007"
    DUPLICATE_ENTRY = "E008"
    PROCESSING_ERROR = "E009"
    UNKNOWN_ERROR = "E999"


# Connection Constants
DEFAULT_PORT: Final[int] = 4370
CONNECTION_TIMEOUT: Final[int] = 10
READ_TIMEOUT: Final[int] = 30
MAX_RETRIES: Final[int] = 3
RETRY_DELAY: Final[int] = 5

# Sync Constants
BATCH_SIZE: Final[int] = 500
HISTORICAL_DAYS_LIMIT: Final[int] = 90
SYNC_LOG_RETENTION_DAYS: Final[int] = 30

# Auto-Mapping Constants
AUTO_MAP_THRESHOLD: Final[float] = 0.85
MIN_MATCH_SCORE: Final[int] = 70

# Dashboard Constants
DASHBOARD_REFRESH_INTERVAL: Final[int] = 60  # seconds
