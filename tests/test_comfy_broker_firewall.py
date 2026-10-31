"""Source-only regression for the ComfyUI host backend nft loopback guard.

Never changes the live nftables ruleset or starts Comfy/GPU jobs.
Linux routes connect("0.0.0.0", port) to lo, which bypasses daddr 127.0.0.1 guards.
"""
from __future__ import annotations

import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy" / "comfy-broker-firewall"
UID = "61889"


class FirewallContractTests(unittest.TestCase):
    def test_guard_matches_all_loopback_routes_including_unspecified_alias(self):
        script = SCRIPT.read_text()
        self.assertIn(
            'meta oifname "lo" tcp dport 8189 meta skuid != $uid reject with tcp reset',
            script)
        # Reject a regression to an IPv4/IPv6 destination filter that misses 0.0.0.0.
        self.assertNotIn("ip daddr 127.0.0.1 tcp dport 8189", script)
        self.assertNotIn("ip6 daddr ::1 tcp dport 8189", script)

    def test_rootless_quadlet_is_guarded_before_backend_start(self):
        quadlet = (ROOT / "deploy" / "comfyui.container").read_text()
        self.assertIn("PublishPort=127.0.0.1:8189:8188", quadlet)
        self.assertIn(
            "ExecStartPre=/usr/bin/sudo -n /usr/local/libexec/comfy-broker-firewall check",
            quadlet,
        )

    def _check(self, simulated_rules):
        with tempfile.TemporaryDirectory(prefix="comfy-firewall-offline-") as scratch:
            fake = Path(scratch)
            (fake / "nft").write_text(
                '#!/bin/sh\n'
                'test "$1" = "-nn" && test "$2" = "list" || exit 29\n'
                'printf "%s\\n" "$MOCK_NFT_RULES"\n')
            (fake / "id").write_text(
                '#!/bin/sh\n'
                'if test "$1" = "-u" && test "$2" = "comfybroker"; then\n'
                f'  echo "{UID}"\n'
                'else\n'
                '  exec /usr/bin/id "$@"\n'
                'fi\n')
            (fake / "nft").chmod(0o755)
            (fake / "id").chmod(0o755)
            env = dict(os.environ,
                       PATH=str(fake) + os.pathsep + os.environ.get("PATH", ""),
                       MOCK_NFT_RULES=simulated_rules)
            return subprocess.run(["/bin/sh", str(SCRIPT), "check"],
                                  env=env, text=True, capture_output=True, check=False)

    def test_check_refuses_daddr_only_rule(self):
        old = (
            'table inet comfy_broker_guard { chain output { '
            'type filter hook output priority mangle; policy accept; '
            f'ip daddr 127.0.0.1 tcp dport 8189 meta skuid != {UID} reject with tcp reset'
            ' } }'
        )
        result = self._check(old)
        self.assertNotEqual(result.returncode, 0, result.stdout)

    def test_check_accepts_full_loopback_egress_guard(self):
        expected = (
            'table inet comfy_broker_guard { chain output { '
            'type filter hook output priority mangle; policy accept; '
            f'meta oifname "lo" tcp dport 8189 meta skuid != {UID} reject with tcp reset'
            ' } }'
        )
        result = self._check(expected)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_check_refuses_wrong_uid_or_hook(self):
        correct = (
            'table inet comfy_broker_guard { chain output { '
            'type filter hook output priority mangle; policy accept; '
            f'meta oifname "lo" tcp dport 8189 meta skuid != {UID} reject with tcp reset'
            ' } }'
        )
        self.assertNotEqual(self._check(correct.replace(UID, "1234")).returncode, 0)
        self.assertNotEqual(self._check(correct.replace("hook output", "hook input")).returncode, 0)


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux loopback behavior")
class LinuxLoopbackCanary(unittest.TestCase):
    def test_unspecified_connect_reaches_127_bound_tcp_listener(self):
        # Isolated ephemeral TCP listener, not Comfy, no live firewall mutations.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            server.settimeout(2)
            port = server.getsockname()[1]
            with socket.create_connection(("0.0.0.0", port), timeout=2) as client:
                peer, _ = server.accept()
                with peer:
                    client.sendall(b"P")
                    self.assertEqual(peer.recv(1), b"P")


if __name__ == "__main__":
    unittest.main()
