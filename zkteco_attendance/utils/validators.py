# Copyright (c) 2024 Your Organization
# MIT License

"""
Validation utilities for ZKTeco Attendance Integration.
"""

import re
import ipaddress
from typing import Optional

import frappe
from frappe import _


def validate_ip_address(ip: str) -> bool:
    """
    Validate IP address format.
    
    Args:
        ip: IP address string
        
    Returns:
        True if valid
        
    Raises:
        frappe.ValidationError: If invalid
    """
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        frappe.throw(_("Invalid IP address: {0}").format(ip))


def validate_port(port: int) -> bool:
    """
    Validate port number.
    
    Args:
        port: Port number
        
    Returns:
        True if valid
        
    Raises:
        frappe.ValidationError: If invalid
    """
    if not 1 <= port <= 65535:
        frappe.throw(_("Port must be between 1 and 65535"))
    return True


def validate_network_range(network: str) -> bool:
    """
    Validate network range in CIDR notation.
    
    Args:
        network: Network range string (e.g., "192.168.1.0/24")
        
    Returns:
        True if valid
        
    Raises:
        frappe.ValidationError: If invalid
    """
    try:
        ipaddress.ip_network(network, strict=False)
        return True
    except ValueError:
        frappe.throw(_("Invalid network range: {0}").format(network))


def validate_date_range(from_date: str, to_date: str, max_days: int = 90) -> bool:
    """
    Validate date range.
    
    Args:
        from_date: Start date
        to_date: End date
        max_days: Maximum allowed days in range
        
    Returns:
        True if valid
        
    Raises:
        frappe.ValidationError: If invalid
    """
    from_dt = frappe.utils.get_datetime(from_date)
    to_dt = frappe.utils.get_datetime(to_date)
    
    if to_dt < from_dt:
        frappe.throw(_("End date must be after start date"))
    
    days_diff = (to_dt - from_dt).days
    if days_diff > max_days:
        frappe.throw(_("Date range cannot exceed {0} days").format(max_days))
    
    return True
