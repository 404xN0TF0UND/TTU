"""Nokia_Retune.py — Nokia SR OS DWDM frequency retune, ITU-grid validated.

Built from automation candidate #3 (~60 sessions). Command sequence
mirrors Tuning Commands.txt exactly:

    configure exclusive
    port <port>
    dwdm frequency <freq-mhz>
    validate
    compare
    commit

The compare output is always captured and kept in the run log. The tool
refuses any frequency that is not on the ITU C-band 100 GHz grid
(channels 1-72, 190100-197200 GHz, per Fiberdyne grid reference).

Usage:
    python Nokia_Retune.py <host> <port> <frequency>

Frequency input formats (all label their unit explicitly in output):
    193.3        THz
    193300       GHz
    193300000    MHz (what SR OS takes on the CLI)
    ch33 / c33   ITU channel number
"""

from netmiko import ConnectHandler, NetmikoTimeoutException, NetmikoAuthenticationException
import getpass
import logging
import os
import re
import sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from PortCheck import parse_nokia

C_MS = 299_792_458  # speed of light, m/s

# ITU C-band 100 GHz grid: channel n -> 190000 + n*100 GHz, n = 1..72
ITU_GRID_GHZ = {190000 + n * 100: n for n in range(1, 73)}


def setup_logging():
    """Timestamped log file per run (same pattern as CienaCFM.py)."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f"nokiaretune_log_{ts}.txt"
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    return logging.getLogger(), log_file


def ghz_to_nm(freq_ghz):
    return C_MS / freq_ghz / 1e9 * 1e9  # m -> nm via GHz


def parse_frequency(text):
    """Parse a frequency in THz / GHz / MHz / channel form.

    Returns (freq_mhz, None) on success or (None, error_string).
    """
    t = str(text).strip().lower().replace(",", "").replace(" ", "")
    m = re.fullmatch(r"c(?:h)?(\d{1,2})", t)
    if m:
        ch = int(m.group(1))
        ghz = 190000 + ch * 100
        if ghz not in ITU_GRID_GHZ:
            return None, f"channel {ch} is off the 100 GHz C-band grid (1-72)"
        return ghz * 1000, None
    try:
        val = float(t)
    except ValueError:
        return None, f"can't parse frequency '{text}'"
    if 190 <= val <= 198:            # THz
        mhz = round(val * 1_000_000)
    elif 190_000 <= val <= 198_000:  # GHz
        mhz = round(val * 1000)
    elif 190_000_000 <= val <= 198_000_000:  # MHz
        mhz = round(val)
    elif 1 <= val <= 72 and val == int(val):  # bare channel number
        mhz = (190000 + int(val) * 100) * 1000
    else:
        return None, (f"'{text}' not recognized as THz (193.3), GHz (193300), "
                      "MHz (193300000), or channel (1-72)")
    return mhz, None


def validate_on_grid(freq_mhz):
    """Return grid info dict if freq is a valid 100 GHz C-band channel,
    else None."""
    if freq_mhz % 1000:
        return None
    ghz = freq_mhz // 1000
    ch = ITU_GRID_GHZ.get(ghz)
    if ch is None:
        return None
    return {"channel": ch, "freq_mhz": freq_mhz, "freq_ghz": ghz,
            "freq_thz": ghz / 1000.0, "wavelength_nm": round(ghz_to_nm(ghz), 2)}


def retune_sequence(port, freq_mhz):
    """Exact Tuning Commands.txt sequencing (frequency labeled in MHz)."""
    return [
        "configure exclusive",
        f"port {port}",
        f"dwdm frequency {freq_mhz}",
        "validate",
        "compare",
        "commit",
        "quit-config",
    ]


def get_port_state(conn, port, logger, host):
    """Run 'show port <port>' and parse admin/oper/wavelength/levels."""
    cmd = f"show port {port}"
    out = conn.send_command(cmd, read_timeout=45)
    logger.info(f"[{host}] {cmd}:\n{out}")
    state = parse_nokia({cmd: out}, port)
    m = re.search(r"TX Laser Wavelength\s*:\s*(\d+\.?\d*)\s*nm", out)
    state["wavelength_nm"] = m.group(1) if m else ""
    return state, out


def retune_target(host, port, freq_mhz, username, password, logger):
    """Retune one Nokia port. Returns dict with grid info, pre/post state,
    outputs (compare always captured), success flag."""
    grid = validate_on_grid(freq_mhz)
    result = {"host": host, "port": port, "grid": grid, "pre": {},
              "post": {}, "outputs": {}, "compare": "", "success": False,
              "error": ""}
    if grid is None:
        result["error"] = (f"{freq_mhz} MHz is not on the ITU 100 GHz C-band "
                           "grid — refusing to send")
        logger.error(f"[{host}] {result['error']}")
        return result

    device = {"ip": host, "username": username, "password": password,
              "device_type": "nokia_sros", "port": 22, "timeout": 30}
    try:
        with ConnectHandler(**device) as conn:
            result["pre"], _ = get_port_state(conn, port, logger, host)

            for cmd in retune_sequence(port, freq_mhz):
                logger.info(f"[{host}] sending: {cmd}")
                try:
                    out = conn.send_command_timing(cmd, read_timeout=90)
                    result["outputs"][cmd] = out
                    logger.info(f"[{host}] output for '{cmd}':\n{out}")
                    if cmd == "compare":
                        result["compare"] = out
                except Exception as e:
                    msg = f"'{cmd}' failed: {e}"
                    result["outputs"][cmd] = msg
                    result["error"] = msg
                    logger.error(f"[{host}] {msg}")
                    return result

            result["post"], _ = get_port_state(conn, port, logger, host)

        # verify: reported TX wavelength within 0.1 nm of the grid target
        try:
            got_nm = float(result["post"].get("wavelength_nm") or 0)
        except ValueError:
            got_nm = 0
        want_nm = grid["wavelength_nm"]
        if got_nm and abs(got_nm - want_nm) <= 0.1:
            result["success"] = True
            logger.info(f"[{host}] verified: TX wavelength {got_nm} nm ~ "
                        f"target {want_nm} nm (ch {grid['channel']})")
        else:
            result["error"] = (f"post-check: TX wavelength reads "
                               f"{got_nm or '?'} nm, expected ~{want_nm} nm "
                               "— verify manually (optic may still be tuning)")
            logger.error(f"[{host}] {result['error']}")
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


# ------------------------------------------------------------ web wrappers

def run_retune_preview(host, port, freq_text, username, password):
    """Read-only: validate frequency against grid and capture pre-state."""
    logger, log_file = setup_logging()
    logger.info("[INIT] Nokia retune PREVIEW (web) — read-only pass")
    freq_mhz, err = parse_frequency(freq_text)
    grid = validate_on_grid(freq_mhz) if freq_mhz else None
    out = {"host": host, "port": port, "freq_input": freq_text,
           "freq_mhz": freq_mhz, "grid": grid, "pre": {},
           "planned": [], "ok": False, "error": err or "", "log_file": log_file}
    if err:
        return out
    if grid is None:
        out["error"] = (f"{freq_mhz} MHz is not on the ITU 100 GHz C-band "
                        "grid (channels 1-72, 190100-197200 GHz)")
        return out
    out["planned"] = retune_sequence(port, freq_mhz)

    device = {"ip": host, "username": username, "password": password,
              "device_type": "nokia_sros", "port": 22, "timeout": 30}
    try:
        with ConnectHandler(**device) as conn:
            out["pre"], _ = get_port_state(conn, port, logger, host)
        out["ok"] = True
    except NetmikoAuthenticationException:
        out["error"] = "auth failed"
    except NetmikoTimeoutException:
        out["error"] = "ssh timeout"
    except Exception as e:
        out["error"] = str(e)[:80]
    if out["error"]:
        logger.error(f"[{host}] preview failed: {out['error']}")
    logger.info("[COMPLETE] Preview finished")
    return out


def run_retune_execute(host, port, freq_mhz, username, password):
    logger, log_file = setup_logging()
    logger.info("[INIT] Nokia retune EXECUTE (web)")
    result = retune_target(host, port, freq_mhz, username, password, logger)
    result["log_file"] = log_file
    result["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info("[COMPLETE] Execute finished")
    return result


# --------------------------------------------------------------------- CLI

def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    host, port, freq_text = sys.argv[1], sys.argv[2], sys.argv[3]

    freq_mhz, err = parse_frequency(freq_text)
    if err:
        print(f"frequency error: {err}")
        sys.exit(1)
    grid = validate_on_grid(freq_mhz)
    if grid is None:
        print(f"{freq_mhz} MHz is not on the ITU 100 GHz C-band grid")
        sys.exit(1)

    print(f"Target: ch {grid['channel']} = {grid['freq_thz']} THz = "
          f"{grid['freq_ghz']} GHz = {grid['wavelength_nm']} nm "
          f"(CLI value: {grid['freq_mhz']} MHz)")

    username = os.environ.get("TTU_SSH_USER") or input("SSH username: ")
    password = getpass.getpass("SSH password: ")

    logger, log_file = setup_logging()
    print(f"Logging to {log_file}\n")
    print("Planned sequence:")
    for cmd in retune_sequence(port, freq_mhz):
        print(f"    {cmd}")

    print(f"\nThis retunes {host} port {port} to {grid['freq_thz']} THz.")
    if input('Type "RETUNE" to proceed: ').strip() != "RETUNE":
        print("aborted — nothing sent")
        sys.exit(0)

    r = retune_target(host, port, freq_mhz, username, password, logger)
    if r["success"]:
        print(f"\nOK — {host} port {port} now at "
              f"{r['post'].get('wavelength_nm')} nm "
              f"(was {r['pre'].get('wavelength_nm') or '?'} nm)")
    else:
        print(f"\nFAILED — {r['error']}")
    if r["compare"]:
        print(f"\ncompare output:\n{r['compare']}")
    print(f"full log: {log_file}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted — no further commands sent.")
        sys.exit(1)
