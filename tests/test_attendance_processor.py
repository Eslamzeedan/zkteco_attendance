# Copyright (c) 2024 Your Organization
# MIT License

"""
Tests for AttendanceProcessor class.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, call

from zkteco_attendance.utils.attendance_processor import AttendanceProcessor
from zkteco_attendance.exceptions import EmployeeMappingNotFoundError, DuplicateCheckinError
from zkteco_attendance.constants import LogProcessStatus


@pytest.fixture
def processor():
    """Create AttendanceProcessor instance."""
    with patch('zkteco_attendance.utils.attendance_processor.EmployeeMapper') as mock_mapper:
        proc = AttendanceProcessor()
        proc.mapper = mock_mapper.return_value
        yield proc


@pytest.fixture
def sample_log():
    """Create sample log data."""
    return {
        "name": "LOG-001",
        "device_user_id": "1001",
        "device": "TEST-DEVICE-001",
        "timestamp": datetime.now() - timedelta(hours=2),
        "punch_type": "IN"
    }


@patch('zkteco_attendance.utils.attendance_processor frappe')
def test_process_single_log_success(mock_frappe, processor, sample_log):
    """Test successful processing of a single log."""
    processor.mapper.get_mapping.return_value = "HR-EMP-001"
    mock_frappe.db.exists.return_value = False
    mock_frappe.db.get_value.return_value = "John Doe"
    
    mock_checkin = MagicMock()
    mock_checkin.name = "CHK-001"
    mock_frappe.get_doc.return_value = mock_checkin
    
    result = processor._process_single_log(sample_log)
    
    assert result == "CHK-001"
    mock_frappe.get_doc.assert_called_once()
    mock_checkin.insert.assert_called_once_with(ignore_permissions=True)


@patch('zkteco_attendance.utils.attendance_processor frappe')
def test_process_single_log_no_mapping(mock_frappe, processor, sample_log):
    """Test processing log with missing mapping."""
    processor.mapper.get_mapping.return_value = None
    
    with pytest.raises(EmployeeMappingNotFoundError):
        processor._process_single_log(sample_log)
    
    mock_frappe.db.set_value.assert_called()


@patch('zkteco_attendance.utils.attendance_processor frappe')
def test_process_single_log_duplicate(mock_frappe, processor, sample_log):
    """Test processing duplicate log."""
    processor.mapper.get_mapping.return_value = "HR-EMP-001"
    mock_frappe.db.exists.return_value = True  # Duplicate detected
    
    with pytest.raises(DuplicateCheckinError):
        processor._process_single_log(sample_log)


@patch('zkteco_attendance.utils.attendance_processor frappe')
def test_determine_log_type_device_known(mock_frappe, processor):
    """Test log type determination when device specifies it."""
    result_in = processor._determine_log_type("HR-EMP-001", datetime.now(), "IN")
    assert result_in == "IN"
    
    result_out = processor._determine_log_type("HR-EMP-001", datetime.now(), "OUT")
    assert result_out == "OUT"


@patch('zkteco_attendance.utils.attendance_processor frappe')
def test_determine_log_type_unknown_first_punch(mock_frappe, processor):
    """Test log type determination for first punch of day."""
    mock_frappe.db.get_value.return_value = None  # No previous checkin
    
    result = processor._determine_log_type("HR-EMP-001", datetime.now(), "Unknown")
    assert result == "IN"


@patch('zkteco_attendance.utils.attendance_processor frappe')
def test_determine_log_type_unknown_alternating(mock_frappe, processor):
    """Test log type determination alternating based on previous."""
    now = datetime.now()
    
    # Previous was IN, so this should be OUT
    mock_frappe.db.get_value.return_value = ("CHK-PREV", now - timedelta(hours=1), "IN")
    result = processor._determine_log_type("HR-EMP-001", now, "Unknown")
    assert result == "OUT"
    
    # Previous was OUT, so this should be IN
    mock_frappe.db.get_value.return_value = ("CHK-PREV2", now - timedelta(minutes=30), "OUT")
    result = processor._determine_log_type("HR-EMP-001", now, "Unknown")
    assert result == "IN"


@patch('zkteco_attendance.utils.attendance_processor frappe')
def test_is_duplicate_checkin_true(mock_frappe, processor):
    """Test duplicate checkin detection."""
    mock_frappe.db.exists.return_value = True
    timestamp = datetime.now()
    
    result = processor._is_duplicate_checkin("HR-EMP-001", timestamp)
    assert result is True


@patch('zkteco_attendance.utils.attendance_processor frappe')
def test_is_duplicate_checkin_false(mock_frappe, processor):
    """Test non-duplicate checkin detection."""
    mock_frappe.db.exists.return_value = False
    timestamp = datetime.now()
    
    result = processor._is_duplicate_checkin("HR-EMP-001", timestamp)
    assert result is False
