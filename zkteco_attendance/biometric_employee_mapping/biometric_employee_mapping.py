# Copyright (c) 2024 Your Organization
# MIT License

"""
Biometric Employee Mapping document controller.
"""

import frappe
from frappe import _
from frappe.model.document import Document


class BiometricEmployeeMapping(Document):
    """Biometric Employee Mapping with duplicate detection."""

    def validate(self):
        """Validate mapping before saving."""
        self.validate_duplicate_employee_device()
        self.validate_duplicate_user_device()
        self.set_employee_id()

    def validate_duplicate_employee_device(self):
        """Ensure employee is not mapped twice to same device."""
        if not self.employee or not self.device:
            return
            
        existing = frappe.db.get_value(
            "Biometric Employee Mapping",
            {
                "employee": self.employee,
                "device": self.device,
                "name": ["!=", self.name]
            },
            "name"
        )
        
        if existing:
            frappe.throw(
                _("Employee {0} is already mapped to another user on device {1}").format(
                    self.employee,
                    self.device
                )
            )

    def validate_duplicate_user_device(self):
        """Ensure device user is not mapped twice."""
        if not self.biometric_user_id or not self.device:
            return
            
        existing = frappe.db.get_value(
            "Biometric Employee Mapping",
            {
                "biometric_user_id": self.biometric_user_id,
                "device": self.device,
                "name": ["!=", self.name]
            },
            "name"
        )
        
        if existing:
            frappe.throw(
                _("Device user {0} is already mapped on device {1}").format(
                    self.biometric_user_id,
                    self.device
                )
            )

    def set_employee_id(self):
        """Set ERPNext Employee ID field."""
        if self.employee:
            self.erpnext_employee_id = self.employee

    def before_insert(self):
        """Set audit fields before insert."""
        self.created_by = frappe.session.user
