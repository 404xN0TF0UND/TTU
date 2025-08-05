#!/usr/bin/env python3
"""
Bandwidth Change Script for Ciena SAOS Devices
Converts SecureCRT script to SSH-based execution with web interface support.
"""

import paramiko
import time
import logging
from datetime import datetime
import os

def setup_logging():
    """Setup logging for the script"""
    log_dir = os.path.dirname(os.path.abspath(__file__))
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(log_dir, f'bandwidth_change_{timestamp}.log')
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def ssh_to_device(device_ip, username, password, commands, logger):
    """SSH to device and execute commands"""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        logger.info(f"[{device_ip}] Connecting to device...")
        ssh.connect(device_ip, username=username, password=password, timeout=10)
        logger.info(f"[{device_ip}] Successfully connected")
        
        channel = ssh.invoke_shell()
        time.sleep(2)
        
        outputs = {}
        
        for command in commands:
            logger.info(f"[{device_ip}] Executing: {command}")
            channel.send(command + '\n')
            time.sleep(2)
            
            # Read output
            output = ""
            while channel.recv_ready():
                output += channel.recv(4096).decode('utf-8')
            
            outputs[command] = output
            logger.info(f"[{device_ip}] Command completed: {command}")
        
        ssh.close()
        return outputs
        
    except Exception as e:
        logger.error(f"[{device_ip}] SSH connection error: {str(e)}")
        return {'connection_error': str(e)}

def run_bandwidth_change_web(device_ip, username, password, port, cir_pir_shaper):
    """Web interface version of the bandwidth change script
    
    Args:
        device_ip: IP address of the Ciena device
        username: SSH username (default: rvaugh200)
        password: SSH password
        port: Port number to modify
        cir_pir_shaper: Bandwidth value in kbps (e.g., 110000 for 110Mbps, 1000000 for 1Gbps)
    """
    logger = setup_logging()
    logger.info("[INIT] Starting Bandwidth Change script (Web Interface)")
    
    # Validate inputs
    if not device_ip or not password or not port or not cir_pir_shaper:
        return {
            'success': False,
            'output': 'Error: All fields are required (Device IP, Password, Port, CIR/PIR/Shaper Rate)',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    try:
        # Convert to integers for validation
        port_int = int(port)
        cir_int = int(cir_pir_shaper)
        
        if port_int <= 0 or cir_int <= 0:
            return {
                'success': False,
                'output': 'Error: Port and CIR/PIR/Shaper Rate must be positive numbers',
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
    except ValueError:
        return {
            'success': False,
            'output': 'Error: Port and CIR/PIR/Shaper Rate must be valid numbers',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    # Set CIR, PIR, and shaper-rate to the same value
    cir = pir = shaper_rate = cir_pir_shaper
    
    logger.info(f"[{device_ip}] Device details - Username: {username}, Port: {port}, CIR/PIR/Shaper: {cir_pir_shaper}")
    
    # Define commands to execute
    commands = [
        "traffic-profiling standard-profile show",
        f"traffic-profiling standard-profile set port {port} profile\tcir {cir} pir {pir}",
        f"traffic-services queuing egress-port set port {port} shaper-rate {shaper_rate}",
        "Con sa",
        "traffic-profiling standard-profile show"
    ]
    
    # Execute commands via SSH
    outputs = ssh_to_device(device_ip, username, password, commands, logger)
    
    # Format output for web display
    formatted_output = []
    for command, output in outputs.items():
        formatted_output.append(f"Command: {command}")
        formatted_output.append(f"Output:\n{output}")
        formatted_output.append("="*50)
    
    result = {
        'success': 'connection_error' not in outputs,
        'output': '\n'.join(formatted_output),
        'raw_outputs': outputs,
        'device_ip': device_ip,
        'port': port,
        'cir_pir_shaper': cir_pir_shaper,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    logger.info("[COMPLETE] Bandwidth change script execution completed (Web Interface)")
    return result

if __name__ == "__main__":
    # Console version for testing
    print("Bandwidth Change Script for Ciena SAOS Devices")
    print("=" * 50)
    
    device_ip = input("Enter device IP: ")
    username = input("Enter username (default: rvaugh200): ") or "rvaugh200"
    password = input("Enter password: ")
    port = input("Enter port number: ")
    cir_pir_shaper = input("Enter CIR/PIR/Shaper rate: ")
    
    result = run_bandwidth_change_web(device_ip, username, password, port, cir_pir_shaper)
    
    print(f"\nSuccess: {result['success']}")
    print(f"Output:\n{result['output']}") 