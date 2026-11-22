"""Meta (Facebook) Conversions API helpers.

Sends server-side conversion events to a Meta pixel. Access tokens and
pixel IDs are configuration, not secrets, but the access token itself
must come from the environment (see config.load_meta_settings()).
"""

API_VERSION = "v21.0"
API_BASE = f"https://graph.facebook.com/{API_VERSION}"


def build_event_payload(event_name, event_id=None, event_source_url=None,
                        user_data=None, custom_data=None, test_event_code=None):
    """Build a single Conversions API event object."""
    event = {"event_name": event_name}
    if event_id:
        event["event_id"] = event_id
    if event_source_url:
        event["event_source_url"] = event_source_url
    if user_data:
        event["user_data"] = user_data
    if custom_data:
        event["custom_data"] = custom_data
    payload = {"data": [event]}
    if test_event_code:
        payload["test_event_code"] = test_event_code
    return payload


def send_events(access_token, pixel_id, events, test_event_code=None):
    """POST events to the Meta Conversions API; returns the API response.

    events: list of event dicts as produced by build_event_payload()["data"],
    or a single event dict.
    """
    import requests

    if isinstance(events, dict):
        events = [events]
    payload = {"data": events}
    if test_event_code:
        payload["test_event_code"] = test_event_code
    response = requests.post(
        f"{API_BASE}/{pixel_id}/events",
        params={"access_token": access_token},
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def send_test_event(access_token, pixel_id, event_name="PageView",
                    event_source_url=None, test_event_code=None):
    """Send a single test event to validate pixel configuration."""
    payload = build_event_payload(
        event_name,
        event_source_url=event_source_url,
        test_event_code=test_event_code,
    )
    return send_events(
        access_token, pixel_id, payload["data"],
        test_event_code=test_event_code,
    )
