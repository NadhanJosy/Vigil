import logging


class EventBus:
    def __init__(self, max_queue_size: int = 1000):
        self._subscribers: dict[str, list] = {}
        self._max_queue = max_queue_size

    def subscribe(self, event_type: str, callback) -> None:
        self._subscribers.setdefault(event_type, []).append(callback)

    def unsubscribe(self, event_type: str, callback) -> None:
        if event_type in self._subscribers:
            self._subscribers[event_type].remove(callback)

    def publish(self, event_type: str, payload: dict) -> None:
        for callback in self._subscribers.get(event_type, []):
            try:
                callback(payload)
            except Exception as e:
                logging.error(f"Event bus callback error: {e}")


event_bus = EventBus()
