# Copyright (c) 2026 Eslam Zedan
# MIT License

"""
Cleanup operations when app is uninstalled.
"""

import frappe


def before_uninstall():
    """Clean up custom fields and other artifacts before uninstall."""
    
    # Remove custom fields added by this app
    custom_fields_to_remove = [
        {"dt": "Employee Checkin", "fieldname": "biometric_device"},
        {"dt": "Employee Checkin", "fieldname": "device_user_id"},
    ]
    
    for cf in custom_fields_to_remove:
        if frappe.db.exists("Custom Field", cf):
            frappe.delete_doc("Custom Field", cf, force=True)
    
    # Disable scheduler events
    frappe.db.sql("""
        DELETE FROM `tabScheduled Job Type` 
        WHERE method LIKE 'zkteco_attendance.%'
    """)
