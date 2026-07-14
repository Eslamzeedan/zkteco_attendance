# Copyright (c) 2024 Your Organization
# MIT License

"""
Pytest configuration and fixtures for ZKTeco Attendance tests.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock


@pytest.fixture
def mock_device_doc():
    """Create a mock Biometric Device document."""
    device = Mock()
    device.name = "TEST-DEVICE-001"
    device.device_name = "Test Device HQ"
    device.device_ip = "192.168.1.100"
    device.device_port = 4370
    device.device_model = "MB2000"
    device.device_serial_number = "SN123456"
    device.password = None
    device.sync_enabled = True
    device.status = "Active"
    device.last_sync_time = None
    device.branch = "HQ"
    device.location = "Main Entrance"
    return device


@pytest.fixture
def mock_attendance_log():
    """Create a mock attendance log from device."""
    log = Mock()
    log.user_id = "1001"
    log.timestamp = datetime.now() - timedelta(hours=2)
    log.status = 0
    log.verified = 1
    log.work_code = 0
    return log


@pytest.fixture
def mock_user():
    """Create a mock user from device."""
    user = Mock()
    user.user_id = "1001"
    user.name = "John Doe"
    user.uid = 1
    user.privilege = 0
    user.password = ""
    user.group_id = ""
    return user


@pytest.fixture
def sample_employee():
    """Create sample employee data."""
    return {
        "name": "HR-EMP-001",
        "employee_name": "John Doe",
        "employee_number": "1001",
        "status": "Active",
        "personal_email": "john@example.com",
        "cell_number": "1234567890"
    }


@pytest.fixture
def parsed_log():
    """Create a parsed log dictionary."""
    return {
        "device_user_id": "1001",
        "timestamp": datetime.now() - timedelta(hours=2),
        "punch_type": "IN",
        "status_code": 0,
        "verified": 1,
        "work_code": 0
    }
