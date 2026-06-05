
import vkbottle.polling.bot_polling as bp

_orig_get_event = bp.BotPolling.get_event

async def patched_get_event(self, server):
    return await self.api.http_client.request_json(
        url=server["server"],
        method="POST",
        params={
            "act": "a_check",
            "key": server["key"],
            "ts": server["ts"],
            "wait": self.wait,
            "version": 3,
        },
        timeout=__import__("aiohttp", fromlist=["ClientTimeout"]).ClientTimeout(total=self.wait + 10),
    )

bp.BotPolling.get_event = patched_get_event
print("vkbottle LP patched: added version=3 parameter")

