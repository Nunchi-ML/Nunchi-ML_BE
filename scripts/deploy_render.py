"""검증한 commit SHA만 Render에 배포하고 해당 배포의 live 상태를 기다린다."""
import json
import os
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .install_model import download, model_source, unpack
from .smoke_test import smoke


def api(key, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = Request("https://api.render.com/v1/" + path, data=data,
                  headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=45) as response:
            return json.load(response)
    except HTTPError as error:
        raise RuntimeError(f"Render API returned HTTP {error.code}") from None
    except URLError:
        raise RuntimeError("Render API connection failed") from None


def wait_live(get_deploy, commit, timeout=1200, interval=10, clock=time.monotonic, sleep=time.sleep):
    deadline = clock() + timeout
    while clock() < deadline:
        deployment = get_deploy()
        status = deployment["status"]
        print("Render deploy status:", status, flush=True)
        if status == "live":
            if deployment.get("commit", {}).get("id") != commit:
                raise RuntimeError("Render deployed a different commit")
            return deployment
        if status in {"build_failed", "update_failed", "canceled", "deactivated", "pre_deploy_failed"}:
            raise RuntimeError("Render deployment failed: " + status)
        sleep(interval)
    raise TimeoutError("Render deployment did not become live within the time limit")


def main():
    key = os.getenv("RENDER_API_KEY", "")
    service_id = os.getenv("RENDER_SERVICE_ID", "")
    commit = os.getenv("GITHUB_SHA", "")
    if not key or not re.fullmatch(r"srv-[a-z0-9]+", service_id) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Configure RENDER_API_KEY, RENDER_SERVICE_ID and a full GITHUB_SHA")
    # Check the service before triggering anything; auto-deploys must stay disabled.
    service = api(key, f"services/{service_id}")
    if service.get("autoDeploy") != "no" or service.get("branch") != "main":
        raise ValueError("Configure Render branch=main and autoDeploy=no for Actions-controlled CD")
    base_url = service["serviceDetails"]["url"]
    url, digest = model_source("deployment/model.json")
    unpack(download(url), digest, "models/model2-pilot-v1")
    created = api(key, f"services/{service_id}/deploys", {"commitId": commit, "clearCache": "do_not_clear"})
    deploy_id = created["id"]
    if not re.fullmatch(r"dep-[a-z0-9]+", deploy_id):
        raise ValueError("Unexpected Render deployment ID")
    wait_live(lambda: api(key, f"services/{service_id}/deploys/{deploy_id}"), commit)
    smoke(base_url, "models/model2-pilot-v1", os.getenv("FRONTEND_ORIGIN") or None)


if __name__ == "__main__":
    main()
