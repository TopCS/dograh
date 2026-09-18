"""LiveKit SIP telephony provider for outbound campaign calls.

This provider uses LiveKit Cloud SIP trunks for outbound calls,
dispatching them directly to the dograh-livekit AgentServer instead
of going through Pipecat pipelines.
"""

import json
from typing import TYPE_CHECKING, Any

from loguru import logger

from api.services.telephony.base import CallInitiationResult, TelephonyProvider

if TYPE_CHECKING:
    pass  # No fastapi imports needed at class level


class LiveKitSipProvider(TelephonyProvider):
    """Outbound calls via LiveKit SIP.

    This provider does NOT use Pipecat. It creates a LiveKit room (with an
    agent dispatch for the dograh-agent worker), then originates an outbound
    SIP call into that room via create_sip_participant. Mirrors the LiveKit
    OSS outbound pattern used in Luminai's outbound-engine.

    For LiveKit OSS the room must be created with agents=[RoomAgentDispatch]
    BEFORE create_sip_participant — OSS has no Cloud-only auto agent_dispatch
    on create_sip_participant.
    """

    PROVIDER_NAME = "livekit_sip"
    WEBHOOK_ENDPOINT = ""  # Not used — LiveKit dispatches directly to AgentServer

    def __init__(self, config: dict[str, Any]):
        self._config = config
        self._sip_trunk_id = config.get("sip_trunk_id", "")
        self.from_numbers = config.get("from_numbers", [])

    async def initiate_call(
        self,
        to_number: str,
        webhook_url: str,
        workflow_run_id: int,
        from_number: str | None = None,
        **kwargs,
    ) -> CallInitiationResult:
        """Initiate outbound SIP call via LiveKit."""
        import os
        from livekit import api as lk_api

        lk_url = os.getenv("LIVEKIT_URL", "").replace("ws://", "http://")
        lk_api_key = os.getenv("LIVEKIT_API_KEY", "")
        lk_api_secret = os.getenv("LIVEKIT_API_SECRET", "")

        if not all([lk_url, lk_api_key, lk_api_secret]):
            raise RuntimeError("LiveKit credentials not configured")

        lkapi = lk_api.LiveKitAPI(
            url=lk_url,
            api_key=lk_api_key,
            api_secret=lk_api_secret,
        )
        try:
            room_name = f"dograh-call-{workflow_run_id}"
            agent_name = os.getenv("DOGRAH_LIVEKIT_AGENT", "dograh-agent")

            metadata = json.dumps({
                "workflow_id": str(kwargs.get("workflow_id", "")),
                "org_id": str(kwargs.get("organization_id", "")),
                "channel": "voice_sip",
                "sender_phone": to_number,
                "campaign_id": str(kwargs.get("campaign_id", "")),
                "lead_id": str(kwargs.get("lead_id", "")),
            })

            # STEP 1 (OSS-critical): create the room WITH the agent dispatch.
            # LiveKit OSS has no auto agent_dispatch on create_sip_participant —
            # the room must carry agents=[RoomAgentDispatch] so the worker gets
            # the job when the SIP participant joins.
            await lkapi.room.create_room(
                lk_api.CreateRoomRequest(
                    name=room_name,
                    agents=[lk_api.RoomAgentDispatch(agent_name=agent_name)],
                    metadata=metadata,
                )
            )
            logger.info("LiveKit room created with agent dispatch: room={} agent={}", room_name, agent_name)

            # STEP 2: originate the outbound SIP leg into that room.
            participant = await lkapi.sip.create_sip_participant(
                lk_api.CreateSIPParticipantRequest(
                    room_name=room_name,
                    sip_trunk_id=self._sip_trunk_id,
                    participant_identity=f"sip_out_{workflow_run_id}",
                    participant_name=to_number,
                    sip_call_to=to_number,
                    wait_until_answered=True,
                )
            )

            call_id = participant.participant_id or f"lk_{workflow_run_id}"
            logger.info(
                "LiveKit SIP outbound call: room={} call_id={} to={}",
                room_name, call_id, to_number,
            )

            return CallInitiationResult(
                call_id=call_id,
                status="initiated",
                caller_number=from_number,
                provider_metadata={
                    "room_name": room_name,
                    "call_id": call_id,
                },
            )

        finally:
            await lkapi.aclose()
