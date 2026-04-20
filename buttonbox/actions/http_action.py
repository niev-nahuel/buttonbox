import json as json_mod
import logging
import threading
import urllib.request
from .base import BaseAction, register_action

log = logging.getLogger(__name__)


@register_action("http")
class HttpAction(BaseAction):
    def execute(self) -> None:
        url     = self.config.get("url", "")
        method  = self.config.get("method", "GET").upper()
        body    = self.config.get("body")
        headers = self.config.get("headers", {})

        def _request() -> None:
            try:
                data = json_mod.dumps(body).encode() if body is not None else None
                req  = urllib.request.Request(url, data=data, method=method)
                req.add_header("Content-Type", "application/json")
                for k, v in headers.items():
                    req.add_header(k, v)
                with urllib.request.urlopen(req, timeout=5) as resp:
                    log.debug("HTTP %s %s → %s", method, url, resp.status)
            except Exception as exc:  # noqa: BLE001
                log.error("HTTP request failed: %s", exc)

        threading.Thread(target=_request, daemon=True).start()

    @classmethod
    def describe(cls) -> str:
        return "Send an HTTP request (webhooks, REST APIs, Home Assistant, MQTT-over-HTTP, …)"

    @classmethod
    def example(cls) -> dict:
        return {
            "type": "http",
            "url": "http://homeassistant.local:8123/api/services/light/toggle",
            "method": "POST",
            "headers": {"Authorization": "Bearer YOUR_TOKEN"},
            "body": {"entity_id": "light.living_room"},
        }
