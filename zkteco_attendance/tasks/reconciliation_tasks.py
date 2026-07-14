# Copyright (c) 2024 Your Organization
# MIT License

"""
Daily reconciliation and maintenance tasks.
"""

import logging
from datetime import datetime, timedelta

import frappe
from frappe import _
from frappe.utils import now_datetime, today, add_days, get_datetime

from ..utils.sync_engine import SyncEngine
from ..utils.attendance_processor import AttendanceProcessor
from ..constants import LogProcessStatus, DeviceStatus

logger = logging.getLogger(__name__)


def daily_reconciliation():
    """
    Daily reconciliation task.
    
    Performs:
    1. Reprocess failed logs
    2. Check for offline devices
    3. Generate reconciliation report
    4. Send alerts if needed
    """
    logger.info("Starting daily reconciliation")
    
    try:
        # 1. Reprocess failed logs from yesterday
        reprocess_failed_logs()
        
        # 2. Check device status
        check_device_health()
        
        # 3. Generate summary
        generate_daily_summary()
        
        logger.info("Daily reconciliation completed")
        
    except Exception as e:
        logger.exception(f"Daily reconciliation failed: {e}")
        frappe.log_error(
            title="Daily Reconciliation Failed",
            message=str(e)
        )


def reprocess_failed_logs():
    """Reprocess logs that failed yesterday."""
    yesterday = add_days(today(), -1)
    
    failed_logs = frappe.get_all(
        "Biometric Attendance Log",
        filters={
            "processed": LogProcessStatus.FAILED,
            "timestamp": ["between", [yesterday, today()]]
        },
        pluck="name"
    )
    
    if not failed_logs:
        logger.info("No failed logs to reprocess")
        return
    
    logger.info(f"Reprocessing {len(failed_logs)} failed logs")
    
    processor = AttendanceProcessor()
    stats = processor.reprocess_logs_bulk(failed_logs)
    
    logger.info(
        f"Reprocessing complete: "
        f"Processed={stats['processed']}, "
        f"Failed={stats['failed']}, "
        f"Skipped={stats['skipped']}"
    )


def check_device_health():
    """Check health of all devices and update status."""
    devices = frappe.get_all(
        "Biometric Device",
        filters={"sync_enabled": 1},
        fields=["name", "device_ip", "last_sync_time", "status"]
    )
    
    offline_threshold = timedelta(hours=2)
    now_dt = now_datetime()
    
    for device in devices:
        if device.status == "Maintenance":
            continue
        
        if device.last_sync_time:
            last_sync = get_datetime(device.last_sync_time)
            if (now_dt - last_sync) > offline_threshold:
                frappe.db.set_value(
                    "Biometric Device",
                    device.name,
                    "status",
                    DeviceStatus.OFFLINE
                )
                logger.warning(f"Device {device.name} marked as offline")
        else:
            # Never synced
            if device.status == "Active":
                frappe.db.set_value(
                    "Biometric Device",
                    device.name,
                    "status",
                    DeviceStatus.OFFLINE
                )


def generate_daily_summary():
    """Generate and log daily summary."""
    yesterday = add_days(today(), -1)
    
    # Get summary stats
    total_logs = frappe.db.count(
        "Biometric Attendance Log",
        {"timestamp": ["between", [yesterday, today()]]}
    )
    
    processed_logs = frappe.db.count(
        "Biometric Attendance Log",
        {
            "timestamp": ["between", [yesterday, today()]],
            "processed": LogProcessStatus.PROCESSED
        }
    )
    
    failed_logs = frappe.db.count(
        "Biometric Attendance Log",
        {
            "timestamp": ["between", [yesterday, today()]],
            "processed": LogProcessStatus.FAILED
        }
    )
    
    checkins_created = frappe.db.count(
        "Employee Checkin",
        {"time": ["between", [yesterday, today()]]}
    )
    
    summary = f"""
    Daily Attendance Summary ({yesterday})
    =====================================
    Total Logs: {total_logs}
    Processed: {processed_logs}
    Failed: {failed_logs}
    Checkins Created: {checkins_created}
    """
    
    logger.info(summary)
    
    # Create a log entry
    frappe.get_doc({
        "doctype": "Biometric Sync Log",
        "device": "SYSTEM",
        "sync_start": now_datetime(),
        "sync_end": now_datetime(),
        "status": "Completed",
        "records_downloaded": total_logs,
        "records_imported": checkins_created,
        "errors": failed_logs,
        "error_message": f"Daily Summary: {processed_logs}/{total_logs} processed"
    }).insert(ignore_permissions=True)
