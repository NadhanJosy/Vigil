import json
import urllib.request


class WebhookChannel:
    def __init__(self, url: str):
        self.url = url

    def send(self, alert: dict) -> None:
        payload = json.dumps(
            {
                "content": f"**{alert.get('ticker')}** — {alert.get('signal_type')}\n{alert.get('summary', '')}",
                "embeds": [
                    {
                        "title": f"{alert.get('ticker')} {alert.get('action', '')}",
                        "color": 0x00FF00 if alert.get("action") == "ENTER" else 0xFF0000,
                        "fields": [
                            {
                                "name": "Edge Score",
                                "value": str(alert.get("edge_score", "N/A")),
                                "inline": True,
                            },
                            {
                                "name": "Regime",
                                "value": str(alert.get("regime", "N/A")),
                                "inline": True,
                            },
                        ],
                    }
                ],
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            self.url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status not in (200, 204):
                raise Exception(f"Webhook status {resp.status}")
