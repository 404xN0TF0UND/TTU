from netmiko import ConnectHandler, NetmikoTimeoutException, NetmikoAuthenticationException
import getpass
import os
import sys
import logging
from datetime import datetime
import time

def setup_logging():
    """Set up logging to a file with a timestamp in the filename. Returns the logger object."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f"ciena_ssh_log_{timestamp}.txt"

    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    logger = logging.getLogger()
    return logger

def ssh_to_ciena(device_ip, username, password, commands, logger, cfm_test=False, local_mepid=9):
    """SSH into a Ciena SAOS device, run commands, capture outputs, and log to file."""
    device = {
        'device_type': 'ciena_saos',
        'ip': device_ip,
        'username': username,
        'password': password,
        'port': 22,
        'timeout': 30,
        'verbose': True
    }

    output_dict = {}

    try:
        print(f"Connecting to {device_ip}...")
        logger.info(f"[{device_ip}] Connecting to device")

        with ConnectHandler(**device) as net_connect:
            net_connect.send_command("prompt")

            # Run standard commands
            for command in commands:
                print(f"\nExecuting command: {command}")
                logger.info(f"[{device_ip}] Executing command: {command}")

                try:
                    use_textfsm = False  # Avoid auto-parsing unless template available
                    output = net_connect.send_command(command, use_textfsm=use_textfsm)
                    output_dict[command] = output
                    print(f"Output for '{command}':\n{output}\n{'-'*50}")
                    logger.info(f"[{device_ip}] Output for '{command}':\n{output}")
                except Exception as e:
                    error_msg = f"Error executing command '{command}': {str(e)}"
                    output_dict[command] = error_msg
                    print(f"{error_msg}\n{'-'*50}")
                    logger.error(f"[{device_ip}] {error_msg}")

            # Run CFM tests if enabled
            if cfm_test:
                cfm_remote = output_dict.get("cfm remote-mep show", "")
                service_name = None
                remote_mep_ids = []

                # Extract service name and MEP IDs from output
                for line in cfm_remote.splitlines():
                    if line.strip().startswith("|") and ".." in line:
                        parts = line.strip("|").split("|")
                        if len(parts) >= 3:
                            service = parts[0].strip()
                            mepid = parts[1].strip()
                            if service and mepid.isdigit():
                                service_name = service  # Assuming same service for all rows
                                remote_mep_ids.append(int(mepid))

                if service_name and remote_mep_ids:
                    for remote_mepid in remote_mep_ids:
                        cfm_command = f"cfm delay send service {service_name} local-mepid {local_mepid} mepid {remote_mepid} count 30"
                        print(f"\nExecuting CFM command: {cfm_command}")
                        logger.info(f"[{device_ip}] Executing CFM command: {cfm_command}")
                        try:
                            output = net_connect.send_command(cfm_command)
                            output_dict[cfm_command] = output
                            print(f"Output for '{cfm_command}':\n{output}\n{'-'*50}")
                            logger.info(f"[{device_ip}] Output for '{cfm_command}':\n{output}")
                        except Exception as e:
                            error_msg = f"Error executing CFM command '{cfm_command}': {str(e)}"
                            output_dict[cfm_command] = error_msg
                            print(f"{error_msg}\n{'-'*50}")
                            logger.error(f"[{device_ip}] {error_msg}")

                    print("Waiting 60 seconds for CFM tests to complete...")
                    time.sleep(60)

                    cfm_show_command = "cfm delay show"
                    print(f"\nExecuting command: {cfm_show_command}")
                    logger.info(f"[{device_ip}] Executing command: {cfm_show_command}")

                    try:
                        output = net_connect.send_command(cfm_show_command)
                        output_dict[cfm_show_command] = output
                        print(f"Output for '{cfm_show_command}':\n{output}\n{'-'*50}")
                        logger.info(f"[{device_ip}] Output for '{cfm_show_command}':\n{output}")
                    except Exception as e:
                        error_msg = f"Error executing command '{cfm_show_command}': {str(e)}"
                        output_dict[cfm_show_command] = error_msg
                        print(f"{error_msg}\n{'-'*50}")
                        logger.error(f"[{device_ip}] {error_msg}")
                else:
                    error_msg = "Failed to extract service name or MEP IDs from 'cfm remote-mep show'."
                    output_dict['cfm_test_error'] = error_msg
                    print(error_msg)
                    logger.error(f"[{device_ip}] {error_msg}")

    except NetmikoTimeoutException:
        error_msg = f"Connection to {device_ip} timed out."
        print(error_msg)
        logger.error(f"[{device_ip}] {error_msg}")
        output_dict['connection_error'] = error_msg

    except NetmikoAuthenticationException:
        error_msg = f"Authentication failed for {device_ip}. Check username/password."
        print(error_msg)
        logger.error(f"[{device_ip}] {error_msg}")
        output_dict['connection_error'] = error_msg

    except Exception as e:
        error_msg = f"Unexpected error connecting to {device_ip}: {str(e)}"
        print(error_msg)
        logger.error(f"[{device_ip}] {error_msg}")
        output_dict['connection_error'] = error_msg

    return output_dict

def main():
    logger = setup_logging()
    logger.info("[INIT] Starting Ciena SAOS SSH script")

    device_ip = input("Enter Ciena device IP address: ")
    username = os.environ.get("TTU_SSH_USER") or input("Enter SSH username: ")
    password = getpass.getpass("Enter SSH password: ")

    local_mepid_input = input("Enter local MEP ID (default 9): ") or "9"
    try:
        local_mepid = int(local_mepid_input)
    except ValueError:
        local_mepid = 9

    commands = [
        "port show",
        "port show port 1",
        "traffic-profiling standard-profile show",
        "cfm remote-mep show"
    ]

    logger.info(f"[{device_ip}] Device details - Username: {username}, Commands: {commands}, Local MEP ID: {local_mepid}")
    outputs = ssh_to_ciena(device_ip, username, password, commands, logger, cfm_test=True, local_mepid=local_mepid)

    print("\nSummary of Command Outputs:")
    logger.info(f"[{device_ip}] Summary of Command Outputs")

    for command, output in outputs.items():
        print(f"\nCommand: {command}")
        print(f"Output:\n{output}\n{'='*50}")
        logger.info(f"[{device_ip}] Command: {command}\nOutput:\n{output}")

    logger.info("[COMPLETE] Script execution completed")

def run_ciena_cfm_web(device_ip, username, password, local_mepid=9):
    """Web interface version of the Ciena CFM script that returns results as a dictionary."""
    logger = setup_logging()
    logger.info("[INIT] Starting Ciena SAOS SSH script (Web Interface)")

    commands = [
        "port show",
        "port show port 1",
        "traffic-profiling standard-profile show",
        "cfm remote-mep show"
    ]

    logger.info(f"[{device_ip}] Device details - Username: {username}, Commands: {commands}, Local MEP ID: {local_mepid}")
    outputs = ssh_to_ciena(device_ip, username, password, commands, logger, cfm_test=True, local_mepid=local_mepid)

    formatted_output = []
    for command, output in outputs.items():
        formatted_output.append(f"Command: {command}")
        formatted_output.append(f"Output:\n{output}")
        formatted_output.append("=" * 50)

    result = {
        'success': 'connection_error' not in outputs and 'cfm_test_error' not in outputs,
        'output': '\n'.join(formatted_output),
        'raw_outputs': outputs,
        'device_ip': device_ip,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    logger.info("[COMPLETE] Script execution completed (Web Interface)")
    return result



# --- Extension (#4 from log mining): MEP status + benchmark reflector ----
# Benchmark sequences mirror the canonical session mined from the 2026
# archive (67x setup / 148x teardown): refDefault reflector +
# refTestDefault test, optional per-circuit ip-interface (EDIA-<n>-ref).
BENCH_REFLECTOR = "refDefault"
BENCH_TEST = "refTestDefault"


def parse_cfm_mep_table(output):
    """Parse 'cfm mep show' table rows into dicts. Columns per SAOS:
    Service | Port | Vid | Mepid | Type | Mac | Admin | CCM | Pri |
    Accelerated | SD Trigger Mode. Handles wrapped service-name rows."""
    meps = []
    for line in output.splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("+"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) >= 11 and cells[3].isdigit():
            meps.append({
                "service": cells[0].rstrip("."), "port": cells[1],
                "vid": cells[2], "mepid": cells[3], "type": cells[4],
                "mac": cells[5], "admin": cells[6], "ccm": cells[7],
                "pri": cells[8], "accelerated": cells[9], "sd_mode": cells[10],
            })
        elif meps and len(cells) >= 11 and cells[0] and cells[0] != "." \
                and not any(cells[1:4]):
            # wrapped service-name continuation row
            meps[-1]["service"] = (meps[-1]["service"]
                                   + cells[0].rstrip(".")).rstrip(".")
    return meps


def cfm_status_commands():
    """Read-only status set: ports, local MEPs, remote MEPs, profiles."""
    return ["port show", "cfm mep show", "cfm remote-mep show",
            "traffic-profiling standard-profile show"]


def run_cfm_status_web(device_ip, username, password):
    """Read-only CFM/MEP status capture with parsed MEP table."""
    logger = setup_logging()
    logger.info("[INIT] Ciena CFM status (Web Interface, read-only)")
    outputs = ssh_to_ciena(device_ip, username, password,
                           cfm_status_commands(), logger, cfm_test=False)
    formatted = []
    for command, output in outputs.items():
        formatted += [f"Command: {command}", f"Output:\n{output}", "=" * 50]
    result = {
        "success": "connection_error" not in outputs,
        "output": "\n".join(formatted),
        "raw_outputs": outputs,
        "meps": parse_cfm_mep_table(outputs.get("cfm mep show", "")),
        "device_ip": device_ip,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    logger.info("[COMPLETE] CFM status finished")
    return result


def benchmark_setup_sequence(port, ip_interface=None):
    seq = [
        f"benchmark create reflector name {BENCH_REFLECTOR} port {port}",
        f"benchmark reflector set name {BENCH_REFLECTOR} mode out-of-service",
        f"benchmark test create name {BENCH_TEST} vtag-stack *",
        f"benchmark reflector clear name {BENCH_REFLECTOR} statistics",
        "benchmark enable",
        "benchmark reflector enable",
        f"benchmark test enable name {BENCH_TEST}",
    ]
    if ip_interface:
        seq.append(f"interface enable ip-interface {ip_interface}")
    seq.append("bench sh")
    return seq


def benchmark_teardown_sequence(ip_interface=None, delete=False):
    seq = [
        f"benchmark test disable name {BENCH_TEST}",
        "benchmark disable",
        "benchmark reflector disable",
    ]
    if ip_interface:
        seq.append(f"interface disable ip-interface {ip_interface}")
    if delete:
        seq += [f"benchmark reflector delete name {BENCH_REFLECTOR} "
                "all-test-instances",
                f"benchmark delete name {BENCH_REFLECTOR}"]
    seq.append("bench sh")
    return seq


def run_benchmark_web(device_ip, username, password, action,
                      port=None, ip_interface=None, delete=False):
    """Run the benchmark reflector setup / teardown / status cycle."""
    logger = setup_logging()
    logger.info(f"[INIT] Ciena benchmark {action} (Web Interface)")
    if action == "setup":
        commands = benchmark_setup_sequence(port, ip_interface)
    elif action == "teardown":
        commands = benchmark_teardown_sequence(ip_interface, delete)
    elif action == "status":
        commands = ["bench sh"]
    else:
        return {"success": False, "output": f"unknown action '{action}'",
                "raw_outputs": {}, "device_ip": device_ip,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    outputs = ssh_to_ciena(device_ip, username, password, commands, logger,
                           cfm_test=False)
    formatted = []
    for command, output in outputs.items():
        formatted += [f"Command: {command}", f"Output:\n{output}", "=" * 50]
    result = {
        "success": "connection_error" not in outputs,
        "output": "\n".join(formatted),
        "raw_outputs": outputs,
        "sequence": commands,
        "device_ip": device_ip,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    logger.info(f"[COMPLETE] Benchmark {action} finished")
    return result


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nScript interrupted by user.")
        logging.error("[INTERRUPT] Script interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        logging.error(f"[ERROR] An unexpected error occurred: {str(e)}")
        sys.exit(1)
