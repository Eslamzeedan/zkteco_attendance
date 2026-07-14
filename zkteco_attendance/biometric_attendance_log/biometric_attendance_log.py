# Copyright (c) 2024 Your Organization
# MIT License

"""
Biometric Attendance Log document controller.
"""

import frappe
from frappe import _
from frappe.model.document import Document


class BiometricAttendanceLog(Document):
    """
    Biometric Attendance Log - Raw log storage.
    
    This doctype stores raw attendance logs from biometric devices.
    Logs should never be deleted - they serve as an audit trail.
    """

    def before_insert(self):
        """Validate before insert."""
        self.validate_timestamp()
        self.validate_device()

    def validate_timestamp(self):
        """Ensure timestamp is provided."""
        if not self.timestamp:
            frappe.throw(_("Timestamp is required"))

    def validate_device(self):
        """Ensure device exists."""
        if self.device and not frappe.db.exists("Biometric Device", self.device):
            frappe.throw(_("Biometric Device {0} does not exist").format(self.device))

    def before_delete(self):
        """Prevent deletion of logs for audit purposes."""
        frappe.throw(
            _("Biometric Attendance Logs cannot be deleted for audit purposes. "
              "Use the 'Skipped' status instead."),
            title=_("Deletion Not Allowed")
        )

    def on_trash(self):
        """Override to prevent deletion."""
        pass
