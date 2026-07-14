# Copyright (c) 2026 Eslam Zedan
# MIT License

"""
Device communication layer for ZKTeco biometric devices.

Handles all direct communication with ZKTeco devices using pyzk library.
Implements connection pooling, retries, and error handling.
"""

import socket
import logging
from datetime import datetime
from typing import Any, Optional
from contextlib import contextmanager

import frappe
from frappe import _
from frappe.utils import now_datetime

from ..constants import (
    DEFAULT_PORT,
    CONNECTION_TIMEOUT,
    READ_TIMEOUT,
    MAX_RETRIES,
    RETRY_DELAY,
)
from ..exceptions import (
    DeviceConnectionError,
    DeviceTimeoutError,
    DeviceAuthenticationError,
    DeviceCommunicationError,
    InvalidDataError,
    ErrorCodes,
)

logger = logging.getLogger(__name__)


class DeviceCommunicator:
    """
    Handles communication with ZKTeco biometric devices.
    
    This class provides a robust interface for:
    - Connection management with retries
    - Attendance log retrieval
    - User data retrieval
    - Device information retrieval
    - Connection testing
    
    Attributes:
        device_ip: IP address of the device
        device_port: Port number for communication
        device_name: Name/identifier of the device in ERPNext
        password: Optional device password
    """

    def __init__(self, device_doc: Any) -> None:
        """
        Initialize DeviceCommunicator with device configuration.
        
        Args:
            device_doc: Biometric Device document object
        """
        self.device_ip: str = device_doc.device_ip
        self.device_port: int = device_doc.device_port or DEFAULT_PORT
        self.device_name: str = device_doc.name
        self.device_model: str = device_doc.device_model or "Unknown"
        self.password: Optional[int] = None
        
        # Parse password if provided (ZKTeco uses integer passwords)
        if device_doc.get("password"):
            try:
                self.password = int(device_doc.password)
            except (ValueError, TypeError):
                self.password = 0
        
        self._connection: Any = None

    @contextmanager
    def get_connection(self):
        """
        Context manager for device connection.
        
        Yields:
            ZK connection object
            
        Raises:
            DeviceConnectionError: If connection fails after retries
        """
        from zk import ZK
        
        conn = None
        last_error = None
        
        for attempt in range(MAX_RETRIES):
            try:
                conn = ZK(
                    ip=self.device_ip,
                    port=self.device_port,
                    timeout=CONNECTION_TIMEOUT,
                    password=self.password,
                    force_udp=False,
                    ommit_ping=False,
                )
                conn.connect()
                conn.disable_device()
                self._connection = conn
                logger.info(
                    f"Connected to device {self.device_ip}:{self.device_port} "
                    f"(attempt {attempt + 1})"
                )
                yield conn
                return
                
            except socket.timeout as e:
                last_error = e
                logger.warning(
                    f"Connection timeout to {self.device_ip} "
                    f"(attempt {attempt + 1}/{MAX_RETRIES})"
                )
                if attempt < MAX_RETRIES - 1:
                    import time
                    time.sleep(RETRY_DELAY)
                    
            except Exception as e:
                last_error = e
                logger.error(
                    f"Connection error to {self.device_ip}: {str(e)} "
                    f"(attempt {attempt + 1}/{MAX_RETRIES})"
                )
                if attempt < MAX_RETRIES - 1:
                    import time
                    time.sleep(RETRY_DELAY)
                    
            finally:
                if conn:
                    try:
                        conn.enable_device()
                        conn.disconnect()
                    except Exception:
                        pass
        
        raise DeviceConnectionError(
            device_ip=self.device_ip,
            device_port=self.device_port,
            reason=str(last_error) if last_error else "Max retries exceeded"
        )

    def test_connection(self) -> dict[str, Any]:
        """
        Test connection to the device.
        
        Returns:
            Dictionary with device information if successful
            
        Raises:
            DeviceConnectionError: If connection fails
            DeviceTimeoutError: If connection times out
        """
        with self.get_connection() as conn:
            device_info = conn.get_device_info()
            firmware_version = conn.get_firmware_version()
            
            return {
                "device_ip": self.device_ip,
                "device_port": self.device_port,
                "serial_number": device_info.get("serial_number", "Unknown"),
                "device_model": self.device_model,
                "firmware_version": firmware_version,
                "platform": device_info.get("platform", "Unknown"),
                "mac_address": device_info.get("mac_address", "Unknown"),
                "users_count": conn.get_user_count(),
                "log_count": conn.get_attendance_count(),
                "connected_at": now_datetime().isoformat(),
            }

    def get_attendance_logs(
        self,
        from_timestamp: Optional[datetime] = None
    ) -> list[dict[str, Any]]:
        """
        Retrieve attendance logs from the device.
        
        Args:
            from_timestamp: Only fetch logs after this timestamp
            
        Returns:
            List of attendance log dictionaries
            
        Raises:
            DeviceConnectionError: If connection fails
            DeviceTimeoutError: If operation times out
            DeviceCommunicationError: If there's a communication error
            InvalidDataError: If received data is invalid
        """
        logs: list[dict[str, Any]] = []
        
        with self.get_connection() as conn:
            try:
                if from_timestamp:
                    attendance = conn.get_attendance(since=from_timestamp)
                else:
                    attendance = conn.get_attendance()
                
                for log in attendance:
                    try:
                        log_data = self._parse_attendance_log(log)
                        logs.append(log_data)
                    except InvalidDataError as e:
                        logger.warning(
                            f"Skipping invalid attendance log: {e.message}"
                        )
                        continue
                        
                logger.info(
                    f"Retrieved {len(logs)} attendance logs from {self.device_ip}"
                )
                return logs
                
            except socket.timeout:
                raise DeviceTimeoutError(
                    device_ip=self.device_ip,
                    operation="get_attendance",
                    timeout_seconds=READ_TIMEOUT
                )
            except Exception as e:
                raise DeviceCommunicationError(
                    device_ip=self.device_ip,
                    operation="get_attendance",
                    reason=str(e)
                )

    def get_users(self) -> list[dict[str, Any]]:
        """
        Retrieve user data from the device.
        
        Returns:
            List of user dictionaries
            
        Raises:
            DeviceConnectionError: If connection fails
            DeviceCommunicationError: If there's a communication error
        """
        users: list[dict[str, Any]] = []
        
        with self.get_connection() as conn:
            try:
                device_users = conn.get_users()
                
                for user in device_users:
                    try:
                        user_data = self._parse_user_data(user)
                        users.append(user_data)
                    except InvalidDataError as e:
                        logger.warning(f"Skipping invalid user: {e.message}")
                        continue
                        
                logger.info(
                    f"Retrieved {len(users)} users from {self.device_ip}"
                )
                return users
                
            except socket.timeout:
                raise DeviceTimeoutError(
                    device_ip=self.device_ip,
                    operation="get_users",
                    timeout_seconds=READ_TIMEOUT
                )
            except Exception as e:
                raise DeviceCommunicationError(
                    device_ip=self.device_ip,
                    operation="get_users",
                    reason=str(e)
                )

    def get_device_time(self) -> datetime:
        """
        Get current device time.
        
        Returns:
            Device datetime object
            
        Raises:
            DeviceConnectionError: If connection fails
        """
        with self.get_connection() as conn:
            return conn.get_time()

    def set_device_time(self, dt: Optional[datetime] = None) -> bool:
        """
        Set device time.
        
        Args:
            dt: Datetime to set (default: current time)
            
        Returns:
            True if successful
            
        Raises:
            DeviceConnectionError: If connection fails
        """
        with self.get_connection() as conn:
            if dt is None:
                dt = datetime.now()
            conn.set_time(dt)
            return True

    def clear_attendance_logs(self) -> bool:
        """
        Clear all attendance logs from device.
        
        Returns:
            True if successful
            
        Raises:
            DeviceConnectionError: If connection fails
            DeviceCommunicationError: If operation fails
        """
        with self.get_connection() as conn:
            try:
                conn.clear_attendance_log()
                logger.info(f"Cleared attendance logs from {self.device_ip}")
                return True
            except Exception as e:
                raise DeviceCommunicationError(
                    device_ip=self.device_ip,
                    operation="clear_attendance_log",
                    reason=str(e)
                )

    def _parse_attendance_log(self, log: Any) -> dict[str, Any]:
        """
        Parse a single attendance log from device format.
        
        Args:
            log: Raw log object from pyzk
            
        Returns:
            Parsed log dictionary
            
        Raises:
            InvalidDataError: If log data is invalid
        """
        try:
            user_id = str(log.user_id).strip()
            if not user_id:
                raise InvalidDataError(
                    data=log,
                    reason="Empty user ID"
                )
            
            timestamp = log.timestamp
            if not timestamp:
                raise InvalidDataError(
                    data=log,
                    reason="Invalid timestamp"
                )
            
            # Determine punch type based on device status
            # ZKTeco uses status codes:
            # 0 = Check-In, 1 = Check-Out, 2 = Break-Out, 3 = Break-In, etc.
            status = getattr(log, 'status', 0)
            punch_type = self._determine_punch_type(status)
            
            return {
                "device_user_id": user_id,
                "timestamp": timestamp,
                "punch_type": punch_type,
                "status_code": status,
                "verified": getattr(log, 'verified', 0),
                "work_code": getattr(log, 'work_code', 0),
            }
            
        except InvalidDataError:
            raise
        except Exception as e:
            raise InvalidDataError(
                data=log,
                reason=f"Parse error: {str(e)}"
            )

    def _parse_user_data(self, user: Any) -> dict[str, Any]:
        """
        Parse a single user record from device format.
        
        Args:
            user: Raw user object from pyzk
            
        Returns:
            Parsed user dictionary
            
        Raises:
            InvalidDataError: If user data is invalid
        """
        try:
            user_id = str(user.user_id).strip()
            if not user_id:
                raise InvalidDataError(
                    data=user,
                    reason="Empty user ID"
                )
            
            name = getattr(user, 'name', '')
            # Handle encoding issues with names
            if isinstance(name, bytes):
                try:
                    name = name.decode('utf-8')
                except UnicodeDecodeError:
                    try:
                        name = name.decode('latin-1')
                    except:
                        name = user_id
            
            return {
                "device_user_id": user_id,
                "name": str(name).strip(),
                "privilege": getattr(user, 'privilege', 0),
                "password": getattr(user, 'password', ''),
                "group_id": getattr(user, 'group_id', ''),
                "user_id": getattr(user, 'uid', 0),
            }
            
        except InvalidDataError:
            raise
        except Exception as e:
            raise InvalidDataError(
                data=user,
                reason=f"Parse error: {str(e)}"
            )

    def _determine_punch_type(self, status_code: int) -> str:
        """
        Determine punch type from device status code.
        
        Args:
            status_code: Status code from device
            
        Returns:
            String representation of punch type
        """
        # Common ZKTeco status codes
        punch_type_map = {
            0: "IN",      # Check-In
            1: "OUT",     # Check-Out
            2: "OUT",     # Break-Out
            3: "IN",      # Break-In
            4: "OUT",     # Overtime-Out
        }
        
        return punch_type_map.get(status_code, "Unknown")


def discover_devices(network_range: str, timeout: int = 2) -> list[dict[str, Any]]:
    """
    Discover ZKTeco devices on a network.
    
    Args:
        network_range: IP range in CIDR notation (e.g., "192.168.1.0/24")
        timeout: Connection timeout per IP
        
    Returns:
        List of discovered device information
    """
    import ipaddress
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from zk import ZK
    
    discovered_devices: list[dict[str, Any]] = []
    
    try:
        network = ipaddress.ip_network(network_range, strict=False)
    except ValueError as e:
        frappe.throw(_("Invalid network range: {0}").format(str(e)))
    
    def check_ip(ip: str) -> Optional[dict[str, Any]]:
        """Check if a ZKTeco device exists at the given IP."""
        try:
            zk = ZK(ip, port=DEFAULT_PORT, timeout=timeout)
            conn = zk.connect()
            try:
                device_info = conn.get_device_info()
                return {
                    "ip": ip,
                    "port": DEFAULT_PORT,
                    "serial_number": device_info.get("serial_number", ""),
                    "model": device_info.get("model", ""),
                    "firmware": conn.get_firmware_version(),
                    "mac_address": device_info.get("mac_address", ""),
                }
            finally:
                conn.disconnect()
        except Exception:
            return None
    
    # Use thread pool for parallel scanning
    ips = [str(ip) for ip in network.hosts()]
    
    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = {executor.submit(check_ip, ip): ip for ip in ips}
        
        for future in as_completed(futures):
            result = future.result()
            if result:
                discovered_devices.append(result)
                logger.info(f"Discovered ZKTeco device at {result['ip']}")
    
    logger.info(
        f"Device discovery complete. Found {len(discovered_devices)} devices"
    )
    return discovered_devices
