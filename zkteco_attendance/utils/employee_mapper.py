# Copyright (c) 2026 Eslam Zedan
# MIT License

"""
Employee mapping utilities for ZKTeco integration.

Handles mapping between device user IDs and ERPNext Employee records.
Supports auto-mapping, manual mapping, and mapping suggestions.
"""

import re
import logging
from difflib import SequenceMatcher
from typing import Any, Optional

import frappe
from frappe import _

from ..constants import AUTO_MAP_THRESHOLD, MIN_MATCH_SCORE

logger = logging.getLogger(__name__)


class EmployeeMapper:
    """
    Handles mapping between ZKTeco device users and ERPNext employees.
    
    Features:
    - Auto-mapping based on user ID and name matching
    - Manual mapping management
    - Mapping suggestions
    - Duplicate detection
    """

    def __init__(self, device: Optional[str] = None) -> None:
        """
        Initialize EmployeeMapper.
        
        Args:
            device: Optional device name to filter operations
        """
        self.device = device

    def get_mapping(
        self,
        device_user_id: str,
        device: str
    ) -> Optional[str]:
        """
        Get ERPNext employee ID for a device user.
        
        Args:
            device_user_id: User ID on the device
            device: Device name
            
        Returns:
            Employee ID if mapping exists, None otherwise
        """
        mapping = frappe.db.get_value(
            "Biometric Employee Mapping",
            {
                "biometric_user_id": device_user_id,
                "device": device
            },
            "employee"
        )
        return mapping

    def create_mapping(
        self,
        employee: str,
        biometric_user_id: str,
        device: str
    ) -> str:
        """
        Create a new employee mapping.
        
        Args:
            employee: ERPNext Employee ID
            biometric_user_id: User ID on the device
            device: Device name
            
        Returns:
            Name of the created mapping document
            
        Raises:
            frappe.ValidationError: If mapping already exists
        """
        # Check for existing mapping
        if frappe.db.exists(
            "Biometric Employee Mapping",
            {
                "biometric_user_id": biometric_user_id,
                "device": device
            }
        ):
            frappe.throw(
                _("Mapping already exists for user ID {0} on device {1}").format(
                    biometric_user_id, device
                )
            )
        
        # Check for duplicate employee mapping on same device
        if frappe.db.exists(
            "Biometric Employee Mapping",
            {
                "employee": employee,
                "device": device
            }
        ):
            frappe.throw(
                _("Employee {0} is already mapped to another user on device {1}").format(
                    employee, device
                )
            )
        
        # Get employee name
        employee_name = frappe.db.get_value("Employee", employee, "employee_name")
        
        mapping = frappe.get_doc({
            "doctype": "Biometric Employee Mapping",
            "employee": employee,
            "employee_name": employee_name,
            "erpnext_employee_id": employee,
            "biometric_user_id": biometric_user_id,
            "device": device,
            "mapping_type": "Manual"
        })
        mapping.insert(ignore_permissions=True)
        
        logger.info(
            f"Created mapping: Employee={employee}, "
            f"BioID={biometric_user_id}, Device={device}"
        )
        
        return mapping.name

    def delete_mapping(self, mapping_name: str) -> None:
        """
        Delete an employee mapping.
        
        Args:
            mapping_name: Name of the mapping document
        """
        frappe.delete_doc("Biometric Employee Mapping", mapping_name, force=True)
        logger.info(f"Deleted mapping: {mapping_name}")

    def auto_map(
        self,
        device: Optional[str] = None,
        threshold: float = AUTO_MAP_THRESHOLD
    ) -> dict[str, Any]:
        """
        Automatically map device users to employees.
        
        Uses multiple matching strategies:
        1. Exact user ID match (employee ID = device user ID)
        2. User ID in employee ID (substring match)
        3. Name similarity matching
        
        Args:
            device: Optional device filter
            threshold: Minimum match score (0-1)
            
        Returns:
            Dictionary with mapping results
        """
        device_filter = device or self.device
        
        # Get unmapped device users
        unmapped_users = self._get_unmapped_users(device_filter)
        
        if not unmapped_users:
            return {
                "mapped": 0,
                "unmapped": 0,
                "suggestions": []
            }
        
        # Get active employees
        employees = self._get_active_employees()
        
        mapped_count = 0
        suggestions = []
        
        for user in unmapped_users:
            match_result = self._find_best_match(user, employees, threshold)
            
            if match_result["matched"]:
                try:
                    self.create_mapping(
                        employee=match_result["employee"],
                        biometric_user_id=user["device_user_id"],
                        device=user["device"]
                    )
                    mapped_count += 1
                except Exception as e:
                    logger.warning(
                        f"Failed to auto-map {user['device_user_id']}: {e}"
                    )
            elif match_result["score"] >= MIN_MATCH_SCORE / 100:
                suggestions.append({
                    "device_user_id": user["device_user_id"],
                    "device": user["device"],
                    "suggested_employee": match_result.get("employee"),
                    "suggested_name": match_result.get("employee_name"),
                    "score": match_result["score"],
                    "match_type": match_result["match_type"]
                })
        
        unmapped_count = len(unmapped_users) - mapped_count
        
        logger.info(
            f"Auto-mapping complete: Mapped={mapped_count}, "
            f"Unmapped={unmapped_count}, Suggestions={len(suggestions)}"
        )
        
        return {
            "mapped": mapped_count,
            "unmapped": unmapped_count,
            "suggestions": suggestions
        }

    def _get_unmapped_users(self, device: Optional[str]) -> list[dict[str, Any]]:
        """Get device users without mappings."""
        query = """
            SELECT 
                bal.device_user_id,
                bal.device,
                MAX(bal.timestamp) as last_punch
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
            ORDER BY last_punch DESC
        """
        
        return frappe.db.sql(query, params, as_dict=True)

    def _get_active_employees(self) -> list[dict[str, Any]]:
        """Get all active employees."""
        return frappe.get_all(
            "Employee",
            filters={"status": "Active"},
            fields=["name", "employee_name", "employee_number", "personal_email", "cell_number"]
        )

    def _find_best_match(
        self,
        user: dict[str, Any],
        employees: list[dict[str, Any]],
        threshold: float
    ) -> dict[str, Any]:
        """
        Find the best employee match for a device user.
        
        Args:
            user: Device user information
            employees: List of active employees
            threshold: Minimum match threshold
            
        Returns:
            Dictionary with match results
        """
        best_match = {
            "matched": False,
            "employee": None,
            "employee_name": None,
            "score": 0,
            "match_type": None
        }
        
        device_user_id = user["device_user_id"]
        
        for emp in employees:
            # Strategy 1: Exact ID match
            if self._exact_id_match(device_user_id, emp):
                return {
                    "matched": True,
                    "employee": emp["name"],
                    "employee_name": emp["employee_name"],
                    "score": 1.0,
                    "match_type": "Exact ID"
                }
            
            # Strategy 2: Numeric ID match
            numeric_match = self._numeric_id_match(device_user_id, emp)
            if numeric_match > best_match["score"]:
                best_match = {
                    "matched": numeric_match >= threshold,
                    "employee": emp["name"],
                    "employee_name": emp["employee_name"],
                    "score": numeric_match,
                    "match_type": "Numeric ID"
                }
            
            # Strategy 3: Employee number match
            emp_num_match = self._employee_number_match(device_user_id, emp)
            if emp_num_match > best_match["score"]:
                best_match = {
                    "matched": emp_num_match >= threshold,
                    "employee": emp["name"],
                    "employee_name": emp["employee_name"],
                    "score": emp_num_match,
                    "match_type": "Employee Number"
                }
        
        return best_match

    def _exact_id_match(self, device_user_id: str, employee: dict[str, Any]) -> bool:
        """Check for exact ID match."""
        emp_id = employee["name"]
        emp_number = employee.get("employee_number", "")
        
        return device_user_id in [emp_id, emp_number]

    def _numeric_id_match(self, device_user_id: str, employee: dict[str, Any]) -> float:
        """Calculate numeric ID match score."""
        # Extract numbers from device user ID
        device_numbers = re.findall(r'\d+', device_user_id)
        if not device_numbers:
            return 0.0
        
        device_num = device_numbers[0]
        
        # Compare with employee ID numbers
        emp_id_numbers = re.findall(r'\d+', employee["name"])
        emp_num_numbers = re.findall(r'\d+', employee.get("employee_number", ""))
        
        if device_num in emp_id_numbers or device_num in emp_num_numbers:
            return 0.95
        
        # Partial match
        for num_list in [emp_id_numbers, emp_num_numbers]:
            for num in num_list:
                if num in device_num or device_num in num:
                    return 0.8
        
        return 0.0

    def _employee_number_match(self, device_user_id: str, employee: dict[str, Any]) -> float:
        """Calculate employee number match score."""
        emp_number = employee.get("employee_number", "")
        if not emp_number:
            return 0.0
        
        # Direct match
        if device_user_id == emp_number:
            return 0.95
        
        # Similarity score
        ratio = SequenceMatcher(None, device_user_id, emp_number).ratio()
        return ratio if ratio > 0.7 else 0.0

    def get_mapping_suggestions(
        self,
        device: Optional[str] = None,
        limit: int = 50
    ) -> list[dict[str, Any]]:
        """
        Get mapping suggestions for unmapped users.
        
        Args:
            device: Optional device filter
            limit: Maximum suggestions to return
            
        Returns:
            List of suggestion dictionaries
        """
        result = self.auto_map(device=device, threshold=0.0)
        return result["suggestions"][:limit]
