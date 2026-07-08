"""library blueprint - routes extracted verbatim from app.py (mechanical split, no behavior change)."""
from flask import Blueprint
from core import *  # shared app, helpers, constants, flask names

library_bp = Blueprint('library', __name__)


@library_bp.route('/commands/library')
def command_library():
    """Library of common network commands"""
    command_library = load_command_library()
    return render_template('command_library.html', command_library=command_library)


@library_bp.route('/commands/library/manage')
def manage_command_library():
    """Manage command library through web interface"""
    command_library = load_command_library()
    return render_template('manage_command_library.html', command_library=command_library)


@library_bp.route('/commands/library/edit', methods=['POST'])
def edit_command_library():
    """Edit command library"""
    try:
        data = request.get_json()
        if data and 'commands' in data:
            save_command_library(data['commands'])
            flash('Command library updated successfully!', 'success')
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Invalid data'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@library_bp.route('/commands/library/add-vendor', methods=['POST'])
def add_vendor():
    """Add a new vendor to the command library"""
    try:
        vendor_name = request.form.get('vendor_name', '').strip().lower()
        if not vendor_name:
            flash('Vendor name is required', 'error')
            return redirect(url_for('library.manage_command_library'))
        
        command_library = load_command_library()
        if vendor_name in command_library:
            flash(f'Vendor "{vendor_name}" already exists', 'error')
        else:
            command_library[vendor_name] = {
                'Basic': [],
                'Troubleshooting': [],
                'Configuration': []
            }
            save_command_library(command_library)
            flash(f'Vendor "{vendor_name}" added successfully!', 'success')
        
        return redirect(url_for('library.manage_command_library'))
    except Exception as e:
        flash(f'Error adding vendor: {str(e)}', 'error')
        return redirect(url_for('library.manage_command_library'))


@library_bp.route('/commands/library/delete-vendor/<vendor_name>', methods=['POST'])
def delete_vendor(vendor_name):
    """Delete a vendor from the command library"""
    try:
        command_library = load_command_library()
        if vendor_name in command_library:
            del command_library[vendor_name]
            save_command_library(command_library)
            flash(f'Vendor "{vendor_name}" deleted successfully!', 'success')
        else:
            flash(f'Vendor "{vendor_name}" not found', 'error')
        
        return redirect(url_for('library.manage_command_library'))
    except Exception as e:
        flash(f'Error deleting vendor: {str(e)}', 'error')
        return redirect(url_for('library.manage_command_library'))


@library_bp.route('/commands/library/delete-command', methods=['POST'])
def delete_command():
    """Delete a specific command from the command library"""
    try:
        vendor = request.form.get('vendor', '').strip()
        category = request.form.get('category', '').strip()
        command = request.form.get('command', '').strip()
        
        if not all([vendor, category, command]):
            flash('Missing required parameters', 'error')
            return redirect(url_for('library.manage_command_library'))
        
        command_library = load_command_library()
        
        if vendor in command_library and category in command_library[vendor]:
            if command in command_library[vendor][category]:
                command_library[vendor][category].remove(command)
                save_command_library(command_library)
                flash(f'Command "{command}" deleted successfully!', 'success')
            else:
                flash(f'Command "{command}" not found in {category}', 'error')
        else:
            flash(f'Vendor "{vendor}" or category "{category}" not found', 'error')
        
        return redirect(url_for('library.manage_command_library'))
    except Exception as e:
        flash(f'Error deleting command: {str(e)}', 'error')
        return redirect(url_for('library.manage_command_library'))
