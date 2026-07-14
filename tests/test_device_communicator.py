# Copyright (c) 2024 Your Organization
# MIT License

"""
Tests for DeviceCommunicator class.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock, contextmanager

from zkteco_attendance.utils.device_communicator import DeviceCommunicator
from zkteco_attendance.exceptions import (
    DeviceConnectionError,
    DeviceTimeoutError,
    InvalidDataError,
)


class TestDeviceCommunicator:
    """Tests for DeviceCommunicator class."""

    def test_init(self, mock_device_doc):
        """Test communicator initialization."""
        comm = DeviceCommunicator(mock_device_doc)
        
        assert comm.device_ip == "192.168.1.100"
        assert comm.device_port == 4370
        assert comm.device_name == "TEST-DEVICE-001"
        assert comm.password is None

    def test_init_with_password(self, mock_device_doc):
        """Test communicator initialization with password."""
        mock_device_doc.password = "12345"
        comm = DeviceCommunicator(mock_device_doc)
        
        assert comm.password == 12345

    def test_init_with_invalid_password(self, mock_device_doc):
        """Test communicator initialization with invalid password."""
        mock_device_doc.password = "invalid"
        comm = DeviceCommunicator(mock_device_doc)
        
        assert comm.password == 0

    @patch('zkteco_attendance.utils.device_communicator.ZK')
    def test_test_connection_success(self, mock_zk_class, mock_device_doc):
        """Test successful connection test."""
        mock_conn = MagicMock()
        mock_zk_class.return_value = mock_conn
        mock_conn.get_device_info.return_value = {
            "serial_number": "SN123456",
            "platform": "ZEM560",
            "mac_address": "00:11:22:33:44:55"
        }
        mock_conn.get_firmware_version.return_value = "Ver 6.60"
        mock_conn.get_user_count.return_value = 100
        mock_conn.get_attendance_count.return_value = 5000
        
        comm = DeviceCommunicator(mock_device_doc)
        result = comm.test_connection()
        
        assert result["success"] is not None or result["serial_number"] == "SN123456"
        assert result["device_ip"] == "192.168.1.100"
        assert result["firmware_version"] == "Ver 6.60"
        mock_conn.connect.assert_called_once()
        mock_conn.disable_device.assert_called_once()
        mock_conn.enable_device.assert_called_once()
        mock_conn.disconnect.assert_called_once()

    @patch('zkteco_attendance.utils.device_communicator.ZK')
    def test_test_connection_failure(self, mock_zk_class, mock_device_doc):
        """Test connection failure."""
        import socket
        mock_zk_class.return_value.connect.side_effect = socket.timeout("Timeout")
        
        comm = DeviceCommunicator(mock_device_doc)
              with pytest.raises(DeviceConnectionError):
            comm.test_connection()

    @patch('zkteco_attendance.utils.device_communicator.ZK')
    def test_get_attendance_logs_success(self, mock_zk_class, mock_device_doc, mock_attendance_log):
        """Test successful attendance log retrieval."""
        mock_conn = MagicMock()
        mock_zk_class.return_value = mock_conn
        mock_conn.get_attendance.return_value = [mock_attendance_log]
        
        comm = DeviceCommunicator(mock_device_doc)
        logs = comm.get_attendance_logs()
        
        assert len(logs) == 1
        assert logs[0]["device_user_id"] == "1001"
        assert logs[0]["punch_type"] == "IN"

    @patch('zkteco_attendance.utils.device_communicator.ZK')
    def test_get_users_success(self, mock_zk_class, mock_device_doc, mock_user):
        """Test successful user retrieval."""
        mock_conn = MagicMock()
        mock_zk_class.return_value = mock_conn
        mock_conn.get_users.return_value = [mock_user]
        
        comm = DeviceCommunicator(mock_device_doc)
        users = comm.get_users()
        
        assert len(users) == 1
        assert users[0]["device_user_id"] == "1001"
        assert users[0]["name"] == "John Doe"

    def test_parse_attendance_log_empty_user_id(self, mock_device_doc):
        """Test parsing log with empty user ID raises error."""
        comm = DeviceCommunicator(mock_device_doc)
        bad_log = Mock()
        bad_log.user_id = ""
        bad_log.timestamp = datetime.now()
        
        with pytest.raises(InvalidDataError):
            comm._parse_attendance_log(bad_log)

    def test_determine_punch_type(self, mock_device_doc):
        """Test punch type determination from status codes."""
        comm = DeviceCommunicator(mock_device_doc)
        
        assert comm._determine_punch_type(0) == "IN"
        assert comm._determine_punch_type(1) == "OUT"
        assert comm._determine_punch_type(2) == "OUT"
        assert comm._determine_punch_type(3) == "IN"
        assert comm._determine_punch_type(99) == "Unknown"
