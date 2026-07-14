# Copyright (c) 2024 Your Organization
# MIT License

"""
Scheduled synchronization tasks.
"""

import logging
import frappe
from frappe.utils import add_days, now_datetime

from ..utils.sync_engine import SyncEngine
from ..constants import SYNC_LOG_RETENTION_DAYS

logger = logging.getLogger(__name__)


def sync_all_devices_5min():
    """
    Scheduled task: Sync all enabled devices every 5 minutes.
    
    Only syncs devices with sync frequency set to 'Every 5 Minutes'.
    """
    devices = frappe.get_all(
        "Biometric Device",
        filters={
            "sync_enabled": 1,
            "status": "Active",
            "sync_frequency": "Every 5 Minutes"
        },
        pluck="name"
    )
    
    if not devices:
        return
    
    logger.info(f"5-min sync: Processing {len(devices)} devices")
    
    engine = SyncEngine()
    for device_name in devices:
        try:
            engine.sync_single_device(device_name)
        except Exception as e:
            logger.error(f"5-min sync failed for {device_name}: {e}")


def sync_all_devices_15min():
    """
    Scheduled task: Sync all enabled devices every 15 minutes.
    
    Only syncs devices with sync frequency set to 'Every 15 Minutes' or higher.
    """
    devices = frappe.get_all(
        "Biometric Device",
        filters={
            "sync_enabled": 1,
            "status": "Active",
            "sync_frequency": ["in", [
                "Every 15 Minutes",
                "Every 30 Minutes",
                "Every Hour"
            ]]
        },
        pluck="name"
    )
    
    if not devices:
        return
    
    logger.info(f"15-min sync: Processing {len(devices)} devices")
    
    engine = SyncEngine()
    for device_name in devices:
        try:
            engine.sync_single_device(device_name)
        except Exception as e:
            logger.error(f"15-min sync failed for {device_name}: {e}")


def cleanup_old_sync_logs():
    """
    Scheduled task: Clean up old sync logs.
    
    Removes sync logs older than retention period.
    """
    cutoff_date = add_days(now_datetime(), -SYNC_LOG_RETENTION_DAYS)
    
    try:
        deleted = frappe.db.sql("""
            DELETE FROM `tabBiometric Sync Log`
            WHERE creation < %s
        """, cutoff_date)
        
        logger.info(f"Cleaned up {deleted} old sync logs")
    except Exception as e:
        logger.error(f"Failed to cleanup sync logs: {e}")
