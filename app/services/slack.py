# app/services/slack.py
import httpx
from app.core.config import settings

async def send_slack_notification(message: str):
    """
    Sends a message to the configured Slack webhook URL.
    """
    if not settings.SLACK_WEBHOOK_URL:
        print("WARNING: SLACK_WEBHOOK_URL is not set. Skipping notification.")
        return

    payload = {"text": message}
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(settings.SLACK_WEBHOOK_URL, json=payload)
            response.raise_for_status() # Raises an exception for 4xx/5xx errors
            print(f"Successfully sent Slack notification.")
        except httpx.RequestError as e:
            print(f"Error sending Slack notification: {e}")