import subprocess, shlex

def _run(cmd: str) -> str:
    return subprocess.check_output(shlex.split(cmd), text=True).strip()

def nmcli(args: str) -> str:
    return _run(f"nmcli {args}")

def is_wifi_connected() -> bool:
    try:
        out = nmcli("-t -f DEVICE,STATE device status")
        for line in out.splitlines():
            parts = line.split(":")
            if len(parts) >= 2 and parts[0] == "wlan0" and parts[1] == "connected":
                return True
        return False
    except Exception:
        return False

def wifi_signal():
    try:
        # active connection details
        out = nmcli("-t -f IN-USE,SSID,SIGNAL device wifi")
        for line in out.splitlines():
            if line.startswith("*:"):
                parts = line.split(":")
                if len(parts) >= 3 and parts[2].isdigit():
                    return int(parts[2])
        return None
    except Exception:
        return None

def scan_networks():
    try:
        nmcli("device wifi rescan")
        out = nmcli("-t -f SSID,SIGNAL,SECURITY device wifi list")
        nets = []
        seen = set()
        for line in out.splitlines():
            ssid, signal, security = (line.split(":")+["",""])[:3]
            if ssid and ssid not in seen:
                seen.add(ssid)
                nets.append({"ssid": ssid, "signal": int(signal) if signal.isdigit() else None, "security": security})
        return nets
    except Exception:
        return []

def connect_wifi(ssid: str, password: str = "") -> bool:
    try:
        if password:
            nmcli(f'device wifi connect "{ssid}" password "{password}" ifname wlan0')
        else:
            nmcli(f'device wifi connect "{ssid}" ifname wlan0')
        return True
    except subprocess.CalledProcessError:
        return False

def ensure_ap(ssid: str, password: str) -> bool:
    try:
        nmcli(f'device wifi hotspot ifname wlan0 ssid "{ssid}" password "{password}"')
        return True
    except subprocess.CalledProcessError:
        return False