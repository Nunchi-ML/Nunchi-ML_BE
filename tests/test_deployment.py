"""외부 서비스 없이 배포 커밋·실패·완료 판정과 실제 응답 검수 흐름을 확인."""
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts.deploy_render import main, wait_live
from scripts.install_model import model_source
from scripts.smoke_test import smoke

SHA = "a" * 40


class DeploymentTests(unittest.TestCase):
    def test_waits_for_exact_commit(self):
        states = iter([{"status": "build_in_progress"}, {"status": "live", "commit": {"id": SHA}}])
        wait_live(lambda: next(states), SHA, sleep=lambda _: None)

    def test_different_commit_is_not_success(self):
        with self.assertRaisesRegex(RuntimeError, "different commit"):
            wait_live(lambda: {"status": "live", "commit": {"id": "b" * 40}}, SHA)

    def test_failed_deploy_does_not_pass_health(self):
        with self.assertRaisesRegex(RuntimeError, "build_failed"):
            wait_live(lambda: {"status": "build_failed"}, SHA)

    def test_timeout_is_a_failure(self):
        ticks = iter([0, 2])
        with self.assertRaises(TimeoutError):
            wait_live(lambda: {}, SHA, timeout=1, clock=lambda: next(ticks))

    def test_model_override_requires_url_and_hash(self):
        with self.assertRaisesRegex(ValueError, "together"):
            model_source("not-used.json", "https://example.com", None)

    def test_deploy_calls_pinned_commit_and_checks_actual_model(self):
        service = {"autoDeploy": "no", "branch": "main", "serviceDetails": {"url": "https://nunchi.onrender.com"}}
        replies = [service, {"id": "dep-example"}, {"status": "live", "commit": {"id": SHA}}]
        with patch.dict(os.environ, {"RENDER_API_KEY": "unit-test-only", "RENDER_SERVICE_ID": "srv-example", "GITHUB_SHA": SHA}, clear=True), \
             patch("scripts.deploy_render.api", side_effect=replies) as api, \
             patch("scripts.deploy_render.model_source", return_value=("url", "hash")), \
             patch("scripts.deploy_render.download", return_value=b"bundle"), \
             patch("scripts.deploy_render.unpack"), patch("scripts.deploy_render.smoke") as verify:
            main()
            self.assertEqual(api.call_args_list[1].args[2]["commitId"], SHA)
            verify.assert_called_once_with("https://nunchi.onrender.com", "models/model2-pilot-v1", None)

    def test_smoke_checks_all_reference_responses(self):
        directory = Path(os.environ["MODEL_DIR"])
        expected = json.loads((directory / "reference/expected.json").read_text(encoding="utf-8"))
        replies = [(json.dumps({"status": "ok", "model2": "ready"}).encode(), {}),
                   (json.dumps({"paths": {"/health": {}, "/predict/glare": {}}}).encode(), {}),
                   (b"SwaggerUIBundle", {})]
        replies += [(json.dumps(item["expected"]).encode(), {}) for item in expected]
        with patch("scripts.smoke_test.request", side_effect=replies) as call:
            smoke("https://nunchi.onrender.com", directory)
            self.assertEqual(call.call_count, 6)
            self.assertIn(b"Content-Type: image/jpeg", call.call_args.args[2])

    def test_smoke_rejects_unready_model(self):
        with patch("scripts.smoke_test.request", return_value=(b'{"status":"ok","model2":"missing"}', {})):
            with self.assertRaisesRegex(RuntimeError, "not ready"):
                smoke("https://nunchi.onrender.com", ".")


if __name__ == "__main__":
    unittest.main()
