/**
 * ZKTeco Attendance Integration - Client Side Scripts
 */

frappe.pages['biometric-attendance'].on_page_load = function(wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Biometric Attendance Dashboard',
        single_column: true
    });
    
    // Load dashboard data
    load_dashboard_data(page);
    
    // Set up refresh interval
    setInterval(function() {
        load_dashboard_data(page);
    }, 60000);
};

function load_dashboard_data(page) {
    frappe.call({
        method: 'zkteco_attendance.api.get_dashboard_data',
        callback: function(r) {
            if (r.message) {
                render_dashboard(page, r.message);
            }
        }
    });
}

function render_dashboard(page, data) {
    // Update number cards
    $('#connected-devices').text(data.devices.active + ' / ' + data.devices.total);
    $('#today-punches').text(data.today_punches);
    $('#sync-failures').text(data.sync_failures);
    $('#unmapped-users').text(data.unmapped_employees);
    
    // Update log status
    $('#logs-processed').text(data.log_status.processed);
    $('#logs-pending').text(data.log_status.pending);
    $('#logs-failed').text(data.log_status.failed);
    
    // Render recent syncs table
    render_sync_table(page, data.recent_syncs);
}

function render_sync_table(page, syncs) {
    var html = '<table class="table table-bordered table-hover">' +
        '<thead><tr>' +
        '<th>Device</th>' +
        '<th>Start Time</th>' +
        '<th>Status</th>' +
        '<th>Downloaded</th>' +
        '<th>Imported</th>' +
        '</tr></thead><tbody>';
    
    syncs.forEach(function(sync) {
        var status_class = 'sync-status-' + sync.status.toLowerCase().replace(' ', '-');
        html += '<tr>' +
            '<td>' + sync.device + '</td>' +
            '<td>' + sync.sync_start + '</td>' +
            '<td><span class="badge ' + status_class + '">' + sync.status + '</span></td>' +
            '<td>' + sync.records_downloaded + '</td>' +
            '<td>' + sync.records_imported + '</td>' +
            '</tr>';
    });
    
    html += '</tbody></table>';
    $('#sync-table-container').html(html);
}

// Biometric Device Form Scripts
frappe.ui.form.on('Biometric Device', {
    refresh: function(frm) {
        if (frm.doc.device_ip) {
            frm.add_custom_button(__('Test Connection'), function() {
                test_device_connection(frm);
            }, __('Actions'));
            
            frm.add_custom_button(__('Sync Now'), function() {
                trigger_manual_sync(frm);
            }, __('Actions'));
            
            frm.add_custom_button(__('Download Users'), function() {
                download_device_users(frm);
            }, __('Actions'));
        }
        
        frm.add_custom_button(__('View Logs'), function() {
            frappe.set_route('List', 'Biometric Attendance Log', {
                device: frm.doc.name
            });
        }, __('Links'));
        
        frm.add_custom_button(__('View Sync History'), function() {
            frappe.set_route('List', 'Biometric Sync Log', {
                device: frm.doc.name
            });
        }, __('Links'));
    },
    
    device_ip: function(frm) {
        // Auto-detect if IP is valid
        if (frm.doc.device_ip) {
            var ipRegex = /^(\d{1,3}\.){3}\d{1,3}$/;
            if (!ipRegex.test(frm.doc.device_ip)) {
                frm.set_df_property('device_ip', 'description', 'Invalid IP format');
            } else {
                frm.set_df_property('device_ip', 'description', '');
            }
        }
    }
});

function test_device_connection(frm) {
    frappe.call({
        method: 'zkteco_attendance.api.test_device_connection',
        args: {
            device_name: frm.doc.name
        },
        btn: frm.page.btn_primary,
        callback: function(r) {
            if (r.message) {
                if (r.message.success) {
                    frappe.msgprint(
                        __('Connection successful! Serial: {0}, Firmware: {1}, Users: {2}, Logs: {3}', [
                            r.message.device_info.serial_number || 'N/A',
                            r.message.device_info.firmware_version || 'N/A',
                            r.message.device_info.users_count || 'N/A',
                            r.message.device_info.log_count || 'N/A'
                        ]),
                        __('Success'),
                        'green'
                    );
                    frm.reload_doc();
                } else {
                    frappe.msgprint(
                        __('Connection failed: {0} (Error: {1})', [
                            r.message.message,
                            r.message.error_code
                        ]),
                        __('Error'),
                        'red'
                    );
                }
            }
        },
        error: function(r) {
            frappe.msgprint(__('An error occurred while testing connection'), __('Error'), 'red');
        }
    });
}

function trigger_manual_sync(frm) {
    frappe.confirm(
        __('Are you sure you want to trigger a manual sync for this device?'),
        function() {
            frappe.call({
                method: 'zkteco_attendance.api.sync_device',
                args: {
                    device_name: frm.doc.name,
                    force: true
                },
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frappe.msgprint(
                            __('Sync job enqueued. Job ID: {0}', [r.message.job_id]),
                            __('Sync Started'),
                            'blue'
                        );
                    }
                }
            });
        }
    );
}

function download_device_users(frm) {
    frappe.call({
        method: 'zkteco_attendance.utils.device_communicator.DeviceCommunicator.get_users',
        args: {
            device_doc: frm.doc
        },
        callback: function(r) {
            if (r.message) {
                frappe.msgprint(
                    __('Found {0} users on device', [r.message.length]),
                    __('Users Downloaded'),
                    'green'
                );
            }
        },
        error: function(r) {
            frappe.msgprint(__('Failed to download users'), __('Error'), 'red');
        }
    });
}

// Biometric Employee Mapping Form Scripts
frappe.ui.form.on('Biometric Employee Mapping', {
    refresh: function(frm) {
        frm.add_custom_button(__('Auto Map All'), function() {
            auto_map_all_employees(frm);
        });
    },
    
    employee: function(frm) {
        if (frm.doc.employee) {
            frappe.db.get_value('Employee', frm.doc.employee, 'employee_name', function(r) {
                if (r) {
                    frm.set_value('employee_name', r.message.employee_name);
                }
            });
        }
    }
});

function auto_map_all_employees(frm) {
    frappe.call({
        method: 'zkteco_attendance.api.auto_map_employees',
        callback: function(r) {
            if (r.message) {
                frappe.msgprint(
                    __('Auto-mapping complete. Mapped: {0}, Unmapped: {1}, Suggestions: {2}', [
                        r.message.mapped,
                        r.message.unmapped,
                        r.message.suggestions.length
                    ]),
                    __('Auto Map Result'),
                    'green'
                );
            }
        }
    });
}

// Utility function to format datetime
function format_datetime(dt) {
    if (!dt) return '';
    var date = new Date(dt);
    return date.toLocaleString();
}
