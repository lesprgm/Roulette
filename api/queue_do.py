import json
from js import Response
from durable_objects import DurableObject

class PrefetchQueueDO(DurableObject):
    """
    Durable Object Acting as the Single Source of Truth for the Prefetch Queue.
    Maintains:
      1. A list of page_ids (order matters).
      2. Deduplication set (via checking id existence).
    """
    
    def __init__(self, state, env):
        self.state = state
        self.env = env
        # Initialize storage if empty
        self.state.blockConcurrencyWhile(self._init_storage)

    async def _init_storage(self):
        # We store the queue simply as a list of IDs in the DO's storage
        queue = await self.state.storage.get("queue")
        if queue is None:
            await self.state.storage.put("queue", [])

    async def fetch(self, request):
        """
        Public API for the DO.
        Routes:
          POST /enqueue -> Body: {page_json}
          POST /dequeue -> Returns: {page_json} or 404
          GET  /size    -> Returns: {count}
        """
        url = request.url
        method = request.method

        if method == "POST" and url.endswith("/enqueue"):
            data = await request.json()
            return await self.enqueue(data)

        if method == "POST" and url.endswith("/dequeue"):
            return await self.dequeue()

        if method == "GET" and url.endswith("/size"):
            queue = await self.state.storage.get("queue")
            return Response.new(json.dumps({"size": len(queue)}), headers={"content-type": "application/json"})

        return Response.new("Not Found", status=404)

    async def enqueue(self, page):
        """
        1. Generate ID (hash of skeleton usually, or random).
        2. Check if ID exists (dedupe).
        3. Write content to KV (ASSETS_KV).
        4. Add ID to local queue list.
        """
        # Simple ID generation for now (in real app, use skeleton hash passed from caller)
        # Assuming page object has an "id" or we make one
        import hashlib
        # Use skeleton hash if available, else content hash
        # Ideally the caller has already computed the skeleton hash for dedupe
        # For this v1, let's assume the caller passes { "page": {...}, "id": "sig_..." }
        
        # If payload is just the page dict, let's compute a hash
        content_str = json.dumps(page, sort_keys=True)
        pid = hashlib.sha256(content_str.encode('utf-8')).hexdigest()
        
        # Dedupe check: Is this ID already in our queue?
        queue = await self.state.storage.get("queue")
        if pid in queue:
            return Response.new(json.dumps({"status": "duplicate", "id": pid}), status=200)

        # Write payload to KV (fast global read)
        await self.env.ASSETS_KV.put(pid, content_str)

        # Update Queue
        queue.append(pid)
        await self.state.storage.put("queue", queue)

        return Response.new(json.dumps({"status": "enqueued", "id": pid, "queue_size": len(queue)}), status=201)

    async def dequeue(self):
        """
        1. Pop head ID.
        2. If empty, return 404.
        3. Fetch content from KV.
        4. Delete content from KV (cleanup).
        5. Return content.
        """
        queue = await self.state.storage.get("queue")
        if not queue:
            return Response.new(json.dumps({"error": "empty"}), status=404, headers={"content-type": "application/json"})

        pid = queue.pop(0)
        await self.state.storage.put("queue", queue)

        # Fetch from KV
        content = await self.env.ASSETS_KV.get(pid)
        
        # Fire-and-forget delete from KV? 
        # Actually, for reliability, we might want to keep it briefly or use a TTL
        # But here we delete to keep it clean.
        # Note: await is safer to ensure it's gone, but adds latency. 
        # Since it's a backend helper, latency is ok.
        await self.env.ASSETS_KV.delete(pid)

        if not content:
            # Race condition edge case: ID in queue but KV missing?
            # Start recursion or return error (caller retries)
            return Response.new(json.dumps({"error": "corrupt_pointer"}), status=500, headers={"content-type": "application/json"})

        return Response.new(content, headers={"content-type": "application/json"})
