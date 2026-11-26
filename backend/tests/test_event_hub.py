from datetime import datetime

from app.event_hub import EventHub


def test_event_hub_publishes_to_multiple_subscribers():
    hub = EventHub()
    first = hub.subscribe()
    second = hub.subscribe()

    event = hub.publish("incidents.updated", {"incident_id": 7})

    assert first.get_nowait() == event
    assert second.get_nowait() == event
    assert event["type"] == "incidents.updated"
    assert event["data"] == {"incident_id": 7}


def test_event_hub_unsubscribe_stops_delivery():
    hub = EventHub()
    subscriber = hub.subscribe()
    hub.unsubscribe(subscriber)

    hub.publish("resources.updated", {"resource_id": 3})

    assert subscriber.empty()


def test_event_hub_keeps_newest_events_for_slow_subscriber():
    hub = EventHub(queue_size=2)
    subscriber = hub.subscribe()

    hub.publish("one")
    hub.publish("two")
    newest = hub.publish("three")

    assert subscriber.get_nowait()["type"] == "two"
    assert subscriber.get_nowait() == newest


def test_event_hub_converts_non_json_data_to_strings():
    hub = EventHub()
    subscriber = hub.subscribe()
    stamp = datetime(2026, 11, 26)

    hub.publish("incidents.updated", {"reported_at": stamp})

    assert subscriber.get_nowait()["data"]["reported_at"] == str(stamp)



def test_sse_stream_route_is_registered():
    from app.main import app

    assert "/api/events/stream" in app.openapi()["paths"]
