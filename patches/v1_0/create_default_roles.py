# Copyright (c) 2024 Your Organization
# MIT License

"""
Patch to create default roles and permissions for ZKTeco Attendance.
"""

import frappe


def execute():
    """Create ZKTeco Manager and ZKTeco User roles if they don't exist."""
    
    roles_data = [
        {
            "role_name": "ZKTeco Manager",
            "desk_access": 1,
            "description": "Full access to manage ZKTeco biometric devices, mappings, and sync operations."
        },
        {
            "role_name": "ZKTeco User",
            "desk_access": 1,
            "description": "Read-only access to view ZKTeco attendance logs and sync statuses."
        }
    ]
    
    for role_data in roles_data:
        if not frappe.db.exists("Role", role_data["role_name"]):
            role = frappe.new_doc("Role")
            role.update(role_data)
            role.insert(ignore_permissions=True)
            frappe.db.commit()
    
    # Add custom fields to Employee Checkin for traceability
    add_custom_fields()


def add_custom_fields():
    """Add custom fields to standard DocTypes."""
    
    import frappe.modules.utils
    
    custom_fields = {
        "Employee Checkin": [
            {
                "fieldname": "biometric_device",
                "label": "Biometric Device",
                "fieldtype": "Link",
                "options": "Biometric Device",
                "insert_after": "device_id",
                "read_only": 1,
                "hidden": 0,
                "translatable": 0
            },
            {
                "fieldname": "device_user_id",
                "label": "Device User ID",
                "fieldtype": "Data",
                "insert_after": "biometric_device",
                "read_only": 1,
                "hidden": 0,
                "translatable": 0
            },
            {
                "fieldname": "biometric_log",
                "label": "Biometric Log Reference",
                "fieldtype": "Link",
                "options": "Biometric Attendance Log",
                "insert_after": "device_user_id",
                "read_only": 1,
                "hidden": 1,
                "translatable": 0
            }
        ]
    }
    
    for doctype, fields in custom_fields.items():
        for field in fields:
            frappe.modules.utils.import_custom_fields({
                "dt": doctype,
                **field
            })
            
    frappe.db.commit()
