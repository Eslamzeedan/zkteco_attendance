# Copyright (c) 2024 Your Organization
# MIT License

"""
Biometric Sync Log document controller.
"""

import frappe
from frappe import _
from frappe.model.document import Document


class BiometricSyncLog(Document):
    """Biometric Sync Log with duration calculation."""

    def before_save(self):
        """Calculate duration before saving."""
        self.calculate_duration()
        self.validate_status()

    def calculate_duration(self):
        """Calculate sync duration."""
        if self.sync_start and self.sync_end:
            start = frappe.utils.get_datetime(self.sync_start)
            end = frappe.utils.get_datetime(self.sync_end)
            duration_seconds = int((end - start).total_seconds())
            self.duration = duration_seconds

    def validate_status(self):
        """Validate status transitions."""
        valid_transitions = {
            "Pending": ["In Progress", "Cancelled"],
            "In Progress": ["Completed", "Failed", "Partially Completed", "Cancelled"],
            "Completed": [],
            "Failed": ["In Progress"],
            "Partially Completed": ["In Progress", "Completed"],
            "Cancelled": [],
        }
        
        if self.is_new():
            return
            
        old_status = frappe.db.get_value("Biometric Sync Log", self.name, "status")
        
        if old_status and old_status != self.status:
            allowed = valid_transitions.get(old_status, [])
            if self.status not in allowed:
                frappe.throw(
                    _("Cannot transition from {0} to {1}").format(
                        old_status, self.status
                    )
                )

    def before_delete(self):
        """Prevent deletion of sync logs."""
        frappe.throw(
            _("Biometric Sync Logs cannot be deleted for audit purposes."),
            title=_("Deletion Not Allowed")
        )
