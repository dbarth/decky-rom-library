"""The handheld's DSU server, which sends its gyroscope to Eden and Dolphin over UDP: on the SteamOS ARM
port, qcom-motion.service."""
HOST = "127.0.0.1"
PORT = 26760

# The kernel's tables of UDP sockets.
TABLES = ("/proc/net/udp", "/proc/net/udp6")


def running():
    """Tell whether a program listens on the DSU port."""
    for table in TABLES:
        try:
            with open(table) as f:
                for line in list(f)[1:]:
                    local = line.split()[1]
                    if int(local.rsplit(":", 1)[1], 16) == PORT:
                        return True
        except (OSError, IndexError, ValueError):
            continue
    return False
