import asyncio

_termination_wakeup_event = asyncio.Event()


def notify_termination_requested() -> None:
    _termination_wakeup_event.set()


def get_termination_wakeup_event() -> asyncio.Event:
    return _termination_wakeup_event
