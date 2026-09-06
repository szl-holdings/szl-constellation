"""Startup and public-asset regression checks; no external product actions."""
import os
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["GRADIO_SSR_MODE"] = "true"
import app as constellation
from fastapi.testclient import TestClient


class RuntimeContract(unittest.TestCase):
    def test_mounted_console_and_public_map(self):
        with TestClient(constellation.app) as client:
            self.assertEqual(client.get("/").status_code, 200)
            self.assertEqual(client.get("/api/constellation/manifest").json()["state"], "DECLARED")
            self.assertEqual(client.get("/api/panels/status").json()["panels"], "MOUNTED")
            self.assertEqual(client.get("/panels/").status_code, 200)
            for name in ("estates.json", "verticals.json"):
                self.assertEqual(client.get("/static/" + name).status_code, 200)
            for name in ("app.py", "requirements.txt", "test_runtime_contract.py"):
                self.assertEqual(client.get("/static/" + name).status_code, 404)

    def test_mount_explicitly_disables_secondary_ssr_server(self):
        with patch.object(constellation, "build_consoles", return_value=object()), patch(
            "gradio.mount_gradio_app", side_effect=lambda app, *a, **kw: app
        ) as mount:
            constellation.create_app()
        self.assertIs(mount.call_args.kwargs["ssr_mode"], False)
        self.assertEqual(mount.call_args.kwargs["css"], constellation.CSS)

    def test_failed_mount_preserves_map_and_honest_status(self):
        with patch.object(constellation, "build_consoles", side_effect=RuntimeError("not public")):
            failed = constellation.create_app()
        with TestClient(failed) as client:
            self.assertEqual(client.get("/").status_code, 200)
            status = client.get("/api/panels/status").json()
            self.assertEqual(status, {"state": "UNAVAILABLE", "panels": "MOUNT_FAILED", "detail": "RuntimeError"})
            for route in ("/panels", "/panels/"):
                response = client.get(route)
                self.assertEqual(response.status_code, 503)
                self.assertNotIn("not public", response.text)

    def test_front_page_has_bounded_manifest_failure_path(self):
        source = (Path(__file__).parent / "holo/index.html").read_text(encoding="utf-8")
        self.assertIn("MANIFEST UNAVAILABLE.", source)
        self.assertIn("AbortSignal.timeout(15000)", source)
        self.assertIn("boot().catch(", source)
        self.assertIn("if(!r.ok)", source)


if __name__ == "__main__":
    unittest.main()
