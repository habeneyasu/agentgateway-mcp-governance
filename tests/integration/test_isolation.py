"""Phase 9: network isolation and container hardening (Phase 3 controls)."""

import json
import socket
import subprocess

import pytest

from conftest import compose, container_python, requires_docker

pytestmark = requires_docker

SERVICES = ["mcp-server", "agentgateway"]


def inspect(service):
    container_id = compose("ps", "-q", service).stdout.strip()
    assert container_id, f"{service} is not running"
    out = subprocess.run(["docker", "inspect", container_id], capture_output=True, text=True, check=True).stdout
    return json.loads(out)[0]


def test_mcp_server_has_no_published_ports():
    assert not inspect("mcp-server")["NetworkSettings"]["Ports"].get("8000/tcp")


def test_mcp_server_container_ip_is_unreachable_from_the_host():
    addresses = [n["IPAddress"] for n in inspect("mcp-server")["NetworkSettings"]["Networks"].values() if n["IPAddress"]]
    assert addresses
    for address in addresses:
        with pytest.raises(OSError):
            socket.create_connection((address, 8000), timeout=2).close()


def test_gateway_ports_are_bound_to_loopback_only():
    bindings = [b for ports in inspect("agentgateway")["NetworkSettings"]["Ports"].values() if ports for b in ports]
    assert bindings
    assert all(b["HostIp"] == "127.0.0.1" for b in bindings), bindings


def test_mcp_server_has_no_outbound_network_access():
    result = container_python("mcp-server", (
        "import socket\n"
        "try:\n    socket.create_connection(('1.1.1.1', 443), 3).close(); print('REACHABLE')\n"
        "except OSError:\n    print('BLOCKED')\n"
    ))
    assert result.strip() == "BLOCKED"


@pytest.mark.parametrize("service", SERVICES)
def test_container_is_hardened(service):
    info = inspect(service)
    host = info["HostConfig"]
    assert info["Config"]["User"] not in ("", "0", "root")
    assert host["ReadonlyRootfs"] is True
    assert host["CapDrop"] == ["ALL"]
    assert "no-new-privileges:true" in host["SecurityOpt"]
