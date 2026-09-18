"""ViciDial toolkit — Agno function tools for outbound call center operations.

Tools call Dograh's internal API which wraps the VicidialAdapter.
ViciDial credentials stay in Dograh — the bridge only sees the internal API.
"""

import logging
from livekit.agents import function_tool

logger = logging.getLogger(__name__)


def make_vicidial_tools(agent_proxy) -> list:
    """Create ViciDial tools if the session has a ViciDial call identity."""

    identity = agent_proxy._config.get("vicidial_identity")
    if not identity or identity.get("type") != "vicidial":
        return []

    org_id = agent_proxy._org_id

    @function_tool
    async def hangup_caller() -> str:
        """Hang up the customer leg via ViciDial. Use when the conversation is complete or the caller requests to end."""
        from app.dograh_client import DograhClient
        from app.config import settings

        client = DograhClient(settings)
        try:
            result = await client._post("/api/internal/vicidial/hangup", {
                "org_id": org_id,
                "identity": identity,
            })
            return f"Hangup {'OK' if result.get('ok') else 'failed'}: {result.get('message', '')}"
        except Exception as exc:
            logger.warning("ViciDial hangup failed: %s", exc)
            return "Hangup unavailable"

    @function_tool
    async def transfer_to_operator(in_group: str = "") -> str:
        """Transfer the caller to a human operator via ViciDial in-group.

        in_group: the ViciDial in-group ID to transfer to (e.g., 'SALES', 'SUPPORT').
        Leave empty or use 'source' for the original in-group.
        """
        from app.dograh_client import DograhClient
        from app.config import settings

        destination = in_group or "source"
        client = DograhClient(settings)
        try:
            result = await client._post("/api/internal/vicidial/transfer", {
                "org_id": org_id,
                "identity": identity,
                "destination": destination,
            })
            return f"Transfer {'OK' if result.get('ok') else 'failed'}: {result.get('message', '')}"
        except Exception as exc:
            logger.warning("ViciDial transfer failed: %s", exc)
            return "Transfer unavailable"

    @function_tool
    async def update_lead_fields(fields_json: str) -> str:
        """Update lead fields in ViciDial (disposition, notes, custom fields).

        fields_json: JSON string with field name → value pairs.
        Example: '{"status": "INTERESTED", "comments": "Wants callback tomorrow"}'
        """
        import json as _json
        from app.dograh_client import DograhClient
        from app.config import settings

        try:
            fields = _json.loads(fields_json)
        except _json.JSONDecodeError:
            return "Error: fields_json must be valid JSON"

        client = DograhClient(settings)
        try:
            result = await client._post("/api/internal/vicidial/update-lead", {
                "org_id": org_id,
                "identity": identity,
                "fields": fields,
            })
            return f"Lead update {'OK' if result.get('ok') else 'failed'}: {result.get('message', '')}"
        except Exception as exc:
            logger.warning("ViciDial lead update failed: %s", exc)
            return "Lead update unavailable"

    return [hangup_caller, transfer_to_operator, update_lead_fields]
