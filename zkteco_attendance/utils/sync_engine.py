# Copyright (c) 2026 Eslam Zedan
# MIT License

"""
Synchronization engine for ZKTeco attendance data.

Handles the complete sync workflow:
1. Connect to device
2. Download attendance logs
3. Store raw logs
4. Trigger attendance processing
5. Update device status
6. Log sync results
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

import frappe
from frappe import _
from frappe.utils import now_datetime, now, add_to_date

from ..constants import (
    SyncStatus,
    DeviceStatus,
    BATCH_SIZE,
    HISTORICAL_DAYS_LIMIT,
)
from ..exceptions import (
    DeviceConnectionError,
    DeviceTimeoutError,
    SyncError,
    ZKTecoBaseError,
)
from .device_communicator import DeviceCommunicator
from .attendance_processor import AttendanceProcessor

logger = logging.getLogger(__name__)


class SyncEngine:
    """
    Main synchronization engine for ZKTeco devices.
    
    Coordinates the complete sync workflow and ensures
    fault-tolerant, auditable operations.
    """

    def __init__(self) -> None:
        """Initialize the sync engine."""
        self.processor = AttendanceProcessor()

    def sync_single_device(
        self,
        device_name: str,
        from_timestamp: Optional[datetime] = None
    ) -> str:
        """
        Synchronize attendance data from a single device.
        
        Args:
            device_name: Name of the Biometric Device document
            from_timestamp: Optional start timestamp for incremental sync
            
        Returns:
            Name of the created Biometric Sync Log document
        """
        sync_log = None
        
        try:
            # Get device document
            device = frappe.get_doc("Biometric Device", device_name)
            
            # Create sync log
            sync_log = self._create_sync_log(device_name)
            
            # Update device status
            self._update_device_status(device_name, DeviceStatus.ACTIVE, "Syncing...")
            
            # Get last sync time if not specified
            if from_timestamp is None and device.last_sync_time:
                from_timestamp = frappe.utils.get_datetime(device.last_sync_time) - timedelta(minutes=5)
            
            # Initialize communicator
            communicator = DeviceCommunicator(device)
            
            # Download logs
            logger.info(f"Starting log download from {device.device_ip}")
            raw_logs = communicator.get_attendance_logs(from_timestamp)
            
            sync_log.db_set("records_downloaded", len(raw_logs))
            
            if not raw_logs:
                sync_log.db_set("status", SyncStatus.COMPLETED)
                sync_log.db_set("sync_end", now_datetime())
                sync_log.save(ignore_permissions=True)
                self._update_device_status(device_name, DeviceStatus.ACTIVE, "No new logs")
                self._update_last_sync_time(device_name)
                return sync_log.name
            
            # Store raw logs in batches
            stored_count = self._store_raw_logs(device_name, raw_logs)
            sync_log.db_set("records_stored", stored_count)
            
            # Process logs into Employee Checkins
            processed_count, error_count = self.processor.process_device_logs(device_name)
            
            sync_log.db_set("records_imported", processed_count)
            sync_log.db_set("errors", error_count)
            sync_log.db_set("status", SyncStatus.COMPLETED)
            sync_log.db_set("sync_end", now_datetime())
            sync_log.save(ignore_permissions=True)
            
            # Update device status
            self._update_device_status(device_name, DeviceStatus.ACTIVE)
            self._update_last_sync_time(device_name)
            
            logger.info(
                f"Sync completed for {device_name}: "
                f"Downloaded={len(raw_logs)}, Stored={stored_count}, "
                f"Processed={processed_count}, Errors={error_count}"
            )
            
            return sync_log.name
            
        except ZKTecoBaseError as e:
            logger.error(f"Sync failed for {device_name}: {e.message}")
            self._handle_sync_error(sync_log, device_name, e)
            raise
            
        except Exception as e:
            logger.exception(f"Unexpected error during sync for {device_name}")
            error = SyncError(device=device_name, reason=str(e))
            self._handle_sync_error(sync_log, device_name, error)
            raise

    def sync_all_devices(self) -> dict[str, Any]:
        """
        Synchronize all enabled devices.
        
        Returns:
            Dictionary with sync results for each device
        """
        devices = frappe.get_all(
            "Biometric Device",
            filters={"sync_enabled": 1, "status": ["!=", "Maintenance"]},
            fields=["name", "device_name", "device_ip"]
        )
        
        results = []
        
        for device in devices:
            try:
                sync_log_name = self.sync_single_device(device.name)
                results.append({
                    "device": device.name,
                    "status": "success",
                    "sync_log": sync_log_name
                })
            except Exception as e:
                results.append({
                    "device": device.name,
                    "status": "failed",
                    "error": str(e)
                })
        
        return {
            "total_devices": len(devices),
            "successful": len([r for r in results if r["status"] == "success"]),
            "failed": len([r for r in results if r["status"] == "failed"]),
            "results": results
        }

    def sync_historical_data(
        self,
        device_name: str,
        from_date: str,
        to_date: str
    ) -> str:
        """
        Sync historical attendance data for a date range.
        
        Args:
            device_name: Name of the Biometric Device
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
            
        Returns:
            Name of the created Biometric Sync Log document
        """
        # Validate date range
        from_dt = frappe.utils.get_datetime(from_date)
        to_dt = frappe.utils.get_datetime(to_date)
        
        if to_dt < from_dt:
            frappe.throw(_("End date must be after start date"))
        
        if (to_dt - from_dt).days > HISTORICAL_DAYS_LIMIT:
            frappe.throw(
                _("Date range cannot exceed {0} days").format(HISTORICAL_DAYS_LIMIT)
            )
        
        return self.sync_single_device(device_name, from_timestamp=from_dt)

    def _create_sync_log(self, device_name: str) -> Any:
        """Create a new Biometric Sync Log document."""
        sync_log = frappe.get_doc({
            "doctype": "Biometric Sync Log",
            "device": device_name,
            "sync_start": now_datetime(),
            "status": SyncStatus.IN_PROGRESS,
            "records_downloaded": 0,
            "records_stored": 0,
            "records_imported": 0,
            "errors": 0,
        })
        sync_log.insert(ignore_permissions=True)
        return sync_log

    def _store_raw_logs(
        self,
        device_name: str,
        logs: list[dict[str, Any]]
    ) -> int:
        """
        Store raw attendance logs in the database.
        
        Args:
            device_name: Device name
            logs: List of log dictionaries from device
            
        Returns:
            Number of logs stored
        """
        stored_count = 0
        batch = []
        
        for log in logs:
            # Check for duplicates
            if self._is_duplicate_log(device_name, log["device_user_id"], log["timestamp"]):
                continue
            
            batch.append({
                "doctype": "Biometric Attendance Log",
                "device_user_id": log["device_user_id"],
                "device": device_name,
                "timestamp": log["timestamp"],
                "punch_type": log["punch_type"],
                "status_code": log.get("status_code", 0),
                "verified": log.get("verified", 0),
                "work_code": log.get("work_code", 0),
                "sync_date": now_datetime(),
                "processed": "Pending",
            })
            
            if len(batch) >= BATCH_SIZE:
                stored_count += self._insert_batch(batch)
                batch = []
        
        # Insert remaining logs
        if batch:
            stored_count += self._insert_batch(batch)
        
        return stored_count

    def _insert_batch(self, batch: list[dict[str, Any]]) -> int:
        """Insert a batch of log records."""
        try:
            for doc_data in batch:
                doc = frappe.new_doc(doc_data.pop("doctype"))
                doc.update(doc_data)
                doc.insert(ignore_permissions=True)
            return len(batch)
        except Exception as e:
            logger.error(f"Batch insert failed: {e}")
            # Try inserting one by one for error isolation
            inserted = 0
            for doc_data in batch:
                try:
                    doc = frappe.new_doc(doc_data.pop("doctype"))
                    doc.update(doc_data)
                    doc.insert(ignore_permissions=True)
                    inserted += 1
                except Exception as single_error:
                    logger.error(
                        f"Single insert failed: {single_error}"
                    )
            return inserted

    def _is_duplicate_log(
        self,
        device_name: str,
        device_user_id: str,
        timestamp: datetime
    ) -> bool:
        """Check if a log already exists."""
        return bool(
            frappe.db.exists(
                "Biometric Attendance Log",
                {
                    "device": device_name,
                    "device_user_id": device_user_id,
                    "timestamp": frappe.utils.get_datetime(timestamp)
                }
            )
        )

    def _update_device_status(
        self,
        device_name: str,
        status: str,
        remarks: str = ""
    ) -> None:
        """Update device status in database."""
        try:
            frappe.db.set_value(
                "Biometric Device",
                device_name,
                {
                    "status": status,
                    "remarks": remarks if remarks else None
                }
            )
        except Exception as e:
            logger.error(f"Failed to update device status: {e}")

    def _update_last_sync_time(self, device_name: str) -> None:
        """Update last sync timestamp for device."""
        try:
            frappe.db.set_value(
                "Biometric Device",
                device_name,
                "last_sync_time",
                now_datetime()
            )
        except Exception as e:
            logger.error(f"Failed to update last sync time: {e}")

    def _handle_sync_error(
        self,
        sync_log: Any,
        device_name: str,
        error: ZKTecoBaseError
    ) -> None:
        """Handle sync errors and update records accordingly."""
        try:
            if sync_log:
                sync_log.db_set("status", SyncStatus.FAILED)
                sync_log.db_set("sync_end", now_datetime())
                sync_log.db_set("error_message", error.message)
                sync_log.save(ignore_permissions=True)
            
            self._update_device_status(
                device_name,
                DeviceStatus.ERROR,
                error.message[:140]
            )
        except Exception as e:
            logger.error(f"Failed to handle sync error: {e}")


# Convenience function for background job
def sync_single_device(device_name: str) -> str:
    """Wrapper function for background job execution."""
    engine = SyncEngine()
    return engine.sync_single_device(device_name)


def sync_historical_data(
    device_name: str,
    from_date: str,
    to_date: str
) -> str:
    """Wrapper function for historical sync background job."""
    engine = SyncEngine()
    return engine.sync_historical_data(device_name, from_date, to_date)
