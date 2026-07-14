# Copyright (c) 2024 Your Organization
# MIT License

"""
Employee document event handlers.

Handles automatic mapping suggestions when employees are created or updated.
"""

import logging
import frappe
from frappe import _

logger = logging.getLogger(__name__)


def after_employee_insert(doc, method):
    """
    Handle after employee insert.
    
    Checks if there are any unmapped device users that might match
    the new employee.
    """
    try:
        # Don't auto-create mappings, just log for review
        logger.info(
            f"New employee created: {doc.name} - {doc.employee_name}. "
            f"Check for potential device user mappings."
        )
    except Exception as e:
        logger.error(f"Error in after_employee_insert: {e}")


def on_employee_update(doc, method):
    """
    Handle employee update.
    
    Updates related mappings if employee name changes.
    """
    if doc.has_value_changed("employee_name"):
        try:
            frappe.db.sql("""
                UPDATE `tabBiometric Employee Mapping`
                SET employee_name = %s
                WHERE employee = %s
            """, (doc.employee_name, doc.name))
            logger.info(f"Updated mapping names for employee {doc.name}")
        except Exception as e:
            logger.error(f"Error updating mappings: {e}")


def before_employee_delete(doc, method):
    """
    Handle before employee delete.
    
    Optionally clean up or deactivate mappings.
    """
    try:
        mappings = frappe.get_all(
            "Biometric Employee Mapping",
            filters={"employee": doc.name},
            pluck="name"
        )
        
        if mappings:
            # Just log - don't auto-delete mappings for audit purposes
            logger.warning(
                f"Employee {doc.name} being deleted. "
                f"{len(mappings)} mappings will become orphaned."
            )
    except Exception as e:
        logger.error(f"Error in before_employee_delete: {e}")
