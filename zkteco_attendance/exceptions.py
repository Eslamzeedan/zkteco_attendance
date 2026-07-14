# Copyright (c) 2026 Eslam Zedan
# MIT License

"""
Custom exceptions for ZKTeco Attendance Integration.
"""

from typing import Optional, Any
from .constants import ErrorCodes


class ZKTecoBaseError(Exception):
    """Base exception for all ZKTeco-related errors."""

    def __init__(
        self,
        message: str,
        error_code: ErrorCodes = ErrorCodes.UNKNOWN_ERROR,
        details: Optional[dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error": True,
            "error_code": self.error_code.value,
            "message": self.message,
            "details": self.details,
        }


class DeviceConnectionError(ZKTecoBaseError):
    """Raised when connection to device fails."""

    def __init__(
        self,
        device_ip: str,
        device_port: int,
        reason: str,
        details: Optional[dict[str, Any]] = None
    ):
        super().__init__(
            message=f"Failed to connect to device {device_ip}:{device_port} - {reason}",
            error_code=ErrorCodes.CONNECTION_FAILED,
            details={"device_ip": device_ip, "device_port": device_port, **(details or {})}
        )


class DeviceTimeoutError(ZKTecoBaseError):
    """Raised when device operation times out."""

    def __init__(
        self,
        device_ip: str,
        operation: str,
        timeout_seconds: int,
        details: Optional[dict[str, Any]] = None
    ):
        super().__init__(
            message=f"Device {device_ip} operation '{operation}' timed out after {timeout_seconds}s",
            error_code=ErrorCodes.TIMEOUT,
            details={"device_ip": device_ip, "operation": operation, "timeout": timeout_seconds, **(details or {})}
        )


class DeviceAuthenticationError(ZKTecoBaseError):
    """Raised when device authentication fails."""

    def __init__(
        self,
        device_ip: str,
        details: Optional[dict[str, Any]] = None
    ):
        super().__init__(
            message=f"Authentication failed for device {device_ip}",
            error_code=ErrorCodes.AUTH_FAILED,
            details={"device_ip": device_ip, **(details or {})}
        )


class DeviceCommunicationError(ZKTecoBaseError):
    """Raised when there's a communication error with the device."""

    def __init__(
        self,
        device_ip: str,
        operation: str,
        reason: str,
        details: Optional[dict[str, Any]] = None
    ):
        super().__init__(
            message=f"Communication error with device {device_ip} during '{operation}': {reason}",
            error_code=ErrorCodes.DEVICE_ERROR,
            details={"device_ip": device_ip, "operation": operation, **(details or {})}
        )


class EmployeeMappingNotFoundError(ZKTecoBaseError):
    """Raised when employee mapping is not found."""

    def __init__(
        self,
        device_user_id: str,
        device: str,
        details: Optional[dict[str, Any]] = None
    ):
        super().__init__(
            message=f"No mapping found for device user ID '{device_user_id}' on device '{device}'",
            error_code=ErrorCodes.MAPPING_NOT_FOUND,
            details={"device_user_id": device_user_id, "device": device, **(details or {})}
        )


class DuplicateCheckinError(ZKTecoBaseError):
    """Raised when a duplicate check-in is detected."""

    def __init__(
        self,
        employee: str,
        timestamp: str,
        details: Optional[dict[str, Any]] = None
    ):
        super().__init__(
            message=f"Duplicate check-in detected for employee '{employee}' at '{timestamp}'",
            error_code=ErrorCodes.DUPLICATE_ENTRY,
            details={"employee": employee, "timestamp": timestamp, **(details or {})}
        )


class InvalidDataError(ZKTecoBaseError):
    """Raised when invalid data is received from device."""

    def __init__(
        self,
        data: Any,
        reason: str,
        details: Optional[dict[str, Any]] = None
    ):
        super().__init__(
            message=f"Invalid data received: {reason}",
            error_code=ErrorCodes.INVALID_DATA,
            details={"data_sample": str(data)[:100], **(details or {})}
        )


class SyncError(ZKTecoBaseError):
    """Raised when sync operation fails."""

    def __init__(
        self,
        device: str,
        reason: str,
        details: Optional[dict[str, Any]] = None
    ):
        super().__init__(
            message=f"Sync failed for device '{device}': {reason}",
            error_code=ErrorCodes.PROCESSING_ERROR,
            details={"device": device, **(details or {})}
        )
