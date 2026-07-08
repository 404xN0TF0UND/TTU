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
