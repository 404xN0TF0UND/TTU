"""tools blueprint - routes extracted verbatim from app.py (mechanical split, no behavior change)."""
from flask import Blueprint
from core import *  # shared app, helpers, constants, flask names

tools_bp = Blueprint('tools', __name__)


@tools_bp.route('/scripts', methods=['GET', 'POST'])
def scripts():
    scripts = [f for f in os.listdir(SCRIPTS_DIR) if f.endswith('.py')]
    output = None
    selected_script = None
    if request.method == 'POST':
        selected_script = request.form.get('script')
        if selected_script and selected_script in scripts:
            try:
                result = subprocess.run(['python', os.path.join(SCRIPTS_DIR, selected_script)], capture_output=True, text=True, timeout=30)
                output = result.stdout + '\n' + result.stderr
            except Exception as e:
                output = f'Error running script: {e}'
    return render_template('scripts.html', scripts=scripts, output=output, selected_script=selected_script)


@tools_bp.route('/scripts/ciena-cfm', methods=['GET', 'POST'])
def ciena_cfm_script():
    """Ciena CFM toolkit: delay tests, MEP status, benchmark reflector."""
    import sys
    sys.path.append(SCRIPTS_DIR)
    default_username = os.environ.get('TTU_SSH_USER', '')
    result = None
    mode = 'status'

    if request.method == 'POST':
        mode = request.form.get('mode', 'status')
        device_ip = request.form.get('device_ip', '').strip()
        username, password = resolve_creds(request.form)

        if not device_ip or not username or not password:
            flash('Device IP, username, and password are required!', 'error')
            return render_template('ciena_cfm.html', result=None, mode=mode,
                                   default_username=default_username)
        try:
            from Ciena_CFM import (run_ciena_cfm_web, run_cfm_status_web,
                                   run_benchmark_web)

            if mode == 'delay':
                try:
                    local_mepid = int(request.form.get('local_mepid', '9'))
                except ValueError:
                    local_mepid = 9
                result = run_ciena_cfm_web(device_ip, username, password,
                                           local_mepid)
            elif mode == 'status':
                result = run_cfm_status_web(device_ip, username, password)
            elif mode in ('bench_setup', 'bench_teardown', 'bench_status'):
                action = mode.replace('bench_', '')
                if action in ('setup', 'teardown') and \
                        request.form.get('confirm_bench') != 'on':
                    flash('Benchmark setup/teardown changes device state — '
                          'tick the confirmation box to proceed. '
                          'Nothing was sent.', 'error')
                    return render_template('ciena_cfm.html', result=None,
                                           mode=mode,
                                           default_username=default_username)
                port = request.form.get('bench_port', '').strip()
                ip_interface = request.form.get('ip_interface', '').strip() \
                    or None
                delete = request.form.get('bench_delete') == 'on'
                if action == 'setup' and not port:
                    flash('Reflector port is required for benchmark setup!',
                          'error')
                    return render_template('ciena_cfm.html', result=None,
                                           mode=mode,
                                           default_username=default_username)
                result = run_benchmark_web(device_ip, username, password,
                                           action, port=port,
                                           ip_interface=ip_interface,
                                           delete=delete)
            else:
                flash(f'Unknown mode: {mode}', 'error')

            if result is not None:
                if result['success']:
                    flash(f'{mode} completed for {device_ip}.', 'success')
                else:
                    flash(f'{mode} completed with errors for {device_ip} — '
                          'check output.', 'warning')
        except ImportError as e:
            flash(f'Error importing Ciena CFM script: {str(e)}', 'error')
        except Exception as e:
            flash(f'Error running Ciena CFM script: {str(e)}', 'error')

    return render_template('ciena_cfm.html', result=result, mode=mode,
                           default_username=default_username)


@tools_bp.route('/scripts/bandwidth-change', methods=['GET', 'POST'])
def bandwidth_change_script():
    """Handle Bandwidth Change script execution with web form inputs."""
    if request.method == 'POST':
        device_ip = request.form.get('device_ip', '').strip()
        username, password = resolve_creds(request.form)
        port = request.form.get('port', '').strip()
        cir_pir_shaper = request.form.get('cir_pir_shaper', '').strip()
        
        # Validation
        if not device_ip or not password or not port or not cir_pir_shaper:
            flash('All fields are required (Device IP, Password, Port, CIR/PIR/Shaper Rate)!', 'error')
            return redirect(url_for('tools.bandwidth_change_script'))
        
        try:
            port_int = int(port)
            cir_int = int(cir_pir_shaper)
            if port_int <= 0 or cir_int <= 0:
                flash('Port and CIR/PIR/Shaper Rate must be positive numbers!', 'error')
                return redirect(url_for('tools.bandwidth_change_script'))
        except ValueError:
            flash('Port and CIR/PIR/Shaper Rate must be valid numbers!', 'error')
            return redirect(url_for('tools.bandwidth_change_script'))
        
        # Import and run the script
        try:
            import sys
            sys.path.append(SCRIPTS_DIR)
            from Bandwidth_Change import run_bandwidth_change_web
            
            result = run_bandwidth_change_web(device_ip, username, password, port, cir_pir_shaper)
            
            if result['success']:
                flash(f'Bandwidth change completed successfully for {device_ip} port {port}!', 'success')
            else:
                flash(f'Bandwidth change completed with errors for {device_ip}. Check output for details.', 'warning')
            
            # Store result in session for display
            session['bandwidth_change_result'] = result
            
        except ImportError as e:
            flash(f'Error importing Bandwidth Change script: {str(e)}', 'error')
        except Exception as e:
            flash(f'Error running Bandwidth Change script: {str(e)}', 'error')
        
        return redirect(url_for('tools.bandwidth_change_script'))
    
    # Get result from session if available
    result = session.pop('bandwidth_change_result', None)
    return render_template('bandwidth_change.html', result=result,
                           default_username=os.environ.get('TTU_SSH_USER', ''))


@tools_bp.route('/credentials', methods=['GET', 'POST'])
def session_credentials():
    """Set or clear in-memory session credentials."""
    if request.method == 'POST':
        if request.form.get('action') == 'clear':
            SESSION_CREDS.clear()
            flash('Session credentials cleared.', 'success')
        else:
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            if not username or not password:
                flash('Username and password are required!', 'error')
            else:
                SESSION_CREDS.update(username=username, password=password,
                                     ts=time_module.time())
                flash(f'Credentials for {username} held in memory for this '
                      'app session (8h max). Script pages will use them '
                      'automatically.', 'success')
        return redirect(url_for('tools.session_credentials'))
    return render_template('credentials.html')


@tools_bp.route('/tools/itu-grid')
def itu_grid_tool():
    """ITU C-band 100 GHz grid reference and unit converter."""
    import sys
    sys.path.append(SCRIPTS_DIR)
    from Nokia_Retune import ITU_GRID_GHZ, ghz_to_nm
    rows = [{'channel': ch, 'ghz': ghz, 'thz': ghz / 1000.0,
             'mhz': ghz * 1000, 'nm': round(ghz_to_nm(ghz), 2)}
            for ghz, ch in sorted(ITU_GRID_GHZ.items())]
    return render_template('itu_grid.html', rows=rows)


@tools_bp.route('/scripts/nokia-retune', methods=['GET', 'POST'])
def nokia_retune_script():
    """Nokia SR OS DWDM frequency retune with grid validation."""
    import sys
    import uuid
    sys.path.append(SCRIPTS_DIR)
    preview = None
    result = None
    token = None
    form = {'host': '', 'port': '', 'frequency': '', 'username': ''}

    if request.method == 'POST':
        expire_pending_retunes()
        action = request.form.get('action', '')

        try:
            from Nokia_Retune import (run_retune_preview, run_retune_execute)
        except ImportError as e:
            flash(f'Error importing Nokia Retune script: {str(e)}', 'error')
            return render_template('nokia_retune.html', preview=None,
                                   result=None, token=None, form=form)

        if action == 'preview':
            form = {k: request.form.get(k, '').strip()
                    for k in ('host', 'port', 'frequency', 'username')}
            form['username'], password = resolve_creds(request.form)
            if not all(form.values()) or not password:
                flash('All fields are required!', 'error')
            else:
                preview = run_retune_preview(form['host'], form['port'],
                                             form['frequency'],
                                             form['username'], password)
                if preview['error']:
                    flash(f"Pre-check failed: {preview['error']}", 'error')
                else:
                    token = uuid.uuid4().hex
                    PENDING_RETUNES[token] = {
                        'host': form['host'], 'port': form['port'],
                        'freq_mhz': preview['freq_mhz'],
                        'username': form['username'], 'password': password,
                        'ts': time_module.time(),
                    }

        elif action == 'execute':
            token_in = request.form.get('token', '')
            pending = PENDING_RETUNES.pop(token_in, None)
            if pending is None:
                flash('Preview expired or already used — run preview again.',
                      'error')
            elif request.form.get('confirm', '').strip() != 'RETUNE':
                PENDING_RETUNES[token_in] = pending
                flash('Confirmation text must be exactly RETUNE — '
                      'nothing was sent. Run preview again to review.',
                      'error')
            else:
                result = run_retune_execute(
                    pending['host'], pending['port'], pending['freq_mhz'],
                    pending['username'], pending['password'])
                if result['success']:
                    flash(f"Port retuned and verified at "
                          f"{result['post'].get('wavelength_nm')} nm.",
                          'success')
                else:
                    flash(f"Retune not verified — {result['error']}",
                          'warning')

    return render_template('nokia_retune.html', preview=preview,
                           result=result, token=token, form=form)


@tools_bp.route('/scripts/port-check', methods=['GET', 'POST'])
def port_check_script():
    """Bulk multi-vendor port status check — show commands only."""
    import sys
    sys.path.append(SCRIPTS_DIR)
    result = None
    targets_text = ''
    username = ''

    if request.method == 'POST':
        try:
            from Port_Disable import parse_targets_text  # shared parser
            from PortCheck import run_port_check_web
        except ImportError as e:
            flash(f'Error importing PortCheck script: {str(e)}', 'error')
            return render_template('port_check.html', result=None,
                                   targets_text='', username='')

        targets_text = request.form.get('targets', '').strip()
        username, password = resolve_creds(request.form)
        if not targets_text or not username or not password:
            flash('Targets, username, and password are required!', 'error')
        else:
            targets, errors = parse_targets_text(targets_text)
            for err in errors:
                flash(f'Target skipped — {err}', 'warning')
            if not targets:
                flash('No valid targets found.', 'error')
            else:
                result = run_port_check_web(targets, username, password)
                bad = sum(1 for r in result['results'] if r['error'])
                if bad:
                    flash(f"{bad} of {len(result['results'])} target(s) had "
                          'errors — see table.', 'warning')

    return render_template('port_check.html', result=result,
                           targets_text=targets_text, username=username)


@tools_bp.route('/scripts/port-disable', methods=['GET', 'POST'])
def port_disable_script():
    """Vendor-aware one-way port disable with pre/post capture."""
    import sys
    import uuid
    sys.path.append(SCRIPTS_DIR)
    preview = None
    result = None
    token = None
    targets_text = ''
    username = ''

    if request.method == 'POST':
        expire_pending_disables()
        action = request.form.get('action', '')

        try:
            from Port_Disable import (parse_targets_text,
                                      run_port_disable_preview,
                                      run_port_disable_execute)
        except ImportError as e:
            flash(f'Error importing Port Disable script: {str(e)}', 'error')
            return render_template('port_disable.html', preview=None,
                                   result=None, token=None, targets_text='',
                                   username='')

        if action == 'preview':
            targets_text = request.form.get('targets', '').strip()
            username, password = resolve_creds(request.form)
            if not targets_text or not username or not password:
                flash('Targets, username, and password are required!', 'error')
            else:
                targets, errors = parse_targets_text(targets_text)
                for err in errors:
                    flash(f'Target skipped — {err}', 'warning')
                if not targets:
                    flash('No valid targets found.', 'error')
                else:
                    preview = run_port_disable_preview(targets, username,
                                                       password)
                    token = uuid.uuid4().hex
                    PENDING_DISABLES[token] = {
                        'targets': targets,
                        'username': username,
                        'password': password,
                        'previews': preview['targets'],
                        'ts': time_module.time(),
                    }

        elif action == 'execute':
            token_in = request.form.get('token', '')
            pending = PENDING_DISABLES.pop(token_in, None)
            if pending is None:
                flash('Preview expired or already used — run preview again.',
                      'error')
            elif request.form.get('confirm', '').strip() != 'DISABLE':
                # put it back so the user can retry the confirmation
                PENDING_DISABLES[token_in] = pending
                token = token_in
                preview = {'targets': pending['previews']}
                targets_text = '\n'.join(
                    f"{h},{p}" for h, p, _ in pending['targets'])
                username = pending['username']
                flash('Confirmation text must be exactly DISABLE — '
                      'nothing was sent.', 'error')
            else:
                result = run_port_disable_execute(
                    pending['targets'], pending['username'],
                    pending['password'], previews=pending['previews'])
                ok = sum(1 for r in result['results'] if r['success'])
                total = len(result['results'])
                if ok == total:
                    flash(f'All {total} port(s) confirmed disabled.',
                          'success')
                else:
                    flash(f'{ok}/{total} port(s) disabled — review the '
                          'failures below.', 'warning')

    return render_template('port_disable.html', preview=preview,
                           result=result, token=token,
                           targets_text=targets_text, username=username)
