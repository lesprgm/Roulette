from workers import WorkerEntrypoint
from main import app
import asgi

class Default(WorkerEntrypoint):
    async def fetch(self, request):
        # Inject the environment (bindings) into the request scope
        # This allows FastAPI endpoints to access env.ASSETS_KV, env.QUEUE_DO, etc.
        # via request.scope["env"]
        return await asgi.fetch(app, request, self.env)
