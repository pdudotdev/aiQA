# conftest.py — Shared pytest fixtures for aiQA network test suites
#
# Provides device connection fixtures via scrapli.
# Connection details are loaded from data/INTENT.json.

import json
import pytest
from scrapli import Scrapli

INTENT_PATH = "data/INTENT.json"

# cli_style -> scrapli platform mapping
PLATFORM_MAP = {
    "ios": "cisco_iosxe",
    "eos": "arista_eos",
    "junos": "juniper_junos",
    "aos": "aruba_aoscx",
    "routeros": "mikrotik_routeros",
    "vyos": "linux",
}


def load_intent():
    """Load design intent / inventory from INTENT.json."""
    with open(INTENT_PATH, "r") as f:
        return json.load(f)


INTENT = load_intent()


@pytest.fixture(scope="session")
def device_conn():
    """
    Session-scoped fixture providing a dict of device_name -> Scrapli connection.

    Connections are opened lazily on first access and closed at session teardown.
    """
    connections = {}

    class LazyConnections:
        """Dict-like accessor that opens connections on first use."""

        def __getitem__(self, device_name):
            if device_name not in connections:
                routers = INTENT.get("routers", {})
                device_data = routers.get(device_name)
                if device_data is None:
                    raise KeyError(f"Device '{device_name}' not found in INTENT.json routers")

                host = device_data["host"]
                cli_style = device_data["cli_style"]
                platform = PLATFORM_MAP.get(cli_style)

                if platform is None:
                    raise ValueError(
                        f"No scrapli platform mapping for cli_style '{cli_style}'"
                    )

                conn = Scrapli(
                    host=host,
                    platform=platform,
                    auth_username="admin",
                    auth_password="admin",
                    auth_strict_key=False,
                    transport="system",
                )
                conn.open()
                connections[device_name] = conn

            return connections[device_name]

    yield LazyConnections()

    # Teardown: close all open connections
    for name, conn in connections.items():
        try:
            conn.close()
        except Exception:
            pass
