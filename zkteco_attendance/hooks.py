# Copyright (c) 2024 Your Organization
# MIT License

from . import __version__ as app_version

app_name = "zkteco_attendance"
app_title = "ZKTeco Attendance"
app_publisher = "Eslam Zedan"
app_description = "ZKTeco Biometric Attendance Integration for ERPNext v15"
app_email = "EslamZeeddaan@gmail.com"
app_license = "MIT"

# Version
app_version = app_version

# Required Apps
required_apps = ["frappe", "hrms"]

# Modules
modules = {
    "ZKTeco Attendance": {
        "color": "#3498DB",
        "icon": "octicon octicon-device-desktop",
        "type": "module"
    }
}

# DocType Events
doc_events = {
    "Employee": {
        "after_insert": "zkteco_attendance.overrides.employee.after_employee_insert",
        "on_update": "zkteco_attendance.overrides.employee.on_employee_update",
        "before_delete": "zkteco_attendance.overrides.employee.before_employee_delete",
    }
}

# Scheduler Events
scheduler_events = {
    "all": [
        {
            "scheduler_type": "all",
            "event": "zkteco_attendance.tasks.sync_tasks.sync_all_devices_5min",
            "frequency": "5 Min",
        },
        {
            "scheduler_type": "all",
            "event": "zkteco_attendance.tasks.sync_tasks.sync_all_devices_15min",
            "frequency": "15 Min",
        },
        {
            "scheduler_type": "daily",
            "event": "zkteco_attendance.tasks.reconciliation_tasks.daily_reconciliation",
            "time": "00:30:00",
        },
        {
            "scheduler_type": "daily",
            "event": "zkteco_attendance.tasks.sync_tasks.cleanup_old_sync_logs",
            "time": "02:00:00",
        },
    ]
}

# Override Standard Controllers
override_doctype_class = {}

# Website Routes
website_route_rules = []

# API Endpoints
api = {}

# Installed Apps
installed_apps = []

# Fixtures
fixtures = [
    {
        "dt": "Custom Field",
        "filters": [["dt", "in", ["Employee", "Employee Checkin"]]]
    },
    {
        "dt": "Role",
        "filters": [["name", "in", ["ZKTeco Manager", "ZKTeco User"]]]
    },
]

# Translation
translation_modules = ["zkteco_attendance"]

# Workspace
workspace = "Biometric Attendance"
