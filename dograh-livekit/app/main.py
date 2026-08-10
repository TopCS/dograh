"""LiveKit AgentServer entrypoint for dograh-livekit."""

import os
import asyncio
import logging
from livekit import agents
from livekit.agents import AgentServer

from app.config import settings

# ── Pre-import livekit plugins on the MAIN THREAD ────────────────────────
# LiveKit Agents requires plugins to be registered on the main thread. Jobs
# run on worker threads (JobExecutorType.THREAD below), so plugin modules
# must be imported here — before AgentServer is constructed — or their
# register_plugin() raises "Plugins must be registered on the main thread".
from livekit.plugins import google as _p_google  # noqa: F401, E402
from livekit.plugins import openai as _p_openai  # noqa: F401, E402
from livekit.plugins import deepgram as _p_deepgram  # noqa: F401, E402
from livekit.plugins import silero as _p_silero  # noqa: F401, E402
from livekit.plugins import cartesia as _p_cartesia  # noqa: F401, E402

os.environ["GOOGLE_API_KEY"] = settings.google_api_key
if settings.google_application_credentials:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_application_credentials
if settings.google_cloud_project:
    os.environ["GOOGLE_CLOUD_PROJECT"] = settings.google_cloud_project
os.environ["OPENAI_API_KEY"] = settings.openai_api_key
os.environ["LIVEKIT_URL"] = settings.livekit_url
os.environ["LIVEKIT_API_KEY"] = settings.livekit_api_key
os.environ["LIVEKIT_API_SECRET"] = settings.livekit_api_secret

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

server = AgentServer(
    ws_url=settings.livekit_url,
    api_key=settings.livekit_api_key,
    api_secret=settings.livekit_api_secret,
    port=0,
    num_idle_processes=1,
    load_threshold=1.0,
    job_executor_type=agents.JobExecutorType.THREAD,
)


@server.rtc_session(agent_name="dograh-agent")
async def dograh_session(ctx: agents.JobContext):
    from app.entrypoint import lumina_session
    await lumina_session(ctx)


async def serve():
    await server.run()


if __name__ == "__main__":
    asyncio.run(serve())
