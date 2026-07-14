# Copyright (c) 2024 Your Organization
# MIT License

"""
Biometric Device document controller.
"""

import frappe
from frappe import _
from frappe.model.document import Document

from ..utils.device_communicator import DeviceCommunicator
from ..utils.validators import validate_ip_address, validate_port
from ..exceptions import ZKTecoBaseError


class BiometricDevice(Document):
    """Biometric Device document with connection testing and sync capabilities."""

    def validate(self):
        """Validate device configuration before saving."""
        self.validate_ip()
        self.validate_port_number()
        self.validate_unique_ip_port()

    def validate_ip(self):
        """Validate IP address format."""
        if self.device_ip:
            validate_ip_address(self.device_ip)

    def validate_port_number(self):
        """Validate port number."""
        if self.device_port:
            validate_port(self.device_port)

    def validate_unique_ip_port(self):
        """Ensure IP:Port combination is unique."""
        if not self.is_new():
            existing = frappe.db.get_value(
                "Biometric Device",
                {
                    "device_ip": self.device_ip,
                    "device_port": self.device_port,
                    "name": ["!=", self.name]
                },
                "name"
            )
            if existing:
                frappe.throw(
                    _("Another device with same IP:Port already exists: {0}").format(
                        existing
                    )
                )

    def on_update(self):
        """Handle after update events."""
        # Reset status if sync settings changed
        if self.has_value_changed("sync_enabled") or self.has_value_changed("sync_frequency"):
            if self.sync_enabled and self.status == "Inactive":
                self.db_set("status", "Active")

    def test_connection(self):
        """
        Test connection to the device.
        
        Called from the Test Connection button.
        """
        if not self.device_ip:
            frappe.throw(_("Device IP is required"))
        
        communicator = DeviceCommunicator(self)
        
        try:
            result = communicator.test_connection()
            
            # Update device info from response
            if result.get("serial_number"):
                self.db_set("device_serial_number", result["serial_number"])
            if result.get("firmware_version"):
                self.db_set("remarks", f"Firmware: {result['firmware_version']}")
            
            self.db_set("status", "Active")
            
            frappe.msgprint(
                _("Connection successful!\\n"
                  "Serial: {0}\\n"
                  "Firmware: {1}\\n"
                  "Users: {2}\\n"
                  "Logs: {3}").format(
                    result.get("serial_number", "N/A"),
                    result.get("firmware_version", "N/A"),
                    result.get("users_count", "N/A"),
                    result.get("log_count", "N/A")
                ),
                title=_("Connection Test"),
                indicator="green"
            )
            
        except ZKTecoBaseError as e:
            self.db_set("status", "Error")
            self.db_set("remarks", e.message[:140])
            frappe.msgprint(
                _("Connection failed: {0}").format(e.message),
                title=_("Connection Test"),
                indicator="red"
            )
            raise

    def manual_sync(self):
        """
        Trigger manual sync for this device.
        
        Called from the Manual Sync button.
        """
        if not self.sync_enabled:
            frappe.throw(_("Enable sync before triggering manual sync"))
        
        from ..utils.sync_engine import sync_single_device
        
        frappe.enqueue(
            "zkteco_attendance.utils.sync_engine.sync_single_device",
            device_name=self.name,
            queue="long",
            timeout=600,
            job_name=f"Manual Sync: {self.device_name}"
        )
        
        frappe.msgprint(
            _("Sync job has been enqueued. Check Sync Logs for progress."),
            title=_("Sync Started"),
            indicator="blue"
        )
