"""Shared TTU core: Flask app object, config, and helper functions.
Routes live in blueprints/ (see app.py for registration).
"""
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, make_response, jsonify, session
import os
import urllib.parse
import subprocess
import json
from datetime import datetime, timedelta
import shutil
from netmiko import ConnectHandler, NetMikoTimeoutException, NetMikoAuthenticationException
import getpass
import re
from jinja2 import Template
# import threading
# import time


app = Flask(__name__)
import secrets as _secrets
app.secret_key = os.environ.get('TTU_SECRET_KEY') or _secrets.token_hex(32)

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), 'templates')
GENERATED_FORMS_DIR = os.path.join(TEMPLATES_DIR, 'generated_forms')
SAVED_NOTES_DIR = os.path.join(os.path.dirname(__file__), 'saved_notes')
SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), 'scripts')
NOTES_METADATA_FILE = os.path.join(SAVED_NOTES_DIR, 'notes_metadata.json')
TEMPLATES_METADATA_FILE = os.path.join(GENERATED_FORMS_DIR, 'templates_metadata.json')
DEVICES_FILE = os.path.join(os.path.dirname(__file__), 'devices.json')
LOGS_DIR = os.path.join(os.path.dirname(__file__), 'Logs', 'Logs')
LOGS_INDEX_FILE = os.path.join(os.path.dirname(__file__), 'logs_index.json')
LOGS_CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'logs_config.json')

os.makedirs(SAVED_NOTES_DIR, exist_ok=True)
os.makedirs(SCRIPTS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

def load_notes_metadata():
    if os.path.exists(NOTES_METADATA_FILE):
        try:
            with open(NOTES_METADATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            # Return empty dict if file is corrupted or doesn't exist
            return {}
    return {}

def save_notes_metadata(metadata):
    with open(NOTES_METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)

def fix_notes_metadata():
    """Fix existing notes metadata to include type field"""
    metadata = load_notes_metadata()
    updated = False
    
    for filename, meta in metadata.items():
        if isinstance(meta, dict) and 'type' not in meta:
            # If it's a quick note file, it should have 'type': 'quick_note'
            # Otherwise, it's a template note
            if filename.endswith('.txt'):
                # Check if it's a quick note by looking at the content
                filepath = os.path.join(SAVED_NOTES_DIR, filename)
                if os.path.exists(filepath):
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read()
                        # Quick notes are typically shorter and don't have structured field labels
                        # Template notes have structured content with field labels
                        if len(content.split('\n')) < 10 and not any(':' in line for line in content.split('\n')[:5]):
                            meta['type'] = 'quick_note'
                        else:
                            meta['type'] = 'template_note'
                        updated = True
                    except:
                        # Default to template_note if we can't read the file
                        meta['type'] = 'template_note'
                        updated = True
    
    if updated:
        save_notes_metadata(metadata)
    
    return updated

def load_templates_metadata():
    if os.path.exists(TEMPLATES_METADATA_FILE):
        with open(TEMPLATES_METADATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_templates_metadata(metadata):
    with open(TEMPLATES_METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)

# Device management
def load_devices():
    if os.path.exists(DEVICES_FILE):
        try:
            with open(DEVICES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            # Return empty dict if file is corrupted or doesn't exist
            return {}
    return {}

def save_devices(devices):
    with open(DEVICES_FILE, 'w', encoding='utf-8') as f:
        json.dump(devices, f, indent=2)

# Logs configuration management
def load_logs_config():
    """Load logs configuration including external folders"""
    if os.path.exists(LOGS_CONFIG_FILE):
        try:
            with open(LOGS_CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # Ensure required fields exist
                if 'external_folders' not in config:
                    config['external_folders'] = []
                if 'monitoring_enabled' not in config:
                    config['monitoring_enabled'] = False
                return config
        except (json.JSONDecodeError, FileNotFoundError):
            pass
    return {
        'external_folders': [],
        'monitoring_enabled': False
    }

def save_logs_config(config):
    """Save logs configuration"""
    with open(LOGS_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)

def check_for_new_logs():
    """Check external folders for new log files and update index if needed"""
    config = load_logs_config()
    
    if not config.get('monitoring_enabled', False):
        return False
    
    # Get current index
    current_index = load_logs_index()
    if not current_index:
        return False
    
    # Get list of all files in external folders
    external_files = set()
    for folder in config.get('external_folders', []):
        if not folder.get('enabled', True) or not os.path.exists(folder['path']):
            continue
            
        for root, dirs, files in os.walk(folder['path']):
            for file in files:
                if file.endswith('.txt'):
                    file_path = os.path.join(root, file)
                    folder_name = os.path.basename(folder['path'])
                    relative_path = os.path.join(folder_name, os.path.relpath(file_path, folder['path']))
                    external_files.add(relative_path)
    
    # Check if there are new files
    current_files = {f['path'] for f in current_index.get('files', [])}
    new_files = external_files - current_files
    
    if new_files:
        # Rebuild index to include new files
        new_index = scan_and_index_logs()
        save_logs_index(new_index)
        return True
    
    return False

def get_device_type(device_name):
    """Determine device type based on device name or IP"""
    device_lower = device_name.lower()
    if 'ciena' in device_lower or any(x in device_lower for x in ['cn3903', 'cn3916', 'cn3930', 'cn3924', '5160', '5170']):
        return 'ciena_os'
    elif 'asr9k' in device_lower or 'ncs5500' in device_lower:
        return 'cisco_xr'
    elif '7250' in device_lower or '7750' in device_lower:
        return 'nokia_sros'
    elif 'mx' in device_lower or 'acx' in device_lower:
        return 'juniper'
    else:
        return 'cisco_ios'  # Default fallback

def get_logout_command(device_type):
    """Get the appropriate logout command for a device type"""
    logout_commands = {
        'ciena_os': 'exit',
        'cisco_xr': 'exit',
        'cisco_ios': 'exit',
        'nokia_sros': 'logout',
        'juniper': 'exit'
    }
    return logout_commands.get(device_type, 'exit')  # Default to 'exit' if device type not found

def execute_command_on_device(device_name, commands, username=None, password=None):
    """Execute commands on a device using Netmiko with RADIUS authentication"""
    try:
        devices = load_devices()
        device_info = devices.get(device_name, {})
        
        if not device_info:
            return {'success': False, 'error': f'Device {device_name} not found in device list'}
        
        device_type = get_device_type(device_name)
        
        # Validate credentials are provided
        if not username or not password:
            return {'success': False, 'error': 'Username and password are required for SSH connection'}
        
        device_config = {
            'device_type': device_type,
            'host': device_info.get('ip_address', device_name),
            'username': username,
            'password': password,
            'port': 22,
            'timeout': 20,
            'global_delay_factor': 2,
        }
        
        with ConnectHandler(**device_config) as net_connect:
            results = []
            logout_command = get_logout_command(device_type)
            
            for i, command in enumerate(commands):
                try:
                    # Handle logout command specially to avoid prompt issues
                    if command.strip().lower() == logout_command.lower():
                        # For logout command, use send_command_timing to avoid waiting for specific prompt
                        output = net_connect.send_command_timing(command, strip_prompt=False)
                        # Add a small delay to ensure the logout command completes
                        import time
                        time.sleep(1)
                        results.append({
                            'command': command,
                            'output': output + '\nSession closed successfully.',
                            'success': True
                        })
                        # Break after logout command since session will be closed
                        break
                    else:
                        # For regular commands, use normal send_command
                        output = net_connect.send_command(command)
                        results.append({
                            'command': command,
                            'output': output,
                            'success': True
                        })
                except Exception as e:
                    results.append({
                        'command': command,
                        'output': f'Error: {str(e)}',
                        'success': False
                    })
            
            return {'success': True, 'results': results}
            
    except NetMikoTimeoutException:
        return {'success': False, 'error': f'Connection timeout to {device_name}'}
    except NetMikoAuthenticationException:
        return {'success': False, 'error': f'RADIUS authentication failed for {device_name}. Check your credentials.'}
    except Exception as e:
        return {'success': False, 'error': f'Connection error: {str(e)}'}

# Remove the background password rotation task
# password_thread = threading.Thread(target=check_password_rotation, daemon=True)
# password_thread.start()
















# --- Session credentials (one prompt per app run) --------------------------
# Held in module memory only — never written to disk, cleared on restart,
# TTL-bounded. Script pages fall back to these when form fields are empty.
SESSION_CREDS = {}
SESSION_CREDS_TTL = 8 * 3600  # a workday


def get_session_creds():
    if SESSION_CREDS and \
            time_module.time() - SESSION_CREDS['ts'] < SESSION_CREDS_TTL:
        return SESSION_CREDS['username'], SESSION_CREDS['password']
    SESSION_CREDS.clear()
    return None, None


def resolve_creds(form):
    """Form credentials win; fall back to session creds, then env username."""
    su, sp = get_session_creds()
    username = (form.get('username', '').strip() or su
                or os.environ.get('TTU_SSH_USER', ''))
    password = form.get('password', '') or sp or ''
    return username, password


@app.context_processor
def inject_creds_status():
    su, _ = get_session_creds()
    return {'creds_active': bool(su), 'creds_username': su or '',
            'default_username': su or os.environ.get('TTU_SSH_USER', '')}




# --- ITU grid converter (client-side tool) --------------------------------


# --- Nokia DWDM Retune (ITU-grid validated, confirm-gated) ----------------
PENDING_RETUNES = {}


def expire_pending_retunes():
    now = time_module.time()
    for k in [k for k, v in PENDING_RETUNES.items()
              if now - v['ts'] > PENDING_DISABLE_TTL]:
        PENDING_RETUNES.pop(k, None)




# --- Port Check (bulk, read-only) ----------------------------------------


# --- Port Disable (one-way, confirm-gated) -------------------------------
# Two-phase flow: "preview" does a read-only pre-state capture and shows the
# planned per-vendor sequence; "execute" requires the preview token plus a
# typed "DISABLE". Credentials for a pending preview live only in this
# in-memory dict (single-user localhost app), are popped on use, and expire.
import time as time_module

PENDING_DISABLES = {}
PENDING_DISABLE_TTL = 600  # seconds


def expire_pending_disables():
    now = time_module.time()
    for k in [k for k, v in PENDING_DISABLES.items()
              if now - v['ts'] > PENDING_DISABLE_TTL]:
        PENDING_DISABLES.pop(k, None)














# Device management routes




# Command execution routes



# Batch operations



# Configuration backup

# Enhanced password rotation management
# @app.route('/password-rotation')
# def password_rotation():
#     """Manage password rotation reminders and history"""
#     # Load password rotation data
#     password_file = os.path.join(os.path.dirname(__file__), 'password_rotation.json')
    
#     def load_password_data():
#         if os.path.exists(password_file):
#             with open(password_file, 'r', encoding='utf-8') as f:
#                 return json.load(f)
#         return {'devices': {}, 'settings': {'rotation_days': 72}}
    
#     def save_password_data(data):
#         with open(password_file, 'w', encoding='utf-8') as f:
#             json.dump(data, f, indent=2)
    
#     password_data = load_password_data()
    
#     if request.method == 'POST':
#         action = request.form.get('action')
        
#         if action == 'update_rotation':
#             rotation_days = int(request.form.get('rotation_days', 72))
#             password_data['settings']['rotation_days'] = rotation_days
#             save_password_data(password_data)
#             flash(f'Password rotation period updated to {rotation_days} days.')
            
#         elif action == 'mark_rotated':
#             device_name = request.form.get('device_name')
#             if device_name:
#                 password_data['devices'][device_name] = {
#                     'last_rotated': datetime.now().isoformat(),
#                     'next_rotation': (datetime.now() + timedelta(days=password_data['settings']['rotation_days'])).isoformat()
#                 }
#                 save_password_data(password_data)
#                 flash(f'Password rotation marked for {device_name}.')
        
#         return redirect(url_for('password_rotation'))
    
#     # Calculate days until rotation for each device
#     devices = load_devices()
#     rotation_status = {}
    
#     for device_name in devices:
#         device_data = password_data['devices'].get(device_name, {})
#         if device_data:
#             last_rotated = datetime.fromisoformat(device_data['last_rotated'])
#             next_rotation = datetime.fromisoformat(device_data['next_rotation'])
#             days_until = (next_rotation - datetime.now()).days
#             rotation_status[device_name] = {
#                 'last_rotated': last_rotated.strftime('%Y-%m-%d'),
#                 'next_rotation': next_rotation.strftime('%Y-%m-%d'),
#                 'days_until': days_until,
#                 'overdue': days_until < 0
#             }
#         else:
#             rotation_status[device_name] = {
#                 'last_rotated': 'Never',
#                 'next_rotation': 'Not set',
#                 'days_until': None,
#                 'overdue': False
#             }
    
#     return render_template('password_rotation.html', 
#                          rotation_status=rotation_status, 
#                          settings=password_data['settings'],
#                          devices=devices)



# Quick commands library
COMMANDS_FILE = os.path.join(os.path.dirname(__file__), 'command_library.json')

def load_command_library():
    """Load command library from JSON file"""
    if os.path.exists(COMMANDS_FILE):
        with open(COMMANDS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        # Create default command library
        default_commands = {
            'ciena': {
                'Basic': [
                    'show equipment',
                    'show interface {port}',
                    'show alarms',
                    'show performance {port}'
                ],
                'Troubleshooting': [
                    'show equipment ont interface {port} detail',
                    'show equipment ont interface {port} statistics',
                    'show equipment ont interface {port} optical-info',
                    'show equipment ont interface {port} alarms'
                ],
                'Configuration': [
                    'show running-config',
                    'show configuration interface {port}',
                    'show equipment ont interface {port} configuration'
                ]
            },
            'cisco': {
                'Basic': [
                    'show version',
                    'show interfaces {interface}',
                    'show ip interface brief',
                    'show ip route'
                ],
                'Troubleshooting': [
                    'show interface {interface} counters',
                    'show interface {interface} status',
                    'show logging',
                    'show ip bgp summary'
                ],
                'Configuration': [
                    'show running-config interface {interface}',
                    'show startup-config',
                    'show ip route {prefix}'
                ]
            },
            'nokia': {
                'Basic': [
                    'show version',
                    'show port {port}',
                    'show interface {interface}',
                    'show router interface'
                ],
                'Troubleshooting': [
                    'show port {port} statistics',
                    'show port {port} detail',
                    'show router status',
                    'show router bgp summary'
                ],
                'Configuration': [
                    'show configuration',
                    'show configuration port {port}',
                    'show configuration router interface {interface}'
                ]
            },
            'juniper': {
                'Basic': [
                    'show version',
                    'show interfaces {interface}',
                    'show route',
                    'show system storage'
                ],
                'Troubleshooting': [
                    'show interface {interface} detail',
                    'show route {prefix}',
                    'show bgp summary',
                    'show system alarms'
                ],
                'Configuration': [
                    'show configuration interfaces {interface}',
                    'show configuration routing-options',
                    'show configuration protocols bgp'
                ]
            }
        }
        save_command_library(default_commands)
        return default_commands

def save_command_library(commands):
    """Save command library to JSON file"""
    with open(COMMANDS_FILE, 'w', encoding='utf-8') as f:
        json.dump(commands, f, indent=2)







def scan_and_index_logs():
    """Scan and index all log files for search functionality"""
    logs_index = {
        'total_files': 0,
        'device_types': {},
        'common_commands': {},
        'date_range': {'earliest': None, 'latest': None},
        'devices': {},
        'files': []
    }
    
    # Load logs configuration
    logs_config = load_logs_config()
    
    # List of folders to scan (default + external)
    folders_to_scan = [LOGS_DIR] + [folder['path'] for folder in logs_config.get('external_folders', [])]
    
    for folder_path in folders_to_scan:
        if not os.path.exists(folder_path):
            continue
            
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if file.endswith('.txt'):
                    file_path = os.path.join(root, file)
                    
                    # Determine relative path based on source folder
                    if folder_path == LOGS_DIR:
                        relative_path = os.path.relpath(file_path, LOGS_DIR)
                    else:
                        # For external folders, use the folder name as prefix
                        folder_name = os.path.basename(folder_path)
                        relative_path = os.path.join(folder_name, os.path.relpath(file_path, folder_path))
                
                # Parse filename for metadata
                try:
                    # Extract timestamp and device info from filename
                    # Format: YYYY-MM-DD-HH-MM-SS.mmm__device_name(device_name).txt
                    parts = file.replace('.txt', '').split('__')
                    if len(parts) >= 2:
                        timestamp_str = parts[0]
                        device_info = parts[1]
                        
                        # Parse timestamp
                        timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d-%H-%M-%S.%f')
                        
                        # Extract device name
                        device_name = device_info.split('(')[0] if '(' in device_info else device_info
                        
                        # Determine device type
                        device_type = 'unknown'
                        if device_name.startswith('ce-'):
                            device_type = 'ciena_cpe'
                        elif device_name.startswith('mtg-'):
                            device_type = 'ciena_metro'
                        elif device_name.startswith('nid-'):
                            device_type = 'ciena_nid'
                        elif device_name.startswith('soag'):
                            device_type = 'nokia_soag'
                        elif device_name.startswith('ceg'):
                            device_type = 'nokia_ceg'
                        
                        # Read file content for command analysis
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                
                            # Extract commands (lines ending with > or #)
                            commands = re.findall(r'[^>#]*[>#]\s*([^\n]+)', content)
                            
                            # Count common commands
                            for cmd in commands:
                                cmd_clean = cmd.strip().split()[0] if cmd.strip() else ''
                                if cmd_clean:
                                    logs_index['common_commands'][cmd_clean] = logs_index['common_commands'].get(cmd_clean, 0) + 1
                            
                        except Exception as e:
                            content = ""
                            commands = []
                        
                        # Update index
                        logs_index['total_files'] += 1
                        logs_index['device_types'][device_type] = logs_index['device_types'].get(device_type, 0) + 1
                        
                        if device_name not in logs_index['devices']:
                            logs_index['devices'][device_name] = {
                                'type': device_type,
                                'file_count': 0,
                                'first_seen': timestamp.isoformat(),
                                'last_seen': timestamp.isoformat()
                            }
                        
                        logs_index['devices'][device_name]['file_count'] += 1
                        logs_index['devices'][device_name]['last_seen'] = timestamp.isoformat()
                        
                        # Update date range
                        if not logs_index['date_range']['earliest'] or timestamp < datetime.fromisoformat(logs_index['date_range']['earliest']):
                            logs_index['date_range']['earliest'] = timestamp.isoformat()
                        if not logs_index['date_range']['latest'] or timestamp > datetime.fromisoformat(logs_index['date_range']['latest']):
                            logs_index['date_range']['latest'] = timestamp.isoformat()
                        
                        # Add file entry
                        logs_index['files'].append({
                            'filename': file,
                            'path': relative_path,
                            'full_path': file_path,
                            'device_name': device_name,
                            'device_type': device_type,
                            'timestamp': timestamp.isoformat(),
                            'size': os.path.getsize(file_path),
                            'command_count': len(commands)
                        })
                        
                except Exception as e:
                    # Skip files that don't match expected format
                    continue
    
    # Sort files by timestamp
    logs_index['files'].sort(key=lambda x: x['timestamp'], reverse=True)
    
    # Sort common commands by frequency
    logs_index['common_commands'] = dict(sorted(logs_index['common_commands'].items(), 
                                               key=lambda x: x[1], reverse=True))
    
    return logs_index

def save_logs_index(index):
    """Save the logs index to file"""
    with open(LOGS_INDEX_FILE, 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2)

def load_logs_index():
    """Load the logs index from file"""
    if os.path.exists(LOGS_INDEX_FILE):
        with open(LOGS_INDEX_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def search_logs(query, device_type=None, date_from=None, date_to=None, device_name=None):
    """Search through indexed logs"""
    index = load_logs_index()
    if not index:
        return []
    
    results = []
    query_lower = query.lower()
    
    for file_info in index['files']:
        # Apply filters
        if device_type and file_info['device_type'] != device_type:
            continue
        if device_name and device_name.lower() not in file_info['device_name'].lower():
            continue
        if date_from:
            file_date = datetime.fromisoformat(file_info['timestamp'])
            if file_date < datetime.fromisoformat(date_from):
                continue
        if date_to:
            file_date = datetime.fromisoformat(file_info['timestamp'])
            if file_date > datetime.fromisoformat(date_to):
                continue
        
        # Search in filename and device name
        if query_lower in file_info['filename'].lower() or query_lower in file_info['device_name'].lower():
            results.append(file_info)
            continue
        
        # Search in file content
        try:
            with open(file_info['full_path'], 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                if query_lower in content.lower():
                    results.append(file_info)
        except:
            continue
    
    return results[:100]  # Limit results









def generate_smart_template_suggestions():
    """Generate smart template suggestions based on log analysis"""
    index = load_logs_index()
    if not index:
        return []
    
    suggestions = []
    
    # Analyze most common commands by device type
    device_type_commands = {}
    for file_info in index['files']:
        device_type = file_info['device_type']
        if device_type not in device_type_commands:
            device_type_commands[device_type] = {}
        
        # This is a simplified analysis - in a real implementation, 
        # we'd parse the actual commands from the file content
        # For now, we'll use the common commands from the index
        for cmd, count in index['common_commands'].items():
            if cmd not in device_type_commands[device_type]:
                device_type_commands[device_type][cmd] = 0
            device_type_commands[device_type][cmd] += count
    
    # Generate suggestions based on device types and common commands
    suggestions = []
    
    # Ciena CPE suggestions
    if 'ciena_cpe' in device_type_commands:
        ciena_commands = device_type_commands['ciena_cpe']
        if 'po sh' in ciena_commands or 'show' in ciena_commands:
            suggestions.append({
                'name': 'Ciena CPE - Port Status Check',
                'description': 'Quick port status check for Ciena CPE devices',
                'category': 'Ciena CPE',
                'commands': [
                    'po sh',
                    'po sh po {port}',
                    'show interface {port} status'
                ],
                'variables': ['port'],
                'priority': 'high',
                'usage_count': ciena_commands.get('po sh', 0) + ciena_commands.get('show', 0)
            })
        
        if 'cfm' in ciena_commands:
            suggestions.append({
                'name': 'Ciena CPE - CFM Monitoring',
                'description': 'CFM monitoring and troubleshooting for Ciena CPE',
                'category': 'Ciena CPE',
                'commands': [
                    'cfm remote-mep show',
                    'cfm local-mep show',
                    'cfm mep show'
                ],
                'variables': [],
                'priority': 'high',
                'usage_count': ciena_commands.get('cfm', 0)
            })
    
    # Nokia SOAG suggestions
    if 'nokia_soag' in device_type_commands:
        nokia_commands = device_type_commands['nokia_soag']
        if 'admin show' in nokia_commands or 'show' in nokia_commands:
            suggestions.append({
                'name': 'Nokia SOAG - Configuration Check',
                'description': 'Configuration and status check for Nokia SOAG devices',
                'category': 'Nokia SOAG',
                'commands': [
                    'admin show configuration full-context | match {pattern}',
                    'admin show version',
                    'show port {port}'
                ],
                'variables': ['pattern', 'port'],
                'priority': 'high',
                'usage_count': nokia_commands.get('admin show', 0) + nokia_commands.get('show', 0)
            })
    
    # Generic troubleshooting suggestions
    suggestions.append({
        'name': 'Generic - Interface Status Check',
        'description': 'Basic interface status check for any device type',
        'category': 'Generic',
        'commands': [
            'show interface {interface}',
            'show interface {interface} status',
            'show interface {interface} statistics'
        ],
        'variables': ['interface'],
        'priority': 'medium',
        'usage_count': index['common_commands'].get('show', 0)
    })
    
    # Sort by usage count
    suggestions.sort(key=lambda x: x['usage_count'], reverse=True)
    
    return suggestions

def get_device_specific_suggestions(device_name):
    """Get template suggestions specific to a device based on its type"""
    index = load_logs_index()
    if not index:
        return []
    
    # Determine device type from name
    device_type = 'unknown'
    if device_name.startswith('ce-'):
        device_type = 'ciena_cpe'
    elif device_name.startswith('mtg-'):
        device_type = 'ciena_metro'
    elif device_name.startswith('nid-'):
        device_type = 'ciena_nid'
    elif device_name.startswith('soag'):
        device_type = 'nokia_soag'
    elif device_name.startswith('ceg'):
        device_type = 'nokia_ceg'
    
    # Get device-specific suggestions
    suggestions = []
    
    if device_type == 'ciena_cpe':
        suggestions = [
            {
                'name': 'Port Status Check',
                'description': 'Check port status and configuration',
                'commands': ['po sh', 'po sh po {port}'],
                'variables': ['port']
            },
            {
                'name': 'CFM Monitoring',
                'description': 'Check CFM status and remote MEPs',
                'commands': ['cfm remote-mep show', 'cfm local-mep show'],
                'variables': []
            },
            {
                'name': 'Interface Statistics',
                'description': 'Check interface statistics and performance',
                'commands': ['show interface {port} statistics', 'show interface {port} detail'],
                'variables': ['port']
            }
        ]
    elif device_type == 'nokia_soag':
        suggestions = [
            {
                'name': 'Configuration Search',
                'description': 'Search configuration for specific patterns',
                'commands': ['admin show configuration full-context | match {pattern}'],
                'variables': ['pattern']
            },
            {
                'name': 'Port Status',
                'description': 'Check port status and configuration',
                'commands': ['show port {port}', 'show port {port} statistics'],
                'variables': ['port']
            },
            {
                'name': 'System Status',
                'description': 'Check system version and status',
                'commands': ['admin show version', 'admin show system'],
                'variables': []
            }
        ]
    
    return suggestions





def discover_devices_from_logs():
    """Discover devices from log analysis and suggest them for device list"""
    index = load_logs_index()
    if not index:
        return []
    
    discovered_devices = []
    
    # Analyze devices from logs
    for device_name, device_info in index['devices'].items():
        # Skip generic/unknown devices
        if device_name in ['Default', 'unknown', 'Unknown']:
            continue
            
        # Determine device type from name
        device_type = 'unknown'
        if device_name.startswith('ce-'):
            device_type = 'ciena_os'
        elif device_name.startswith('mtg-'):
            device_type = 'ciena_os'
        elif device_name.startswith('nid-'):
            device_type = 'ciena_os'
        elif device_name.startswith('soag'):
            device_type = 'nokia_sros'
        elif device_name.startswith('ceg'):
            device_type = 'nokia_sros'
        elif device_name.startswith('asr'):
            device_type = 'cisco_xr'
        elif device_name.startswith('ncs'):
            device_type = 'cisco_xr'
        elif device_name.startswith('mx'):
            device_type = 'juniper'
        elif device_name.startswith('acx'):
            device_type = 'juniper'
        
        # Create device suggestion
        discovered_devices.append({
            'name': device_name,
            'ip_address': device_name,  # Use name as IP for now
            'device_type': device_type,
            'username': '',  # Will be prompted for RADIUS
            'description': f'Discovered from logs - {device_info["file_count"]} log files',
            'file_count': device_info['file_count'],
            'first_seen': device_info['first_seen'],
            'last_seen': device_info['last_seen'],
            'suggested': True
        })
    
    # Sort by file count (most active devices first)
    discovered_devices.sort(key=lambda x: x['file_count'], reverse=True)
    
    return discovered_devices

def get_device_discovery_stats():
    """Get statistics about device discovery"""
    index = load_logs_index()
    if not index:
        return {}
    
    existing_devices = load_devices()
    existing_device_names = set(existing_devices.keys())
    
    discovered_devices = discover_devices_from_logs()
    discovered_device_names = {device['name'] for device in discovered_devices}
    
    stats = {
        'total_discovered': len(discovered_devices),
        'already_added': len(discovered_device_names.intersection(existing_device_names)),
        'new_devices': len(discovered_device_names - existing_device_names),
        'device_types': {},
        'most_active': discovered_devices[:10] if discovered_devices else []
    }
    
    # Count device types
    for device in discovered_devices:
        device_type = device['device_type']
        if device_type not in stats['device_types']:
            stats['device_types'][device_type] = 0
        stats['device_types'][device_type] += 1
    
    return stats






def execute_batch_commands(devices, commands, username=None, password=None):
    """Execute commands on multiple devices in batch"""
    results = {
        'total_devices': len(devices),
        'successful': 0,
        'failed': 0,
        'results': {},
        'summary': {},
        'start_time': datetime.now().isoformat(),
        'end_time': None
    }
    
    # Track command success/failure counts
    command_stats = {}
    for command in commands:
        command_stats[command] = {'success': 0, 'failed': 0}
    
    for device_name in devices:
        try:
            device_result = execute_command_on_device(device_name, commands, username, password)
            results['results'][device_name] = device_result
            
            if device_result['success']:
                results['successful'] += 1
                # Track individual command results
                for cmd_result in device_result['results']:
                    command = cmd_result['command']
                    if command not in command_stats:
                        command_stats[command] = {'success': 0, 'failed': 0}
                    
                    if cmd_result['success']:
                        command_stats[command]['success'] += 1
                    else:
                        command_stats[command]['failed'] += 1
            else:
                results['failed'] += 1
                # Mark all commands as failed for this device
                for command in commands:
                    if command not in command_stats:
                        command_stats[command] = {'success': 0, 'failed': 0}
                    command_stats[command]['failed'] += 1
                    
        except Exception as e:
            results['results'][device_name] = {
                'success': False,
                'error': f'Exception: {str(e)}',
                'results': []
            }
            results['failed'] += 1
    
    results['end_time'] = datetime.now().isoformat()
    results['summary'] = command_stats
    
    return results

def save_batch_result(batch_result, description=""):
    """Save batch execution result as a note"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"batch_execution_{timestamp}.txt"
    
    # Create note content
    content = f"""BATCH EXECUTION REPORT
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Description: {description}

SUMMARY:
- Total Devices: {batch_result['total_devices']}
- Successful: {batch_result['successful']}
- Failed: {batch_result['failed']}
- Success Rate: {(batch_result['successful'] / batch_result['total_devices'] * 100):.1f}%

EXECUTION TIME:
- Start: {batch_result['start_time']}
- End: {batch_result['end_time']}

COMMAND SUMMARY:
"""
    
    for command, stats in batch_result['summary'].items():
        total = stats['success'] + stats['failed']
        success_rate = (stats['success'] / total * 100) if total > 0 else 0
        content += f"- {command}: {stats['success']}/{total} successful ({success_rate:.1f}%)\n"
    
    content += "\nDETAILED RESULTS:\n" + "="*50 + "\n\n"
    
    for device_name, result in batch_result['results'].items():
        content += f"DEVICE: {device_name}\n"
        content += f"Status: {'SUCCESS' if result['success'] else 'FAILED'}\n"
        
        if result['success']:
            for cmd_result in result['results']:
                content += f"\nCommand: {cmd_result['command']}\n"
                content += f"Status: {'SUCCESS' if cmd_result['success'] else 'FAILED'}\n"
                content += f"Output:\n{cmd_result['output']}\n"
                content += "-" * 30 + "\n"
        else:
            content += f"Error: {result.get('error', 'Unknown error')}\n"
        
        content += "\n" + "="*50 + "\n\n"
    
    # Save the note
    note_path = os.path.join(SAVED_NOTES_DIR, filename)
    with open(note_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    # Add to notes metadata
    notes_metadata = load_notes_metadata()
    notes_metadata[filename] = {
        'created': datetime.now().isoformat(),
        'type': 'batch_execution_note',
        'tags': ['batch', 'execution', 'automation'],
        'favorite': False,
        'description': f'Batch execution on {batch_result["total_devices"]} devices - {description}'
    }
    save_notes_metadata(notes_metadata)
    
    return filename
