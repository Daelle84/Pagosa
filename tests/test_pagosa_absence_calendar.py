"""Creating an Absence from the Pagosa's calendar reaches the heater.

Until 2026-11-20 ``async_create_event`` imported its 90-day ceiling from a
module that does not exist (``pagosa_absence`` ; the constant lives in
``absence.py``), so every Absence drawn on the card or sent by
``calendar.create_event`` failed with ``ModuleNotFoundError`` before a
request left. The import sat inside the method, so loading the platform said
nothing. These pin that both paths -- an Absence starting now and one
programmed for later -- reach the hub.
"""

import asyncio
from datetime import timedelta

from custom_components.cozytouch.pagosa.calendar import PagosaAbsenceCalendar
from homeassistant.util import dt as dt_util


class _Hub:
    def __init__(self):
        self.away = []
        self.programmed = []

    def pagosa_absence_window(self):
        return None

    async def async_set_pagosa_away(self, on, **kwargs):
        self.away.append((on, kwargs))

    async def pagosa_program_absence(self, start, end):
        self.programmed.append((start, end))


def _calendar(hub):
    calendar = object.__new__(PagosaAbsenceCalendar)
    calendar._hub = hub
    calendar.async_write_ha_state = lambda: None
    return calendar


def test_an_absence_starting_now_sets_the_heater_away():
    hub = _Hub()
    now = dt_util.now()

    asyncio.run(
        _calendar(hub).async_create_event(
            dtstart=now, dtend=now + timedelta(days=5), summary="Absence"
        )
    )

    assert len(hub.away) == 1
    on, kwargs = hub.away[0]
    assert on is True
    assert kwargs["days"] == 5
    assert hub.programmed == []


def test_an_absence_starting_later_is_programmed():
    hub = _Hub()
    start = dt_util.now() + timedelta(days=1)

    asyncio.run(
        _calendar(hub).async_create_event(
            dtstart=start, dtend=start + timedelta(days=3), summary="Absence"
        )
    )

    assert hub.away == []
    assert hub.programmed == [
        (int(start.timestamp()), int((start + timedelta(days=3)).timestamp()))
    ]
