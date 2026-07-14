# Copyright (c) 2024 Your Organization
# MIT License

"""
Tests for SyncEngine class.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock, call

from zkteco_attendance.utils.sync_engine import SyncEngine
from zkteco_attendance.exceptions import DeviceConnectionError, SyncError
from zkteco_attendance.constants import SyncStatus, DeviceStatus


@pytest.fixture
def sync_engine():
    """Create SyncEngine instance with mocked processor."""
    with patch('zkteco_attendance.utils.sync_engine.AttendanceProcessor') as mock_processor:
        engine = SyncEngine()
        engine.processor = mock_processor.return_value
        yield engine


@pytest.fixture
def mock_logs():
    """Create sample parsed logs."""
    return [
        {
            "device_user_id": "1001",
            "timestamp": datetime.now() - timedelta(hours=2),
            "punch_type": "IN",
            "status_code": 0,
            "verified": 1,
            "work_code": 0
        },
        {
            "device_user_id": "1002",
            "timestamp": datetime.now() - timedelta(hours=1),
            "punch_type": "OUT",
            "status_code": 1,
            "verified": 1,
            "work_code": 0
        }
    ]


@patch('zkteco_attendance.utils.sync_engine.DeviceCommunicator')
@patch('zkteco_attendance.utils.sync_engine frappe')
def test_sync_single_device_success(mock_frappe, mock_comm_class, sync_engine, mock_device_doc, mock_logs):
    """Test successful device sync."""
    # Setup mocks
    mock_frappe.get_doc.return_value = mock_device_doc
    mock_frappe.utils.now_datetime.return_value = datetime.now()
    
    mock_comm_instance = MagicMock()
    mock_comm_class.return_value = mock_comm_instance
    mock_comm_instance.get_attendance_logs.return_value = mock_logs
    
    mock_sync_log = MagicMock()
    mock_frappe.get_doc.return_value = mock_device_doc
    mock_frappe.new_doc.return_value = mock_sync_log
    
    sync_engine.processor.process_device_logs.return_value = (2, 0)
    
    # Execute
    result = sync_engine.sync_single_device("TEST-DEVICE-001")
    
    # Assert
    mock_comm_instance.get_attendance_logs.assert_called_once()
    assert mock_sync_log.insert.called or mock_sync_log.db_set.called
    assert mock_frappe.db.set_value.called


@patch('zkteco_attendance.utils.sync_engine.DeviceCommunicator')
@patch('zkteco_attendance.utils.sync_engine frappe')
def test_sync_single_device_connection_error(mock_frappe, mock_comm_class, sync_engine, mock_device_doc):
    """Test device sync handling connection error."""
    mock_frappe.get_doc.return_value = mock_device_doc
    mock_comm_instance = MagicMock()
    mock_comm_class.return_value = mock_comm_instance
    mock_comm_instance.get_attendance_logs.side_effect = DeviceConnectionError(
        device_ip="192.168.1.100",
        device_port=4370,
        reason="Timeout"
    )
    
    mock_sync_log = MagicMock()
    mock_frappe.new_doc.return_value = mock_sync_log
    
    with pytest.raises(DeviceConnectionError):
        sync_engine.sync_single_device("TEST-DEVICE-001")
    
    # Verify error was handled and status updated
    assert mock_sync_log.db_set.called
    calls = [c for c in mock_sync_log.db_set.call_args_list if 'status' in str(c)]
    assert any("Failed" in str(c) for c in calls)


@patch('zkteco_attendance.utils.sync_engine frappe')
def test_is_duplicate_log_true(mock_frappe, sync_engine):
    """Test duplicate log detection returns true."""
    mock_frappe.db.exists.return_value = True
    
    result = sync_engine._is_duplicate_log(
        "TEST-DEVICE-001",
        "1001",
        datetime.now()
    )
    
    assert result is True
    mock_frappe.db.exists.assert_called_once()


@patch('zkteco_attendance.utils.sync_engine frappe')
def test_is_duplicate_log_false(mock_frappe, sync_engine):
    """Test duplicate log detection returns false."""
    mock_frappe.db.exists.return_value = False
    
    result = sync_engine._is_duplicate_log(
        "TEST-DEVICE-001",
        "1001",
        datetime.now()
    )
    
    assert result is False
