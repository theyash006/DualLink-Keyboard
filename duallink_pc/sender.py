from __future__ import annotations

import collections
import threading
import time
from dataclasses import dataclass
from typing import Callable

from .protocol import InputEvent
from .transports import Transport


@dataclass
class SenderStats:
    queued: int = 0
    sent: int = 0
    dropped: int = 0
    reconnects: int = 0
    connected: bool = False
    last_error: str = ""


class EventBuffer:
    def __init__(self, maxlen: int) -> None:
        self._items: collections.deque[InputEvent] = collections.deque(maxlen=maxlen)
        self._condition = threading.Condition()
        self.dropped = 0

    def push(self, event: InputEvent) -> None:
        with self._condition:
            if len(self._items) == self._items.maxlen:
                self._items.popleft()
                self.dropped += 1
            self._items.append(event)
            self._condition.notify()

    def push_left(self, event: InputEvent) -> None:
        with self._condition:
            if len(self._items) == self._items.maxlen:
                self._items.pop()
                self.dropped += 1
            self._items.appendleft(event)
            self._condition.notify()

    def pop(self, timeout_s: float) -> InputEvent | None:
        deadline = time.monotonic() + timeout_s
        with self._condition:
            while not self._items:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._condition.wait(remaining)
            return self._items.popleft()

    def notify_all(self) -> None:
        with self._condition:
            self._condition.notify_all()

    def __len__(self) -> int:
        with self._condition:
            return len(self._items)


class LowLatencySender:
    def __init__(
        self,
        transport_factory: Callable[[], Transport],
        *,
        max_queue: int = 4096,
        retry_delay_s: float = 0.35,
        stale_event_ms: float = 800.0,
        debug: bool = False,
    ) -> None:
        self._transport_factory = transport_factory
        self._retry_delay_s = retry_delay_s
        self._stale_event_ms = stale_event_ms
        self._debug = debug
        self._buffer = EventBuffer(max_queue)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="DualLink-Sender", daemon=True)
        self.stats = SenderStats()

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._buffer.notify_all()
        self._thread.join(timeout=2)

    def send(self, event: InputEvent) -> None:
        self._buffer.push(event)
        self.stats.queued = len(self._buffer)
        self.stats.dropped = self._buffer.dropped

    def _run(self) -> None:
        while not self._stop.is_set():
            transport = self._transport_factory()
            try:
                self._log(f"connecting with {transport.name}")
                transport.connect()
                self.stats.connected = True
                self.stats.last_error = ""
                self._connected_loop(transport)
            except Exception as exc:
                self.stats.connected = False
                self.stats.last_error = str(exc)
                self.stats.reconnects += 1
                self._log(f"transport error: {exc}")
                time.sleep(self._retry_delay_s)
            finally:
                try:
                    transport.close()
                except Exception:
                    pass
                self.stats.connected = False

    def _connected_loop(self, transport: Transport) -> None:
        last_ping = 0.0
        while not self._stop.is_set():
            event = self._buffer.pop(timeout_s=0.05)
            if event is None:
                now = time.monotonic()
                if now - last_ping >= 1.0:
                    transport.ping()
                    last_ping = now
                continue
            try:
                transport.send_event(event)
                self.stats.sent += 1
                self.stats.queued = len(self._buffer)
                self.stats.dropped = self._buffer.dropped
            except Exception:
                if self._event_age_ms(event) <= self._stale_event_ms:
                    self._buffer.push_left(event)
                raise

    @staticmethod
    def _event_age_ms(event: InputEvent) -> float:
        if not event.created_ns:
            return 0.0
        return (time.perf_counter_ns() - event.created_ns) / 1_000_000

    def _log(self, message: str) -> None:
        if self._debug:
            print(f"[sender] {message}")

