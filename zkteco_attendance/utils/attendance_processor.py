# Copyright (c) 2024 Your Organization
# MIT License

"""
Attendance processing engine for ZKTeco integration.

Converts raw biometric logs into ERPNext Employee Checkin records.
Handles shift compatibility and duplicate prevention.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

import frappe
from frappe import _
from frappe.utils import now_datetime, get_datetime, add_minutes

from ..constants import LogProcessStatus
from ..exceptions import (
    EmployeeMappingNotFoundError,
    DuplicateCheckinError,
    ZKTecoBaseError,
)
from .employee_mapper import EmployeeMapper

logger = logging.getLogger(__name__)


class AttendanceProcessor:
    """
    Processes raw biometric attendance logs into Employee Checkins.
    
    Features:
    - Shift-aware processing
    - Duplicate prevention
    - Error handling and logging
    - Bulk processing support
    """

    def __init__(self) -> None:
        """Initialize the attendance processor."""
        self.mapper = EmployeeMapper()

    def process_device_logs(
        self,
        device: str,
        limit: Optional[int] = None
    ) -> tuple[int, int]:
        """
        Process all pending logs for a device.
        
        Args:
            device: Device name
            limit: Maximum logs to process
            
        Returns:
            Tuple of (processed_count, error_count)
        """
        filters = {
            "device": device,
            "processed": LogProcessStatus.PENDING
        }
        
        logs = frappe.get_all(
            "Biometric Attendance Log",
            filters=filters,
            fields=["name", "device_user_id", "device", "timestamp", "punch_type"],
            order_by="timestamp asc",
            limit=limit
        )
        
        processed_count = 0
        error_count = 0
        
        for log in logs:
            try:
                self._process_single_log(log)
                self._update_log_status(log["name"], LogProcessStatus.PROCESSED)
                processed_count += 1
            except Exception as e:
                self._update_log_status(
                    log["name"],
                    LogProcessStatus.FAILED,
                    str(e)[:500]
                )
                error_count += 1
                logger.error(
                    f"Failed to process log {log['name']}: {e}"
                )
        
        logger.info(
            f"Processed {device}: Success={processed_count}, Errors={error_count}"
        )
        return processed_count, error_count

    def process_single_log(self, log_name: str) -> None:
        """
        Process a single attendance log.
        
        Args:
            log_name: Name of the Biometric Attendance Log document
        """
        log = frappe.get_doc("Biometric Attendance Log", log_name)
        self._process_single_log({
            "name": log.name,
            "device_user_id": log.device_user_id,
            "device": log.device,
            "timestamp": log.timestamp,
            "punch_type": log.punch_type
        })
        self._update_log_status(log_name, LogProcessStatus.PROCESSED)

    def reprocess_logs_bulk(self, log_ids: list[str]) -> dict[str, int]:
        """
        Reprocess multiple logs (for error recovery).
        
        Args:
            log_ids: List of log document names
            
        Returns:
            Dictionary with processing statistics
        """
        stats = {
            "processed": 0,
            "failed": 0,
            "skipped": 0
        }
        
        for log_id in log_ids:
            try:
                # Reset status
                self._update_log_status(log_id, LogProcessStatus.REPROCESSED)
                
                # Get log data
                log = frappe.get_doc("Biometric Attendance Log", log_id)
                
                # Delete existing checkin if any
                existing_checkin = frappe.db.get_value(
                    "Employee Checkin",
                    {
                        "biometric_log": log_id
                    },
                    "name"
                )
                if existing_checkin:
                    frappe.delete_doc("Employee Checkin", existing_checkin, force=True)
                
                # Process the log
                self._process_single_log({
                    "name": log.name,
                    "device_user_id": log.device_user_id,
                    "device": log.device,
                    "timestamp": log.timestamp,
                    "punch_type": log.punch_type
                })
                
                self._update_log_status(log_id, LogProcessStatus.PROCESSED)
                stats["processed"] += 1
                
            except EmployeeMappingNotFoundError:
                self._update_log_status(
                    log_id,
                    LogProcessStatus.SKIPPED,
                    "No employee mapping found"
                )
                stats["skipped"] += 1
            except Exception as e:
                self._update_log_status(log_id, LogProcessStatus.FAILED, str(e)[:500])
                stats["failed"] += 1
                logger.error(f"Reprocess failed for {log_id}: {e}")
        
        return stats

    def _process_single_log(self, log: dict[str, Any]) -> str:
        """
        Internal method to process a single log entry.
        
        Args:
            log: Log data dictionary
            
        Returns:
            Name of created Employee Checkin
            
        Raises:
            EmployeeMappingNotFoundError: If no mapping exists
            DuplicateCheckinError: If duplicate checkin detected
        """
        # Find employee mapping
        employee = self.mapper.get_mapping(
            device_user_id=log["device_user_id"],
            device=log["device"]
        )
        
        if not employee:
            # Update log with missing mapping
            self._update_log_employee(log["name"], None, "No mapping found")
            raise EmployeeMappingNotFoundError(
                device_user_id=log["device_user_id"],
                device=log["device"]
            )
        
        # Check for duplicates
        timestamp = get_datetime(log["timestamp"])
        if self._is_duplicate_checkin(employee, timestamp):
            self._update_log_status(
                log["name"],
                LogProcessStatus.SKIPPED,
                "Duplicate checkin"
            )
            raise DuplicateCheckinError(
                employee=employee,
                timestamp=str(timestamp)
            )
        
        # Determine log type
        log_type = self._determine_log_type(employee, timestamp, log["punch_type"])
        
        # Create Employee Checkin
        checkin = frappe.get_doc({
            "doctype": "Employee Checkin",
            "employee": employee,
            "time": timestamp,
            "log_type": log_type,
            "device_id": log["device"],
            "biometric_device": log["device"],
            "device_user_id": log["device_user_id"],
            "biometric_log": log["name"],
        })
        checkin.insert(ignore_permissions=True)
        
        # Update log with employee info
        employee_name = frappe.db.get_value("Employee", employee, "employee_name")
        self._update_log_employee(log["name"], employee, employee_name=employee_name)
        
        logger.debug(
            f"Created checkin {checkin.name} for {employee} at {timestamp}"
        )
        
        return checkin.name

    def _determine_log_type(
        self,
        employee: str,
        timestamp: datetime,
        device_punch_type: str
    ) -> str:
        """
        Determine if the punch is IN or OUT based on context.
        
        Uses multiple strategies:
        1. Device punch type if known
        2. Previous checkin logic
        3. Shift timing logic
        
        Args:
            employee: Employee ID
            timestamp: Punch timestamp
            device_punch_type: Punch type from device (IN/OUT/Unknown)
            
        Returns:
            "IN" or "OUT"
        """
        # If device clearly indicates type
        if device_punch_type in ["IN", "OUT"]:
            return device_punch_type
        
        # For unknown types, use previous checkin logic
        # Get the most recent checkin for this employee
        last_checkin = frappe.db.get_value(
            "Employee Checkin",
            {"employee": employee, "time": ["<", timestamp]},
            ["name", "time", "log_type"],
            order_by="time desc"
        )
        
        if not last_checkin:
            # First checkin of the day/session is typically IN
            return "IN"
        
        last_time = get_datetime(last_checkin[1])
        last_type = last_checkin[2]
        
        # If last was IN, this should be OUT
        if last_type == "IN":
            return "OUT"
        
        # If last was OUT, this should be IN
        if last_type == "OUT":
            return "IN"
        
        # Default based on time gap
        time_gap = (timestamp - last_time).total_seconds() / 3600
        return "OUT" if time_gap < 12 else "IN"

    def _is_duplicate_checkin(
        self,
        employee: str,
        timestamp: datetime,
        tolerance_minutes: int = 2
    ) -> bool:
        """
        Check if a duplicate checkin exists.
        
        Args:
            employee: Employee ID
            timestamp: Punch timestamp
            tolerance_minutes: Time tolerance for duplicate detection
            
        Returns:
            True if duplicate exists
        """
        from_time = add_minutes(timestamp, -tolerance_minutes)
        to_time = add_minutes(timestamp, tolerance_minutes)
        
        return bool(
            frappe.db.exists(
                "Employee Checkin",
                {
                    "employee": employee,
                    "time": ["between", [from_time, to_time]]
                }
            )
        )

    def _update_log_status(
        self,
        log_name: str,
        status: str,
        error_message: Optional[str] = None
    ) -> None:
        """Update the processing status of a log."""
        updates = {"processed": status}
        if error_message:
            updates["error_message"] = error_message
        
        frappe.db.set_value("Biometric Attendance Log", log_name, updates)

    def _update_log_employee(
        self,
        log_name: str,
        employee: Optional[str],
        error_message: Optional[str] = None,
        employee_name: Optional[str] = None
    ) -> None:
        """Update the employee field on a log."""
        updates = {
            "employee": employee,
            "employee_id": employee
        }
        if employee_name:
            updates["employee_name"] = employee_name
        if error_message:
            updates["error_message"] = error_message
            updates["processed"] = LogProcessStatus.FAILED
        
        frappe.db.set_value("Biometric Attendance Log", log_name, updates)


# Background job wrapper
def reprocess_logs_bulk(log_ids: list[str]) -> dict[str, int]:
    """Wrapper for bulk reprocessing background job."""
    processor = AttendanceProcessor()
    return processor.reprocess_logs_bulk(log_ids)
