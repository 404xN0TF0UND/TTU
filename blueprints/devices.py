"""devices blueprint - routes extracted verbatim from app.py (mechanical split, no behavior change)."""
from flask import Blueprint
from core import *  # shared app, helpers, constants, flask names

devices_bp = Blueprint('devices', __name__)


@devices_bp.route('/devices')
def manage_devices():
    devices = load_devices()
    return render_template('manage_devices.html', devices=devices)


@devices_bp.route('/devices/add', methods=['GET', 'POST'])
def add_device():
    if request.method == 'POST':
        device_name = request.form.get('device_name', '').strip()
        ip_address = request.form.get('ip_address', '').strip()
        device_type = request.form.get('device_type', '').strip()
        username = request.form.get('username', '').strip()
        description = request.form.get('description', '').strip()
        
        if not device_name or not ip_address:
            flash('Device name and IP address are required.')
            return redirect(url_for('devices.add_device'))
        
        devices = load_devices()
        devices[device_name] = {
            'ip_address': ip_address,
            'device_type': device_type,
            'username': username,
            'description': description,
            'added_date': datetime.now().isoformat()
        }
        save_devices(devices)
        flash(f'Device {device_name} added successfully.')
        return redirect(url_for('devices.manage_devices'))
    
    return render_template('add_device.html')


@devices_bp.route('/devices/delete/<device_name>', methods=['POST'])
def delete_device(device_name):
    devices = load_devices()
    if device_name in devices:
        del devices[device_name]
        save_devices(devices)
        flash(f'Device {device_name} deleted successfully.')
    return redirect(url_for('devices.manage_devices'))


@devices_bp.route('/devices/clear-all', methods=['POST'])
def clear_all_devices():
    """Clear all devices from the device list"""
    try:
        # Delete the devices.json file to clear all devices
        if os.path.exists(DEVICES_FILE):
            os.remove(DEVICES_FILE)
        flash('All devices have been cleared successfully.')
    except Exception as e:
        flash(f'Error clearing devices: {str(e)}')
    return redirect(url_for('devices.manage_devices'))


@devices_bp.route('/devices/backup/<device_name>', methods=['POST'])
def backup_config(device_name):
    """Backup device configuration"""
    devices = load_devices()
    if device_name not in devices:
        flash(f'Device {device_name} not found.')
        return redirect(url_for('devices.manage_devices'))
    
    device_info = devices[device_name]
    device_type = get_device_type(device_name)
    
    # Commands to get configuration based on device type
    backup_commands = {
        'ciena_os': ['show running-config'],
        'cisco_xr': ['show running-config'],
        'cisco_ios': ['show running-config'],
        'nokia_sros': ['show configuration'],
        'juniper': ['show configuration']
    }
    
    commands = backup_commands.get(device_type, ['show running-config'])
    
    result = execute_command_on_device(device_name, commands)
    
    if result['success']:
        # Save configuration backup
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{device_name}_config_backup_{timestamp}.txt"
        filepath = os.path.join(SAVED_NOTES_DIR, filename)
        
        note_content = f"# Configuration Backup - {device_name}\n"
        note_content += f"# Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        note_content += f"# Device Type: {device_type}\n\n"
        
        for cmd_result in result['results']:
            note_content += f"## Command: {cmd_result['command']}\n"
            note_content += f"## Output:\n{cmd_result['output']}\n\n"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(note_content)
        
        # Save metadata
        metadata = load_notes_metadata()
        metadata[filename] = {
            'created': datetime.now().isoformat(),
            'modified': datetime.now().isoformat(),
            'tags': ['config_backup', device_name.lower()],
            'type': 'config_backup_note',
            'favorite': False
        }
        save_notes_metadata(metadata)
        
        flash(f'Configuration backup saved as {filename}')
    else:
        flash(f'Backup failed: {result["error"]}')
    
    return redirect(url_for('devices.manage_devices'))


@devices_bp.route('/devices/discover')
def device_discovery():
    """Device discovery from log analysis"""
    stats = get_device_discovery_stats()
    discovered_devices = discover_devices_from_logs()
    
    return render_template('device_discovery.html', 
                         stats=stats, 
                         discovered_devices=discovered_devices)


@devices_bp.route('/devices/discover/add/<device_name>')
def add_discovered_device(device_name):
    """Add a discovered device to the device list"""
    discovered_devices = discover_devices_from_logs()
    
    # Find the device in discovered list
    device_to_add = None
    for device in discovered_devices:
        if device['name'] == device_name:
            device_to_add = device
            break
    
    if not device_to_add:
        flash(f'Device {device_name} not found in discovery list', 'error')
        return redirect(url_for('devices.device_discovery'))
    
    # Store device data in localStorage for pre-filling the add device form
    device_data = {
        'name': device_to_add['name'],
        'ip_address': device_to_add['ip_address'],
        'device_type': device_to_add['device_type'],
        'username': device_to_add['username'],
        'description': device_to_add['description']
    }
    
    return render_template('add_discovered_device.html', 
                         device=device_to_add, 
                         device_data_json=device_data)


@devices_bp.route('/devices/discover/bulk-add', methods=['POST'])
def bulk_add_discovered_devices():
    """Bulk add multiple discovered devices"""
    try:
        selected_devices = request.form.getlist('selected_devices')
        discovered_devices = discover_devices_from_logs()
        
        added_count = 0
        existing_devices = load_devices()
        
        for device_name in selected_devices:
            # Find device in discovered list
            device_to_add = None
            for device in discovered_devices:
                if device['name'] == device_name:
                    device_to_add = device
                    break
            
            if device_to_add and device_name not in existing_devices:
                # Add to existing devices
                existing_devices[device_name] = {
                    'ip_address': device_to_add['ip_address'],
                    'device_type': device_to_add['device_type'],
                    'username': device_to_add['username'],
                    'description': device_to_add['description'],
                    'added_date': datetime.now().isoformat()
                }
                added_count += 1
        
        # Save updated device list
        save_devices(existing_devices)
        
        flash(f'Successfully added {added_count} devices to your device list!', 'success')
        return redirect(url_for('devices.manage_devices'))
        
    except Exception as e:
        flash(f'Error adding devices: {str(e)}', 'error')
        return redirect(url_for('devices.device_discovery'))


@devices_bp.route('/devices/discover/clear', methods=['POST'])
def clear_discovery_data():
    """Clear all discovered device data by rebuilding the logs index"""
    try:
        # Delete the logs index file to clear all discovery data
        if os.path.exists(LOGS_INDEX_FILE):
            os.remove(LOGS_INDEX_FILE)
        
        flash('All discovered device data has been cleared successfully.')
        return redirect(url_for('devices.device_discovery'))
    except Exception as e:
        flash(f'Error clearing discovery data: {str(e)}')
        return redirect(url_for('devices.device_discovery'))


@devices_bp.route('/devices/discover/auto-suggest')
def auto_suggest_devices():
    """Get auto-suggestions for device names based on logs"""
    query = request.args.get('q', '').lower()
    if not query:
        return jsonify([])
    
    discovered_devices = discover_devices_from_logs()
    suggestions = []
    
    for device in discovered_devices:
        if query in device['name'].lower():
            suggestions.append({
                'name': device['name'],
                'device_type': device['device_type'],
                'file_count': device['file_count'],
                'last_seen': device['last_seen']
            })
    
    # Limit to 10 suggestions
    return jsonify(suggestions[:10])
