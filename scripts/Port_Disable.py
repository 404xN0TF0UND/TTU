"""Port_Disable.py — one-way, vendor-aware port disable with pre/post capture.

Built from the #1 automation candidate in the log mining (~800 sessions,
Dec 2025 - Jun 2026): circuit turn-downs. The sessions never contain a
re-enable, so this tool is deliberately ONE-WAY — there is no enable path.
A typed confirmation ("DISABLE") is required before any config command.

Flow per target:
    1. ping + SSH, capture pre-state (admin/oper, light levels, description)
    2. show planned per-vendor command sequence, wait for confirmation
    3. execute disable sequence, commit/save
    4. re-run show, verify admin state is down, log before + after

Usage:
    python Port_Disable.py <host> <port> [vendor]
    python Port_Disable.py -f targets.csv

CSV format (one target per line, vendor optional):
    host,port[,vendor]

Port format per vendor (same as PortCheck.py):
    nokia   slot/mda/port           e.g. 1/1/10
    xr      full interface name     e.g. GigabitEthernet0/0/0/5
    juniper full interface name     e.g. ge-0/2/2, xe-0/1/3
    ciena   port number             e.g. 3

Vendor is autodetected via SSH if omitted.
"""

from netmiko import ConnectHandler, NetmikoTimeoutException, NetmikoAuthenticationException
from netmiko.ssh_autodetect import SSHDetect
import getpass
import logging
import os
import sys
import csv
from datetime import datetime

# Reuse the read-only checker: vendor aliases, show-command builders, parsers
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from PortCheck import (VENDOR_ALIASES, PARSERS, commands_for, ping_host,
                       check_target, print_table)


def setup_logging():
    """Timestamped log file per run (same pattern as CienaCFM.py)."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f"portdisable_log_{ts}.txt"
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    return logging.getLogger(), log_file


# ------------------------------------------------------- disable sequences
# Sequences mirror the exact workflows mined from the session logs.

def disable_sequence(vendor, port):
    """Config-mode command list that disables the port, ending back in
    operational mode. For display (confirm gate) and execution."""
    if vendor == "nokia_sros":                      # MD-CLI
        return [
            "configure exclusive",
            f"port {port} admin-state disable",
            "validate",
            "compare",
            "commit",
            "quit-config",
        ]
    if vendor == "cisco_xr":
        return [
            "configure exclusive",
            f"interface {port}",
            "shutdown",
            "commit",
            "end",
        ]
    if vendor == "juniper_junos":
        return [
            "configure exclusive",
            f"set interfaces {port} disable",
            "commit and-quit",
        ]
    if vendor == "ciena_saos":
        return [
            f"port disable port {port}",
            "configuration save",
        ]
    return []


def verify_command(vendor, port):
    """Show command used for the post-disable check."""
    return commands_for(vendor, port)[0]


def _post_ok(vendor, post):
    """True when the parsed post-state confirms the port is disabled."""
    admin = (post.get("admin") or "").lower()
    oper = (post.get("oper") or "").lower()
    return admin.startswith("down") or oper in ("down", "disabled")


# --------------------------------------------------------------- executor

def disable_target(host, port, vendor, username, password, logger,
                   pre=None):
    """Disable one port. Returns dict with pre/post state, outputs, success.

    Never runs config commands when the pre-state capture failed or the
    port is already admin-down (marked skipped instead).
    """
    result = {"host": host, "port": port, "vendor": vendor or "?",
              "pre": pre or {}, "post": {}, "outputs": {},
              "success": False, "skipped": False, "error": ""}

    # 1. pre-state (reuses the read-only checker: ping, SSH, parse)
    if pre is None:
        pre = check_target(host, port, vendor, username, password, logger)
        result["pre"] = pre
    if pre.get("error"):
        result["error"] = f"pre-check failed: {pre['error']}"
        logger.error(f"[{host}] {result['error']} — no config commands sent")
        return result
    vendor = VENDOR_ALIASES.get((pre.get("vendor") or vendor or "").lower(),
                                pre.get("vendor") or vendor)
    result["vendor"] = vendor
    if vendor not in PARSERS:
        result["error"] = f"unknown vendor '{vendor}'"
        logger.error(f"[{host}] {result['error']}")
        return result

    if (pre.get("admin") or "").lower().startswith("down"):
        result["skipped"] = True
        result["success"] = True
        result["error"] = "already admin-down — nothing sent"
        logger.info(f"[{host}] port {port} already admin-down, skipping")
        return result

    # 2. disable sequence
    device = {"ip": host, "username": username, "password": password,
              "device_type": vendor, "port": 22, "timeout": 30}
    try:
        with ConnectHandler(**device) as conn:
            for cmd in disable_sequence(vendor, port):
                logger.info(f"[{host}] sending: {cmd}")
                try:
                    out = conn.send_command_timing(cmd, read_timeout=90)
                    result["outputs"][cmd] = out
                    logger.info(f"[{host}] output for '{cmd}':\n{out}")
                except Exception as e:
                    msg = f"'{cmd}' failed: {e}"
                    result["outputs"][cmd] = msg
                    result["error"] = msg
                    logger.error(f"[{host}] {msg}")
                    return result

            # 3. post-state verify in the same session
            vcmd = verify_command(vendor, port)
            logger.info(f"[{host}] verify: {vcmd}")
            try:
                out = conn.send_command(vcmd, read_timeout=45)
                result["outputs"][vcmd] = out
                result["post"] = PARSERS[vendor]({vcmd: out}, port)
                logger.info(f"[{host}] post-state:\n{out}")
            except Exception as e:
                result["error"] = f"verify failed: {e}"
                logger.error(f"[{host}] {result['error']}")
                return result

        result["success"] = _post_ok(vendor, result["post"])
        if not result["success"]:
            result["error"] = (f"post-check: admin={result['post'].get('admin')}"
                               f" oper={result['post'].get('oper')} — "
                               "port may NOT be disabled, check manually")
            logger.error(f"[{host}] {result['error']}")
        else:
            logger.info(f"[{host}] port {port} confirmed disabled")
    except NetmikoAuthenticationException:
        result["error"] = "auth failed"
        logger.error(f"[{host}] authentication failed")
    except NetmikoTimeoutException:
        result["error"] = "ssh timeout"
        logger.error(f"[{host}] SSH timeout")
    except Exception as e:
        result["error"] = str(e)[:80]
        logger.error(f"[{host}] {e}")
    return result


# ---------------------------------------------------------- target parsing

def parse_targets_text(text):
    """Parse 'host,port[,vendor]' lines (textarea or CSV file contents).
    Returns (targets, errors): targets = list of (host, port, vendor|None)."""
    targets, errors = [], []
    for lineno, row in enumerate(csv.reader(text.splitlines()), 1):
        row = [c.strip() for c in row if c.strip()]
        if not row or row[0].startswith("#"):
            continue
        if len(row) < 2:
            errors.append(f"line {lineno}: need host,port — got {row}")
            continue
        vendor = None
        if len(row) > 2:
            vendor = VENDOR_ALIASES.get(row[2].lower())
            if vendor is None:
                errors.append(f"line {lineno}: unknown vendor '{row[2]}'")
                continue
        targets.append((row[0], row[1], vendor))
    return targets, errors


# ------------------------------------------------------------ web wrappers

def run_port_disable_preview(targets, username, password):
    """Pre-state capture for the web confirm gate. Read-only.
    Returns {'targets': [...], 'log_file': str}; each target dict carries
    pre-state fields plus the planned command sequence."""
    logger, log_file = setup_logging()
    logger.info("[INIT] Port disable PREVIEW (web) — read-only pass")
    out = []
    for host, port, vendor in targets:
        pre = check_target(host, port, vendor, username, password, logger)
        v = VENDOR_ALIASES.get((pre.get("vendor") or vendor or "").lower())
        out.append({
            "host": host, "port": port, "vendor": v or pre.get("vendor", "?"),
            "pre": pre,
            "planned": disable_sequence(v, port) if v in PARSERS else [],
            "ok": not pre.get("error") and v in PARSERS
                  and not (pre.get("admin") or "").lower().startswith("down"),
            "already_down": (pre.get("admin") or "").lower().startswith("down"),
        })
    logger.info("[COMPLETE] Preview finished")
    return {"targets": out, "log_file": log_file}


def run_port_disable_execute(targets, username, password, previews=None):
    """Execute the disable on all targets. previews (optional) is the list
    returned by run_port_disable_preview — reused as pre-state."""
    logger, log_file = setup_logging()
    logger.info("[INIT] Port disable EXECUTE (web)")
    pre_by_key = {}
    for p in (previews or []):
        pre_by_key[(p["host"], str(p["port"]))] = p["pre"]
    results = []
    for host, port, vendor in targets:
        pre = pre_by_key.get((host, str(port)))
        results.append(disable_target(host, port, vendor, username,
                                      password, logger, pre=pre))
    logger.info("[COMPLETE] Execute finished")
    return {"results": results, "log_file": log_file,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}


# --------------------------------------------------------------------- CLI

def main():
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    if argv[0] == "-f":
        with open(argv[1], newline="") as f:
            targets, errors = parse_targets_text(f.read())
    else:
        text = ",".join(argv[:3])
        targets, errors = parse_targets_text(text)
    for e in errors:
        print(f"skipping: {e}")
    if not targets:
        print("no valid targets")
        sys.exit(1)

    username = os.environ.get("TTU_SSH_USER") or input("SSH username: ")
    password = getpass.getpass("SSH password: ")

    logger, log_file = setup_logging()
    logger.info("[INIT] Port disable (CLI)")
    print(f"\nLogging to {log_file}")

    print("\n=== PRE-STATE (read-only) ===")
    previews = []
    for host, port, vendor in targets:
        pre = check_target(host, port, vendor, username, password, logger)
        previews.append(pre)
    print_table(previews)

    print("\n=== PLANNED COMMANDS ===")
    for (host, port, vendor), pre in zip(targets, previews):
        v = VENDOR_ALIASES.get((pre.get("vendor") or vendor or "").lower())
        state = "SKIP (already admin-down)" if \
            (pre.get("admin") or "").lower().startswith("down") else \
            ("SKIP (pre-check failed)" if pre.get("error") else "will run")
        print(f"\n{host} port {port} [{v or '?'}] — {state}")
        for cmd in disable_sequence(v, port) if v else []:
            print(f"    {cmd}")

    print("\nThis will DISABLE the ports above. There is no enable path.")
    if input('Type "DISABLE" to proceed: ').strip() != "DISABLE":
        print("aborted — nothing sent")
        logger.info("[ABORT] user did not confirm")
        sys.exit(0)

    print("\n=== EXECUTING ===")
    results = []
    for (host, port, vendor), pre in zip(targets, previews):
        r = disable_target(host, port, vendor, username, password, logger,
                           pre=pre)
        tag = "SKIPPED" if r["skipped"] else \
              ("OK — port disabled" if r["success"] else f"FAILED — {r['error']}")
        print(f"{host} port {port}: {tag}")
        results.append(r)

    ok = sum(1 for r in results if r["success"])
    print(f"\n{ok}/{len(results)} succeeded. Full log: {log_file}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted — no further commands sent.")
        sys.exit(1)
