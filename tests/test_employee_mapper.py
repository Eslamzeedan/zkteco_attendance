# Copyright (c) 2024 Your Organization
# MIT License

"""
Tests for EmployeeMapper class.
"""

import pytest
from unittest.mock import patch, MagicMock

from zkteco_attendance.utils.employee_mapper import EmployeeMapper


@pytest.fixture
def mapper():
    """Create EmployeeMapper instance."""
    return EmployeeMapper(device="TEST-DEVICE-001")


@patch('zkteco_attendance.utils.employee_mapper frappe')
def test_get_mapping_found(mock_frappe, mapper):
    """Test getting an existing mapping."""
    mock_frappe.db.get_value.return_value = "HR-EMP-001"
    
    result = mapper.get_mapping("1001", "TEST-DEVICE-001")
    
    assert result == "HR-EMP-001"
    mock_frappe.db.get_value.assert_called_once_with(
        "Biometric Employee Mapping",
        {"biometric_user_id": "1001", "device": "TEST-DEVICE-001"},
        "employee"
    )


@patch('zkteco_attendance.utils.employee_mapper frappe')
def test_get_mapping_not_found(mock_frappe, mapper):
    """Test getting a non-existing mapping returns None."""
    mock_frappe.db.get_value.return_value = None
    
    result = mapper.get_mapping("9999", "TEST-DEVICE-001")
    
    assert result is None


@patch('zkteco_attendance.utils.employee_mapper frappe')
def test_create_mapping_success(mock_frappe, mapper):
    """Test successful mapping creation."""
    mock_frappe.db.exists.return_value = False
    mock_frappe.db.get_value.return_value = "John Doe"
    mock_doc = MagicMock()
    mock_frappe.get_doc.return_value = mock_doc
    
    result = mapper.create_mapping("HR-EMP-001", "1001", "TEST-DEVICE-001")
    
    assert result == mock_doc.name
    mock_frappe.get_doc.assert_called_once()
    mock_doc.insert.assert_called_once_with(ignore_permissions=True)


@patch('zkteco_attendance.utils.employee_mapper frappe')
def test_create_mapping_duplicate_user(mock_frappe, mapper):
    """Test creating duplicate mapping throws error."""
    mock_frappe.db.exists.return_value = True
    
    with pytest.raises(Exception) as exc_info:
        mapper.create_mapping("HR-EMP-001", "1001", "TEST-DEVICE-001")
    
    assert "already exists" in str(exc_info.value)


def test_exact_id_match(mapper):
    """Test exact ID matching logic."""
    employee = {
        "name": "1001",
        "employee_name": "Test User",
        "employee_number": "EMP-1001"
    }
    
    assert mapper._exact_id_match("1001", employee) is True
    assert mapper._exact_id_match("EMP-1001", employee) is True
    assert mapper._exact_id_match("9999", employee) is False


def test_numeric_id_match(mapper):
    """Test numeric ID matching logic."""
    employee = {
        "name": "HR-EMP-001",
        "employee_name": "Test User",
        "employee_number": "1001"
    }
    
    # Exact numeric match in employee_number
    score = mapper._numeric_id_match("1001", employee)
    assert score == 0.95
    
    # Partial numeric match
    score = mapper._numeric_id_match("10012", employee)
    assert score == 0.8
    
    # No match
    score = mapper._numeric_id_match("9999", employee)
    assert score == 0.0
