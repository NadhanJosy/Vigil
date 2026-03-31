import json
import urllib.request


class SlackChannel:
    def __init__(self, url: str):
        self.url = url

    def send(self, alert: dict) -> None:
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{alert.get('ticker')} — {alert.get('signal_type')}",
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Action:*\n{alert.get('action', 'N/A')}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Edge:*\n{alert.get('edge_score', 'N/A')}",
                    },
                ],
            },
        ]
        if alert.get("summary"):
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": alert["summary"]},
                }
            )
        payload = json.dumps({"blocks": blocks}).encode("utf-8")
        req = urllib.request.Request(
            self.url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status not in (200, 204):
                raise Exception(f"Slack status {resp.status}")
