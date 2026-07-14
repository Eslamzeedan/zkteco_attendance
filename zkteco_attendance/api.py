# Copyright (c) 2026 Eslam Zedan
# MIT License

"""
REST API endpoints for ZKTeco Attendance Integration.

All endpoints require System Manager or ZKTeco Manager role.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime
from typing import Any

from .utils.device_communicator import DeviceCommunicator
from .utils.sync_engine import SyncEngine
from .utils.attendance_processor import AttendanceProcessor
from .exceptions import (
    DeviceConnectionError,
    DeviceTimeoutError,
    ZKTecoBaseError,
)


@frappe.whitelist()
def test_device_connection(device_name: str) -> dict[str, Any]:
    """
    Test connection to a biometric device.

    Args:
        device_name: Name of the Biometric Device document

    Returns:
        Dictionary with connection test results

    Raises:
        frappe.PermissionError: If user lacks required permissions
    """
    frappe.only_for("System Manager", "ZKTeco Manager")
    
    if not frappe.db.exists("Biometric Device", device_name):
        frappe.throw(_("Device {0} not found").format(device_name))
    
    device = frappe.get_doc("Biometric Device", device_name)
    communicator = DeviceCommunicator(device)
    
    try:
        result = communicator.test_connection()
        return {
            "success": True,
            "message": _("Connection successful"),
            "device_info": result,
            "timestamp": now_datetime().isoformat()
        }
    except ZKTecoBaseError as e:
        return {
            "success": False,
            "message": e.message,
            "error_code": e.error_code.value,
            "timestamp": now_datetime().isoformat()
        }


@frappe.whitelist()
def sync_device(device_name: str, force: bool = False) -> dict[str, Any]:
    """
    Trigger manual sync for a specific device.

    Args:
        device_name: Name of the Biometric Device document
        force: Force sync even if auto-sync is disabled

    Returns:
        Dictionary with sync operation results

    Raises:
        frappe.PermissionError: If user lacks required permissions
    """
    frappe.only_for("System Manager", "ZKTeco Manager")
    
    if not frappe.db.exists("Biometric Device", device_name):
        frappe.throw(_("Device {0} not found").format(device_name))
    
    device = frappe.get_doc("Biometric Device", device_name)
    
    if not device.sync_enabled and not force:
        frappe.throw(_("Auto-sync is disabled for this device. Use force=True to override."))
    
    # Enqueue background job for sync
    sync_engine = SyncEngine()
    job_id = frappe.enqueue(
        "zkteco_attendance.utils.sync_engine.sync_single_device",
        device_name=device_name,
        queue="long",
        timeout=600,
        job_name=f"Sync Device: {device_name}"
    )
    
    return {
        "success": True,
        "message": _("Sync job enqueued"),
        "job_id": job_id,
        "device": device_name,
        "timestamp": now_datetime().isoformat()
    }


@frappe.whitelist()
def sync_all_devices(force: bool = False) -> dict[str, Any]:
    """
    Trigger sync for all enabled devices.

    Args:
        force: Force sync even if auto-sync is disabled

    Returns:
        Dictionary with sync operation results
    """
    frappe.only_for("System Manager", "ZKTeco Manager")
    
    devices = frappe.get_all(
        "Biometric Device",
        filters={"sync_enabled": 1} if not force else {},
        fields=["name", "device_name"]
    )
    
    job_ids = []
    for device in devices:
        job_id = frappe.enqueue(
            "zkteco_attendance.utils.sync_engine.sync_single_device",
            device_name=device.name,
            queue="long",
            timeout=600,
            job_name=f"Sync Device: {device.device_name or device.name}"
        )
        job_ids.append({"device": device.name, "job_id": job_id})
    
    return {
        "success": True,
        "message": _("Sync jobs enqueued for {0} devices").format(len(devices)),
        "jobs": job_ids,
        "timestamp": now_datetime().isoformat()
    }


@frappe.whitelist()
def get_device_status(device_name: str) -> dict[str, Any]:
    """
    Get current status of a device.

    Args:
        device_name: Name of the Biometric Device document

    Returns:
        Dictionary with device status information
    """
    frappe.only_for("System Manager", "ZKTeco Manager")
    
    if not frappe.db.exists("Biometric Device", device_name):
        frappe.throw(_("Device {0} not found").format(device_name))
    
    device = frappe.get_doc("Biometric Device", device_name)
    
    # Get recent sync logs
    recent_syncs = frappe.get_all(
        "Biometric Sync Log",
        filters={"device": device_name},
        fields=["name", "sync_start", "sync_end", "status", "records_downloaded", "records_imported"],
        order_by="creation desc",
        limit=5
    )
    
    # Get today's punch count
    today_punches = frappe.db.count(
        "Biometric Attendance Log",
        filters={
            "device": device_name,
            "timestamp": [">=", frappe.utils.today()]
        }
    )
    
    # Get unmapped count for this device
    unmapped_count = frappe.db.sql("""
        SELECT COUNT(DISTINCT bal.device_user_id) 
        FROM `tabBiometric Attendance Log` bal
        LEFT JOIN `tabBiometric Employee Mapping` bem 
            ON bal.device_user_id = bem.biometric_user_id 
            AND bal.device = bem.device
        WHERE bal.device = %s AND bem.name IS NULL
    """, device_name)[0][0]
    
    return {
        "device": device_name,
        "device_name": device.device_name,
        "status": device.status,
        "last_sync_time": device.last_sync_time,
        "sync_enabled": device.sync_enabled,
        "today_punches": today_punches,
        "unmapped_users": unmapped_count,
        "recent_syncs": recent_syncs,
        "timestamp": now_datetime().isoformat()
    }


@frappe.whitelist()
def reprocess_logs(
    from_date: str,
    to_date: str,
    device: str | None = None,
    employee: str | None = None,
    status_filter: str | None = None
) -> dict[str, Any]:
    """
    Reprocess attendance logs based on filters.

    Args:
        from_date: Start date for reprocessing
        to_date: End date for reprocessing
        device: Optional device filter
        employee: Optional employee filter
        status_filter: Optional status filter (Failed, Skipped)

    Returns:
        Dictionary with reprocessing results
    """
    frappe.only_for("System Manager", "ZKTeco Manager")
    
    filters = {
        "timestamp": ["between", [from_date, to_date]]
    }
    
    if device:
        filters["device"] = device
    if employee:
        filters["employee"] = employee
    if status_filter:
        filters["processed"] = status_filter
    
    logs_to_reprocess = frappe.get_all(
        "Biometric Attendance Log",
        filters=filters,
        fields=["name", "employee", "device_user_id", "device", "timestamp", "punch_type"]
    )
    
    if not logs_to_reprocess:
        return {
            "success": True,
            "message": _("No logs found matching the criteria"),
            "reprocessed": 0
        }
    
    # Enqueue reprocessing job
    job_id = frappe.enqueue(
        "zkteco_attendance.utils.attendance_processor.reprocess_logs_bulk",
        log_ids=[log.name for log in logs_to_reprocess],
        queue="long",
        timeout=1800,
        job_name="Reprocess Attendance Logs"
    )
    
    return {
        "success": True,
        "message": _("Reprocessing job enqueued for {0} logs").format(len(logs_to_reprocess)),
        "job_id": job_id,
        "logs_to_reprocess": len(logs_to_reprocess),
        "timestamp": now_datetime().isoformat()
    }


@frappe.whitelist()
def get_unmapped_employees(device: str | None = None) -> list[dict[str, Any]]:
    """
    Get list of unmapped device users for mapping suggestions.

    Args:
        device: Optional device filter

    Returns:
        List of unmapped user information
    """
    frappe.only_for("System Manager", "ZKTeco Manager")
    
    query = """
        SELECT 
            bal.device_user_id,
            bal.device,
            MIN(bal.timestamp) as first_punch,
            MAX(bal.timestamp) as last_punch,
            COUNT(*) as punch_count
        FROM `tabBiometric Attendance Log` bal
        LEFT JOIN `tabBiometric Employee Mapping` bem 
            ON bal.device_user_id = bem.biometric_user_id 
            AND bal.device = bem.device
        WHERE bem.name IS NULL
    """
    
    params: list[Any] = []
    
    if device:
        query += " AND bal.device = %s"
        params.append(device)
    
    query += """
        GROUP BY bal.device_user_id, bal.device
        ORDER BY punch_count DESC
        LIMIT 100
    """
    
    result = frappe.db.sql(query, params, as_dict=True)
    return result


@frappe.whitelist()
def auto_map_employees(device: str | None = None, threshold: float = 0.85) -> dict[str, Any]:
    """
    Auto-map device users to ERPNext employees based on matching criteria.

    Args:
        device: Optional device filter
        threshold: Minimum matching threshold (0-1)

    Returns:
        Dictionary with auto-mapping results
    """
    frappe.only_for("System Manager", "ZKTeco Manager")
    
    from .utils.employee_mapper import EmployeeMapper
    
    mapper = EmployeeMapper(device=device)
    result = mapper.auto_map(threshold=threshold)
    
    return {
        "success": True,
        "mapped": result["mapped"],
        "unmapped": result["unmapped"],
        "suggestions": result["suggestions"],
        "timestamp": now_datetime().isoformat()
    }


@frappe.whitelist()
def get_dashboard_data() -> dict[str, Any]:
    """
    Get data for the Biometric Attendance dashboard.

    Returns:
        Dictionary with dashboard widget data
    """
    frappe.only_for("System Manager", "ZKTeco Manager")
    
    today = frappe.utils.today()
    
    # Connected/Active devices
    active_devices = frappe.db.count("Biometric Device", {"status": "Active"})
    total_devices = frappe.db.count("Biometric Device")
    
    # Today's punches
    today_punches = frappe.db.count(
        "Biometric Attendance Log",
        {"timestamp": [">=", today]}
    )
    
    # Sync failures in last 24 hours
    sync_failures = frappe.db.count(
        "Biometric Sync Log",
        {
            "status": "Failed",
            "sync_start": [">=", frappe.utils.add_days(today, -1)]
        }
    )
    
    # Unmapped employees
    unmapped = frappe.db.sql("""
        SELECT COUNT(DISTINCT device_user_id) 
        FROM `tabBiometric Attendance Log` bal
        WHERE NOT EXISTS (
            SELECT 1 FROM `tabBiometric Employee Mapping` bem 
            WHERE bem.biometric_user_id = bal.device_user_id 
            AND bem.device = bal.device
        )
    """)[0][0]
    
    # Processed vs Unprocessed
    processed = frappe.db.count(
        "Biometric Attendance Log",
        {"processed": "Processed"}
    )
    pending = frappe.db.count(
        "Biometric Attendance Log",
        {"processed": "Pending"}
    )
    failed = frappe.db.count(
        "Biometric Attendance Log",
        {"processed": "Failed"}
    )
    
    # Recent sync logs
    recent_syncs = frappe.get_all(
        "Biometric Sync Log",
        fields=["name", "device", "sync_start", "status", "records_downloaded", "records_imported"],
        order_by="creation desc",
        limit=10
    )
    
    # Device-wise punch distribution
    device_punches = frappe.db.sql("""
        SELECT bd.name, bd.device_name, 
               COUNT(bal.name) as punch_count
        FROM `tabBiometric Device` bd
        LEFT JOIN `tabBiometric Attendance Log` bal 
            ON bd.name = bal.device 
            AND bal.timestamp >= %s
        GROUP BY bd.name, bd.device_name
        ORDER BY punch_count DESC
    """, today, as_dict=True)
    
    return {
        "devices": {
            "active": active_devices,
            "total": total_devices,
            "inactive": total_devices - active_devices
        },
        "today_punches": today_punches,
        "sync_failures": sync_failures,
        "unmapped_employees": unmapped,
        "log_status": {
            "processed": processed,
            "pending": pending,
            "failed": failed
        },
        "recent_syncs": recent_syncs,
        "device_punches": device_punches,
        "timestamp": now_datetime().isoformat()
    }


@frappe.whitelist()
def discover_devices(network_range: str, timeout: int = 2) -> dict[str, Any]:
    """
    Discover ZKTeco devices on the network.

    Args:
        network_range: IP range to scan (e.g., "192.168.1.0/24")
        timeout: Connection timeout in seconds

    Returns:
        Dictionary with discovered devices

    Note:
        This is a potentially long-running operation and runs in background.
    """
    frappe.only_for("System Manager", "ZKTeco Manager")
    
    job_id = frappe.enqueue(
        "zkteco_attendance.utils.device_communicator.discover_devices",
        network_range=network_range,
        timeout=timeout,
        queue="long",
        timeout=300,
        job_name="Discover ZKTeco Devices"
    )
    
    return {
        "success": True,
        "message": _("Device discovery started"),
        "job_id": job_id,
        "timestamp": now_datetime().isoformat()
    }


@frappe.whitelist()
def bulk_import_historical_logs(
    device_name: str,
    from_date: str,
    to_date: str
) -> dict[str, Any]:
    """
    Bulk import historical attendance logs from a device.

    Args:
        device_name: Name of the Biometric Device
        from_date: Start date
        to_date: End date

    Returns:
        Dictionary with import job information
    """
    frappe.only_for("System Manager", "ZKTeco Manager")
    
    if not frappe.db.exists("Biometric Device", device_name):
        frappe.throw(_("Device {0} not found").format(device_name))
    
    job_id = frappe.enqueue(
        "zkteco_attendance.utils.sync_engine.sync_historical_data",
        device_name=device_name,
        from_date=from_date,
        to_date=to_date,
        queue="long",
        timeout=3600,
        job_name=f"Historical Import: {device_name}"
    )
    
    return {
        "success": True,
        "message": _("Historical data import started"),
        "job_id": job_id,
        "device": device_name,
        "date_range": {"from": from_date, "to": to_date},
        "timestamp": now_datetime().isoformat()
    }
