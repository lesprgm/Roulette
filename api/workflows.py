from js import WorkflowEntrypoint, WorkflowStep, WorkflowEvent
import json
import httpx

class TopUpWorkflow(WorkflowEntrypoint):
    async def run(self, event: WorkflowEvent, step: WorkflowStep):
        # Step 1: Check Queue Size
        # We need to call the QueueDO to get the size
        # To call a DO from a Workflow, we need the ID.
        # Typically we use a singleton ID for the global queue.
        env = self.env
        
        size_check = await step.do(
            "check_queue_size",
            self._check_size,
            env
        )
        
        if size_check >= 5: # Target fill
            return {"status": "healthy", "size": size_check}

        # Step 2: Generate Burst if low
        # We assume we have an internal helper or generic way to call LLM
        # For this migration, we might put the LLM call in a separate step or directly here
        # Note: Workflows can await long async tasks.
        
        generated_count = await step.do(
            "generate_burst",
            self._generate_and_enqueue,
            env,
            5 - size_check
        )
        
        return {"status": "refilled", "added": generated_count}

    async def _check_size(self, env):
        # Get the singleton ID for the queue
        idx = env.QUEUE_DO.idFromName("global_prefetch_queue")
        stub = env.QUEUE_DO.get(idx)
        resp = await stub.fetch("http://do/size")
        data = await resp.json()
        return data["size"]

    async def _generate_and_enqueue(self, env, needed):
        # Import here to avoid global scope issues in Workers sometimes
        from api.llm_client import generate_page_burst_async
        
        count = 0
        # We generate a burst. Note: make sure generate_page_burst_async uses httpx!
        # We'll need to update llm_client to support async/httpx first.
        # This is a placeholder for the logic:
        async for page in generate_page_burst_async(brief="", seed=123, count=needed, env=env):
            # Enqueue each page into DO
            idx = env.QUEUE_DO.idFromName("global_prefetch_queue")
            stub = env.QUEUE_DO.get(idx)
            await stub.fetch("http://do/enqueue", method="POST", body=json.dumps(page))
            count += 1
            
        return count
