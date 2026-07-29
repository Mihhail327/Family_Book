from fastapi.testclient import TestClient
from sqlmodel import Session
from app.models import User, Event, EventType
from tests.conftest import authorize_client

def test_static_and_meta_routes(client: TestClient):
    res_sw = client.get("/sw.js")
    assert res_sw.status_code == 200

    res_manifest = client.get("/manifest.json")
    assert res_manifest.status_code == 200

    res_debug = client.get("/debug-test")
    assert res_debug.status_code == 200
    assert res_debug.json()["status"] == "ok"

def test_calendar_routes(client: TestClient, test_user: User, session: Session):
    authorize_client(client, test_user.id) # type: ignore

    # GET календарь
    res_cal = client.get("/calendar")
    assert res_cal.status_code == 200

    # Добавление события
    res_add = client.post(
        "/calendar/events/add",
        data={"title": "День рождения", "event_date": "2026-08-15", "event_type": "birthday"},
        follow_redirects=False
    )
    assert res_add.status_code == 200

    # Запрос событий месяца
    res_events = client.get("/calendar/events?month=8&year=2026")
    assert res_events.status_code == 200
    assert 15 in res_events.json()["events"]

    # Запрос детальных событий дня
    res_day = client.get("/calendar/day-details?day=15&month=8&year=2026")
    assert res_day.status_code == 200

    # Удаление события
    event = session.query(Event).filter(Event.title == "День рождения").first()
    assert event is not None
    res_del = client.delete(f"/calendar/events/{event.id}")
    assert res_del.status_code == 200
