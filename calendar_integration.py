"""
Google Calendar Integration — Midwife Agent
Full CRUD: book, view, edit, cancel appointments
GC Advisory — gcadvisory.co.nz
"""

import json
import os
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/drive.readonly",
]
NZ_TZ = ZoneInfo("Pacific/Auckland")

APPOINTMENT_DURATIONS = {
    "booking appointment": 60, "36 week": 45, "38 week": 45, "40 week": 45,
    "postnatal": 30, "antenatal": 45, "home visit": 60, "transfer": 30,
    "phone consultation": 20, "follow up": 30, "new client": 60, "default": 45,
}


# ── Credentials ────────────────────────────────────────────────────────────────

def get_google_credentials() -> Optional[Credentials]:
    token_json = os.getenv("GOOGLE_TOKEN")
    if not token_json:
        return None
    try:
        d = json.loads(token_json)
        creds = Credentials(
            token=d.get("token"),
            refresh_token=d.get("refresh_token"),
            token_uri=d.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=d.get("client_id"),
            client_secret=d.get("client_secret"),
            scopes=d.get("scopes", GOOGLE_SCOPES),
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        return creds
    except Exception:
        return None


def credentials_to_dict(creds: Credentials) -> dict:
    return {
        "token": creds.token, "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri, "client_id": creds.client_id,
        "client_secret": creds.client_secret, "scopes": list(creds.scopes or []),
    }


def build_google_flow(redirect_uri: str) -> Flow:
    config = {"web": {
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [redirect_uri],
    }}
    return Flow.from_client_config(config, scopes=GOOGLE_SCOPES, redirect_uri=redirect_uri)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse_duration(appointment_type: str) -> int:
    lower = appointment_type.lower()
    for key, mins in APPOINTMENT_DURATIONS.items():
        if key in lower:
            return mins
    return APPOINTMENT_DURATIONS["default"]


def _fmt(event: dict) -> dict:
    s = event.get("start", {})
    e = event.get("end", {})
    return {
        "id": event.get("id"),
        "title": event.get("summary", "Untitled"),
        "start": s.get("dateTime", s.get("date", "")),
        "end": e.get("dateTime", e.get("date", "")),
        "description": event.get("description", ""),
        "location": event.get("location", ""),
        "status": event.get("status", "confirmed"),
        "link": event.get("htmlLink", ""),
    }


# ── Calendar CRUD ──────────────────────────────────────────────────────────────

def list_events(creds: Credentials, days_ahead: int = 14, max_results: int = 20) -> list[dict]:
    svc = build("calendar", "v3", credentials=creds)
    now = datetime.now(NZ_TZ)
    try:
        result = svc.events().list(
            calendarId="primary",
            timeMin=now.isoformat(),
            timeMax=(now + timedelta(days=days_ahead)).isoformat(),
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        return [_fmt(e) for e in result.get("items", [])]
    except HttpError as e:
        raise RuntimeError(f"Calendar error: {e}")


def create_event(
    creds: Credentials, title: str, start_dt: datetime,
    duration_minutes: Optional[int] = None,
    description: str = "", location: str = "",
) -> dict:
    svc = build("calendar", "v3", credentials=creds)
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=NZ_TZ)
    mins = duration_minutes or _parse_duration(title)
    end_dt = start_dt + timedelta(minutes=mins)
    body = {
        "summary": title, "description": description, "location": location,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": "Pacific/Auckland"},
        "end":   {"dateTime": end_dt.isoformat(),   "timeZone": "Pacific/Auckland"},
        "reminders": {"useDefault": False, "overrides": [
            {"method": "email", "minutes": 1440},
            {"method": "popup", "minutes": 60},
        ]},
    }
    try:
        return _fmt(svc.events().insert(calendarId="primary", body=body).execute())
    except HttpError as e:
        raise RuntimeError(f"Calendar error: {e}")


def update_event(
    creds: Credentials, event_id: str,
    title: Optional[str] = None, start_dt: Optional[datetime] = None,
    duration_minutes: Optional[int] = None, description: Optional[str] = None,
    location: Optional[str] = None,
) -> dict:
    svc = build("calendar", "v3", credentials=creds)
    try:
        existing = svc.events().get(calendarId="primary", eventId=event_id).execute()
    except HttpError as e:
        raise RuntimeError(f"Event not found: {e}")

    if title: existing["summary"] = title
    if description is not None: existing["description"] = description
    if location is not None: existing["location"] = location
    if start_dt:
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=NZ_TZ)
        existing["start"] = {"dateTime": start_dt.isoformat(), "timeZone": "Pacific/Auckland"}
        if duration_minutes:
            end_dt = start_dt + timedelta(minutes=duration_minutes)
        else:
            old_s = datetime.fromisoformat(existing["start"]["dateTime"])
            old_e = datetime.fromisoformat(existing["end"]["dateTime"])
            end_dt = start_dt + (old_e - old_s)
        existing["end"] = {"dateTime": end_dt.isoformat(), "timeZone": "Pacific/Auckland"}
    try:
        return _fmt(svc.events().update(calendarId="primary", eventId=event_id, body=existing).execute())
    except HttpError as e:
        raise RuntimeError(f"Calendar error: {e}")


def cancel_event(creds: Credentials, event_id: str) -> dict:
    svc = build("calendar", "v3", credentials=creds)
    try:
        svc.events().delete(calendarId="primary", eventId=event_id).execute()
        return {"deleted": True, "event_id": event_id}
    except HttpError as e:
        raise RuntimeError(f"Calendar error: {e}")


def get_availability(creds: Credentials, date: datetime, duration_minutes: int = 45) -> list[dict]:
    """Return free slots (8am-5pm NZ) on a given day, excluding existing events."""
    svc = build("calendar", "v3", credentials=creds)
    if date.tzinfo is None:
        date = date.replace(tzinfo=NZ_TZ)
    day_start = date.replace(hour=8,  minute=0, second=0, microsecond=0)
    day_end   = date.replace(hour=17, minute=0, second=0, microsecond=0)

    try:
        result = svc.events().list(
            calendarId="primary",
            timeMin=day_start.isoformat(),
            timeMax=day_end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        ).execute()
    except HttpError as e:
        raise RuntimeError(f"Calendar error: {e}")

    busy = []
    for e in result.get("items", []):
        s = e.get("start", {}).get("dateTime")
        en = e.get("end", {}).get("dateTime")
        if s and en:
            busy.append((datetime.fromisoformat(s), datetime.fromisoformat(en)))

    slots, cursor = [], day_start
    while cursor + timedelta(minutes=duration_minutes) <= day_end:
        slot_end = cursor + timedelta(minutes=duration_minutes)
        if not any(s < slot_end and cursor < e for s, e in busy):
            slots.append({"start": cursor.isoformat(), "end": slot_end.isoformat()})
        cursor += timedelta(minutes=30)
    return slots
