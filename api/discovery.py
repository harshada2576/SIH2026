"""Local Network Backend Discovery for SIH26184 CyberShield.

Advertises the backend on local network/hotspot via:
1. mDNS / DNS-SD (Zeroconf / Bonjour / NSD) on _cybershield._tcp.local. and _sih26184._tcp.local.
2. UDP Subnet Broadcast Responder on port 8888 for hotspot environments where multicast DNS is filtered.
"""
from __future__ import annotations

import json
import logging
import socket
import threading
import time
from typing import List, Optional

try:
    from zeroconf import IPVersion, ServiceInfo, Zeroconf
    ZEROCONF_AVAILABLE = True
except ImportError:
    ZEROCONF_AVAILABLE = False

log = logging.getLogger("discovery")


def get_all_lan_ips() -> List[str]:
    """Retrieve all non-loopback IPv4 addresses on host interfaces."""
    ips = set()
    # Method 1: Connect to external route probe
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass

    # Method 2: Hostname resolution
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                ips.add(ip)
    except Exception:
        pass

    if not ips:
        ips.add("127.0.0.1")
    return list(ips)


def get_primary_lan_ip() -> str:
    """Return the primary routable LAN IPv4 address."""
    ips = get_all_lan_ips()
    for ip in ips:
        if not ip.startswith("127."):
            return ip
    return "127.0.0.1"


class DiscoveryService:
    """Manages local mDNS and UDP broadcast discovery announcements for the CyberShield server."""

    def __init__(self, port: int = 5003, service_name: str = "CyberShield-Backend") -> None:
        self.port = port
        self.service_name = service_name
        self.zeroconf: Optional[Zeroconf] = None
        self.service_infos: List[ServiceInfo] = []
        self.udp_sock: Optional[socket.socket] = None
        self.running = False
        self._udp_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self.running:
            return
        self.running = True

        lan_ip = get_primary_lan_ip()
        lan_ips = get_all_lan_ips()
        raw_ips = [socket.inet_aton(ip) for ip in lan_ips if not ip.startswith("127.")]
        if not raw_ips:
            raw_ips = [socket.inet_aton(lan_ip)]

        props = {
            b"version": b"1.0.0",
            b"project": b"SIH26184",
            b"app": b"CyberShield",
            b"api": b"/cases",
            b"ws": b"/ws",
        }

        # 1. mDNS / Zeroconf Service Advertising
        if ZEROCONF_AVAILABLE:
            try:
                self.zeroconf = Zeroconf(ip_version=IPVersion.V4Only)

                # Advertise standard custom service type
                info_cybershield = ServiceInfo(
                    type_="_cybershield._tcp.local.",
                    name=f"{self.service_name}._cybershield._tcp.local.",
                    port=self.port,
                    properties=props,
                    addresses=raw_ips,
                    server=f"{socket.gethostname().split('.')[0]}.local.",
                )
                self.zeroconf.register_service(info_cybershield)
                self.service_infos.append(info_cybershield)

                # Advertise project-specific alias
                info_sih = ServiceInfo(
                    type_="_sih26184._tcp.local.",
                    name=f"SIH26184-Defense._sih26184._tcp.local.",
                    port=self.port,
                    properties=props,
                    addresses=raw_ips,
                    server=f"{socket.gethostname().split('.')[0]}.local.",
                )
                self.zeroconf.register_service(info_sih)
                self.service_infos.append(info_sih)

                # Advertise generic http type for broader compatibility
                info_http = ServiceInfo(
                    type_="_http._tcp.local.",
                    name=f"CyberShield-HTTP._http._tcp.local.",
                    port=self.port,
                    properties=props,
                    addresses=raw_ips,
                    server=f"{socket.gethostname().split('.')[0]}.local.",
                )
                self.zeroconf.register_service(info_http)
                self.service_infos.append(info_http)

                log.info(f"[DISCOVERY] mDNS registered: _cybershield._tcp.local. on {lan_ip}:{self.port}")
            except Exception as e:
                log.warning(f"[DISCOVERY] mDNS registration warning: {e}")
        else:
            log.warning("[DISCOVERY] Zeroconf package not available; relying on UDP broadcast discovery responder.")

        # 2. UDP Broadcast Discovery Responder (Port 8888)
        self._start_udp_responder()

    def _start_udp_responder(self) -> None:
        try:
            self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                self.udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            except Exception:
                pass
            self.udp_sock.bind(("0.0.0.0", 8888))
            self.udp_sock.settimeout(1.0)

            def _udp_loop():
                log.info(f"[DISCOVERY] UDP Broadcast responder listening on 0.0.0.0:8888")
                while self.running and self.udp_sock:
                    try:
                        data, addr = self.udp_sock.recvfrom(2048)
                        text = data.decode("utf-8", errors="ignore").strip()
                        if "CYBERSHIELD_DISCOVER" in text or "SIH26184_DISCOVER" in text:
                            lan_ip = get_primary_lan_ip()
                            payload = {
                                "service": "cybershield",
                                "project": "SIH26184",
                                "version": "1.0.0",
                                "ip": lan_ip,
                                "port": self.port,
                                "baseUrl": f"http://{lan_ip}:{self.port}",
                                "wsUrl": f"ws://{lan_ip}:{self.port}/ws",
                                "hostname": socket.gethostname(),
                            }
                            resp_msg = f"CYBERSHIELD_BACKEND:{json.dumps(payload)}\n".encode("utf-8")
                            self.udp_sock.sendto(resp_msg, addr)
                            log.info(f"[DISCOVERY] Answered discovery probe from {addr[0]}:{addr[1]} -> {lan_ip}:{self.port}")
                    except socket.timeout:
                        continue
                    except Exception as e:
                        if self.running:
                            log.debug(f"[DISCOVERY] UDP responder notice: {e}")
                        break

            self._udp_thread = threading.Thread(target=_udp_loop, name="CyberShield-UDPDiscovery", daemon=True)
            self._udp_thread.start()
        except Exception as e:
            log.warning(f"[DISCOVERY] Could not bind UDP discovery socket on 8888: {e}")

    def stop(self) -> None:
        self.running = False
        if self.zeroconf and self.service_infos:
            for s in self.service_infos:
                try:
                    self.zeroconf.unregister_service(s)
                except Exception:
                    pass
            try:
                self.zeroconf.close()
            except Exception:
                pass
            self.zeroconf = None
            self.service_infos = []

        if self.udp_sock:
            try:
                self.udp_sock.close()
            except Exception:
                pass
            self.udp_sock = None
        log.info("[DISCOVERY] Discovery service stopped.")
