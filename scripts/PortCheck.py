"""PortCheck.py — read-only multi-vendor port status checker.

Checks admin/oper state, description, and TX/RX light levels on
Nokia SR OS, Cisco IOS-XR, Juniper, and Ciena SAOS devices.
Show commands only — never enters config mode.

Usage:
    python PortCheck.py <host> <port> [vendor]
    python PortCheck.py -f targets.csv

CSV format (one target per line, vendor optional):
    host,port[,vendor]
    soag06.cinco.tx.houston.comcast.net,1/1/10,nokia
    ssag02.area4.il.chicago.comcast.net,GigabitEthernet0/0/0/5,xr
    ag-setcwaej05w.seatac.wa.seattle.comcast.net,ge-0/2/2,juniper
    nid-cpe-wpblfljn00w.metroeohfc.fl.comcast.net,3,ciena

Port format per vendor:
    nokia   slot/mda/port           e.g. 1/1/10
    xr      full interface name     e.g. GigabitEthernet0/0/0/5, TenGigE0/4/0/9
    juniper full interface name     e.g. ge-0/2/2, xe-0/1/3
    ciena   port number             e.g. 3

If vendor is omitted, netmiko SSH autodetection is attempted.
"""

from netmiko import ConnectHandler, NetmikoTimeoutException, NetmikoAuthenticationException
from netmiko.ssh_autodetect import SSHDetect
import getpass
import sys
import os
import re
import csv
import logging
import platform
import subprocess
from datetime import datetime

VENDOR_ALIASES = {
    "nokia": "nokia_sros", "sros": "nokia_sros", "nokia_sros": "nokia_sros",
    "xr": "cisco_xr", "cisco": "cisco_xr", "cisco_xr": "cisco_xr",
    "iosxr": "cisco_xr", "5501": "cisco_xr", "9k": "cisco_xr",
    "juniper": "juniper_junos", "junos": "juniper_junos",
    "juniper_junos": "juniper_junos",
    "ciena": "ciena_saos", "saos": "ciena_saos", "ciena_saos": "ciena_saos",
}

FIELDS = ["host", "port", "vendor", "ping", "admin", "oper",
          "rx_dbm", "tx_dbm", "optic", "descr", "error"]


def setup_logging():
    """Timestamped log file per run (same pattern as CienaCFM.py)."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f"portcheck_log_{ts}.txt"
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    return logging.getLogger(), ts


def ping_host(host, timeout_s=3):
    """One ping, cross-platform. Returns True if host answers."""
    if platform.system().lower() == "windows":
        cmd = ["ping", "-n", "1", "-w", str(timeout_s * 1000), host]
    else:
        cmd = ["ping", "-c", "1", "-W", str(timeout_s), host]
    try:
        r = subprocess.run(cmd, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=timeout_s + 3)
        return r.returncode == 0
    except Exception:
        return False


def first_float(text):
    m = re.search(r"(-?\d+\.?\d*)", text)
    return m.group(1) if m else ""


# ---------------------------------------------------------------- parsers

def parse_nokia(outputs, port):
    """Parse 'show port <p>' output (includes DDM table)."""
    text = outputs.get(f"show port {port}", "")
    r = {}
    m = re.search(r"Admin State\s*:\s*(\S+)", text)
    r["admin"] = m.group(1) if m else ""
    m = re.search(r"Oper State\s*:\s*(\S+)", text)
    r["oper"] = m.group(1) if m else ""
    m = re.search(r"Description\s*:\s*(.+)", text)
    r["descr"] = m.group(1).strip() if m else ""
    # DDM rows: first numeric column is the current value
    m = re.search(r"Rx Optical Power \(avg dBm\)\s+(-?\d+\.?\d*)", text)
    r["rx_dbm"] = m.group(1) if m else ""
    m = re.search(r"Tx Output Power \(dBm\)\s+(-?\d+\.?\d*)", text)
    r["tx_dbm"] = m.group(1) if m else ""
    optic = []
    m = re.search(r"Transceiver Type\s*:\s*(\S+)", text)
    if m and m.group(1) != "unsupported":
        optic.append(m.group(1))
    m = re.search(r"Optical Compliance\s*:\s*(\S+)", text)
    if m:
        optic.append(m.group(1))
    m = re.search(r"TX Laser Wavelength\s*:\s*(\d+\.?\d*)\s*nm", text)
    if m:
        optic.append(m.group(1) + "nm")
    r["optic"] = " ".join(optic)
    return r


def parse_xr(outputs, port):
    """Parse 'show interfaces <if>' + 'show controllers optics <r/s/i/p>'."""
    text = outputs.get(f"show interfaces {port}", "")
    r = {}
    m = re.search(r"^\S+ is (administratively down|up|down)"
                  r", line protocol is (\S+)", text, re.M)
    if m:
        r["admin"] = "down" if "administratively" in m.group(1) else "up"
        r["oper"] = m.group(2)
    else:
        r["admin"] = r["oper"] = ""
    m = re.search(r"Description:\s*(.+)", text)
    r["descr"] = m.group(1).strip() if m else ""
    opt = ""
    for k, v in outputs.items():
        if k.startswith("show controllers optics"):
            opt = v
    m = re.search(r"RX Power\s*=\s*(-?\d+\.?\d*)\s*dBm", opt)
    r["rx_dbm"] = m.group(1) if m else ""
    m = re.search(r"Actual TX Power\s*=\s*(-?\d+\.?\d*)\s*dBm", opt)
    r["tx_dbm"] = m.group(1) if m else ""
    optic = []
    m = re.search(r"Optics Type:\s*(.+)", opt)
    if m:
        optic.append(m.group(1).strip())
    m = re.search(r"Frequency=(\d+\.?\d*)\s*THz", opt)
    if m:
        optic.append(m.group(1) + "THz")
    m = re.search(r"Wavelength=(\d+\.?\d*)\s*nm", opt)
    if m:
        optic.append(m.group(1) + "nm")
    r["optic"] = " ".join(optic)
    m = re.search(r"Detected Alarms:\s*\n\s*(\S+)", opt)
    if m:
        r["optic"] = (r["optic"] + f" ALARM:{m.group(1)}").strip()
    return r


def parse_juniper(outputs, port):
    """Parse 'show interfaces <if>' + 'show interfaces diagnostics optics'."""
    text = outputs.get(f"show interfaces {port}", "")
    r = {}
    m = re.search(r"Physical interface:\s*\S+,\s*(Enabled|Disabled|"
                  r"Administratively down),\s*Physical link is (\S+)", text)
    if m:
        r["admin"] = "up" if m.group(1) == "Enabled" else "down"
        r["oper"] = m.group(2).lower()
    else:
        r["admin"] = r["oper"] = ""
    m = re.search(r"Description:\s*(.+)", text)
    r["descr"] = m.group(1).strip() if m else ""
    opt = outputs.get(f"show interfaces diagnostics optics {port}", "")
    m = re.search(r"Receiver signal average optical power\s*:.*?/\s*"
                  r"(-?\s*(?:Inf|\d+\.?\d*))\s*dBm", opt)
    r["rx_dbm"] = m.group(1).replace(" ", "") if m else ""
    m = re.search(r"Laser output power\s*:.*?/\s*"
                  r"(-?\s*(?:Inf|\d+\.?\d*))\s*dBm", opt)
    r["tx_dbm"] = m.group(1).replace(" ", "") if m else ""
    m = re.search(r"Media type:\s*(\S+)", text)
    r["optic"] = m.group(1) if m else ""
    m = re.search(r"Active alarms\s*:\s*(\S+)", text)
    if m and m.group(1).lower() != "none":
        r["optic"] = (r["optic"] + f" ALARM:{m.group(1)}").strip()
    return r


def parse_ciena(outputs, port):
    """Parse SAOS 'port show port <n>' / 'port show' table row + xcvr."""
    text = ""
    for k, v in outputs.items():
        if k.startswith("port show"):
            text += v + "\n"
    r = {"admin": "", "oper": "", "descr": "", "rx_dbm": "", "tx_dbm": "",
         "optic": ""}
    # table row: | name | type |Link| duration |XCVR|STP| Mode |AN|Link| ...
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 9 and cells[0] == str(port):
            r["oper"] = cells[2].lower()
            r["admin"] = "up" if cells[8].lower().startswith("ena") else "down"
            r["optic"] = cells[1]
            break
    xcvr = ""
    for k, v in outputs.items():
        if "xcvr" in k:
            xcvr = v
    m = re.search(r"Rx\s*(?:Optical)?\s*Power.*?(-?\d+\.?\d*)", xcvr, re.I)
    r["rx_dbm"] = m.group(1) if m else ""
    m = re.search(r"Tx\s*(?:Output)?\s*Power.*?(-?\d+\.?\d*)", xcvr, re.I)
    r["tx_dbm"] = m.group(1) if m else ""
    m = re.search(r"Wavelength.*?(\d{4}\.?\d*)", xcvr, re.I)
    if m:
        r["optic"] = (r["optic"] + " " + m.group(1) + "nm").strip()
    return r


def commands_for(vendor, port):
    if vendor == "nokia_sros":
        return [f"show port {port}"]
    if vendor == "cisco_xr":
        rsip = re.search(r"(\d+(?:/\d+)+)", port)
        cmds = [f"show interfaces {port}"]
        if rsip:
            cmds.append(f"show controllers optics {rsip.group(1)}")
        return cmds
    if vendor == "juniper_junos":
        return [f"show interfaces {port}",
                f"show interfaces diagnostics optics {port}"]
    if vendor == "ciena_saos":
        return [f"port show port {port}", f"port xcvr show port {port}"]
    return []


PARSERS = {"nokia_sros": parse_nokia, "cisco_xr": parse_xr,
           "juniper_junos": parse_juniper, "ciena_saos": parse_ciena}


# ---------------------------------------------------------------- runner

def check_target(host, port, vendor, username, password, logger):
    result = {f: "" for f in FIELDS}
    result.update(host=host, port=port, vendor=vendor or "?")

    print(f"\n--- {host} port {port} ---")
    result["ping"] = "ok" if ping_host(host) else "FAIL"
    logger.info(f"[{host}] ping: {result['ping']}")
    if result["ping"] == "FAIL":
        print("  ping failed — skipping SSH")
        result["error"] = "unreachable"
        return result

    base = {"ip": host, "username": username, "password": password,
            "port": 22, "timeout": 30}

    try:
        if not vendor:
            print("  autodetecting vendor...")
            guess = SSHDetect(**base, device_type="autodetect").autodetect()
            logger.info(f"[{host}] autodetect: {guess}")
            vendor = VENDOR_ALIASES.get(guess or "", guess)
            if vendor not in PARSERS:
                result["error"] = f"autodetect failed ({guess})"
                print(f"  {result['error']} — specify vendor in input")
                return result
            result["vendor"] = vendor

        outputs = {}
        with ConnectHandler(**base, device_type=vendor) as conn:
            for cmd in commands_for(vendor, port):
                logger.info(f"[{host}] sending: {cmd}")
                try:
                    out = conn.send_command(cmd, read_timeout=45)
                    outputs[cmd] = out
                    logger.info(f"[{host}] output for '{cmd}':\n{out}")
                except Exception as e:
                    outputs[cmd] = ""
                    logger.error(f"[{host}] '{cmd}' failed: {e}")

        result.update(PARSERS[vendor](outputs, port))
    except NetmikoAuthenticationException:
        result["error"] = "auth failed"
        logger.error(f"[{host}] authentication failed")
    except NetmikoTimeoutException:
        result["error"] = "ssh timeout"
        logger.error(f"[{host}] SSH timeout")
    except Exception as e:
        result["error"] = str(e)[:60]
        logger.error(f"[{host}] {e}")

    print(f"  admin={result['admin'] or '?'} oper={result['oper'] or '?'} "
          f"rx={result['rx_dbm'] or '?'}dBm tx={result['tx_dbm'] or '?'}dBm")
    return result


def load_targets(argv):
    """Returns list of (host, port, vendor_or_None)."""
    targets = []
    if argv[0] == "-f":
        with open(argv[1], newline="") as f:
            for row in csv.reader(f):
                row = [c.strip() for c in row if c.strip()]
                if not row or row[0].startswith("#"):
                    continue
                if len(row) < 2:
                    print(f"skipping bad line: {row}")
                    continue
                v = VENDOR_ALIASES.get(row[2].lower()) if len(row) > 2 else None
                targets.append((row[0], row[1], v))
    else:
        host, port = argv[0], argv[1]
        v = VENDOR_ALIASES.get(argv[2].lower()) if len(argv) > 2 else None
        targets.append((host, port, v))
    return targets


def print_table(results):
    cols = ["host", "port", "ping", "admin", "oper", "rx_dbm", "tx_dbm",
            "optic", "error"]
    widths = {c: max(len(c), max((len(str(r[c])) for r in results),
                                 default=0)) for c in cols}
    widths["host"] = min(widths["host"], 42)
    widths["optic"] = min(widths["optic"], 30)
    line = "  ".join(c.ljust(widths[c]) for c in cols)
    print("\n" + line)
    print("-" * len(line))
    for r in results:
        print("  ".join(str(r[c])[:widths[c]].ljust(widths[c]) for c in cols))


def main():
    if len(sys.argv) < 3 and not (len(sys.argv) == 3 and sys.argv[1] == "-f"):
        if len(sys.argv) < 2 or sys.argv[1] not in ("-f",) and len(sys.argv) < 3:
            print(__doc__)
            sys.exit(1)

    logger, ts = setup_logging()
    targets = load_targets(sys.argv[1:])
    if not targets:
        print("no targets found")
        sys.exit(1)

    username = input("Username: ")
    password = getpass.getpass("Password: ")

    results = [check_target(h, p, v, username, password, logger)
               for h, p, v in targets]

    print_table(results)

    csv_file = f"portcheck_results_{ts}.csv"
    with open(csv_file, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(results)
    print(f"\nresults: {csv_file}")
    print(f"raw log: portcheck_log_{ts}.txt")


if __name__ == "__main__":
    main()
