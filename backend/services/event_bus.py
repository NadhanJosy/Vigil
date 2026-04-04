import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Executor for running synchronous handlers without blocking the event loop
_executor = ThreadPoolExecutor(max_workers=4)


class EventBus:
    def __init__(self, max_queue_size: int = 1000):
        self._subscribers: dict[str, list] = {}
        self._max_queue = max_queue_size
        # FIX 8: Maintain a set of active tasks to prevent garbage collection
        # of fire-and-forget tasks created via publish_sync.
        self._background_tasks: set[asyncio.Task] = set()

    def subscribe(self, event_type: str, callback) -> None:
        self._subscribers.setdefault(event_type, []).append(callback)

    def unsubscribe(self, event_type: str, callback) -> None:
        if event_type in self._subscribers:
            self._subscribers[event_type].remove(callback)

    async def publish(self, event_type: str, payload: dict) -> None:
        """Publish an event to all subscribers.

        Async handlers are awaited directly. Sync handlers are run in a
        ThreadPoolExecutor to avoid blocking the event loop.
        """
        for callback in self._subscribers.get(event_type, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(payload)
                else:
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(_executor, callback, payload)
            except Exception as e:
                logger.error("Event bus callback error: %s", e)


    def publish_sync(self, event_type: str, payload: dict) -> None:
        """Synchronous wrapper for publish — for use from sync contexts.

        FIX 8: Tasks are stored in _background_tasks set to prevent garbage
        collection. A done callback removes them from the set when complete.
        """
        try:
            loop = asyncio.get_running_loop()
            # Already in async context — schedule via create_task
            task = loop.create_task(self.publish(event_type, payload))
            # Store reference to prevent garbage collection
            self._background_tasks.add(task)
            # Remove from set when done and log exceptions
            task.add_done_callback(self._on_task_done)
        except RuntimeError:
            # No running event loop — safe to create one
            asyncio.run(self.publish(event_type, payload))

    def _on_task_done(self, task: asyncio.Task) -> None:
        """Callback invoked when a background task completes."""
        # Remove from the active tasks set
        self._background_tasks.discard(task)
        # Log any exceptions
        if task.exception() is not None:
            exc = task.exception()
            logger.error(f"Event bus background task failed: {exc}", exc_info=exc)


event_bus = EventBus()
