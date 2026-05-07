import json
import requests
from datetime import datetime, timedelta
import warnings
import urllib3
from zoneinfo import ZoneInfo

warnings.filterwarnings(
    "ignore",
    category=urllib3.exceptions.InsecureRequestWarning
)

API_URL = (
    "https://resourcereservations.usc.edu/"
    "RandR/Front.aspx?page=getResourceStatesAPI"
    "&locationId=1"
    "&resourceDomainId=0"
    "&resourceTypeId=99"
)


def round_to_five_minutes(dt):

    minutes_to_add = (5 - dt.minute % 5) % 5

    rounded = dt + timedelta(minutes=minutes_to_add)

    return rounded.replace(second=0, microsecond=0)


def format_time(dt):

    return dt.strftime("%I:%M %p")


def calculate_duration(start, end):

    duration = end - start

    if duration <= timedelta(minutes=55):
        return None

    max_duration = min(duration, timedelta(hours=2))

    total_minutes = int(max_duration.total_seconds() / 60)

    hours = total_minutes // 60
    minutes = total_minutes % 60

    if minutes == 0:
        duration_text = f"{hours} hrs"
    else:
        duration_text = f"{hours} hr {minutes} mins"

    return {
        "start": format_time(start),
        "sort_time": start.isoformat(),
        "duration": duration_text,
        "seconds": int(max_duration.total_seconds())
    }


def process_bookings(bookings):

    results = []

    # No bookings → available now
    if not bookings:

        now = round_to_five_minutes(datetime.now())

        results.append({
            "start": format_time(now),
            "sort_time": now.isoformat(),
            "duration": "2 hrs",
            "seconds": 7200
        })

        return results

    # Current time → first booking
    try:

        current_time = round_to_five_minutes(datetime.now())

        first_booking_start = datetime.fromisoformat(
            bookings[0]["start"]
        )

        initial_gap = calculate_duration(
            current_time,
            first_booking_start
        )

        if initial_gap:
            results.append(initial_gap)

    except Exception:
        pass

    # Between bookings
    for i in range(len(bookings) - 1):

        try:

            end_time = round_to_five_minutes(
                datetime.fromisoformat(bookings[i]["end"])
            ) + timedelta(minutes=5)

            next_start = round_to_five_minutes(
                datetime.fromisoformat(bookings[i + 1]["start"])
            ) - timedelta(minutes=5)

            gap = calculate_duration(
                end_time,
                next_start
            )

            if gap:
                results.append(gap)

        except Exception:
            pass

    # After last booking
    try:

        last_end = round_to_five_minutes(
            datetime.fromisoformat(bookings[-1]["end"])
        ) + timedelta(minutes=5)

        results.append({
            "start": format_time(last_end),
            "sort_time": last_end.isoformat(),
            "duration": "2 hrs",
            "seconds": 7200
        })

    except Exception:
        pass

    return results


def fetch_rooms():

    response = requests.get(
        API_URL,
        verify=False,
        timeout=30
    )

    response.raise_for_status()

    return response.json()


def generate_output(data):

    all_rooms = []

    for room in data.get("resources", []):

        if room.get("state") == "FAULTY":
            continue

        bookings = room.get("bookings", [])

        available = process_bookings(bookings)

        all_rooms.extend(available)

    # Correct datetime sorting
    all_rooms.sort(
        key=lambda x: (
            datetime.fromisoformat(x["sort_time"]),
            x["seconds"]
        )
    )

    # Remove duplicates
    unique = []
    seen = set()

    for room in all_rooms:

        key = f'{room["start"]}-{room["duration"]}'

        if key not in seen:

            seen.add(key)

            unique.append(room)

    top_rooms = unique[:5]

    # Remove internal sort field
    for room in top_rooms:
        room.pop("sort_time", None)
        room.pop("seconds", None)

    info = [
        {
            "item": "Collab Rooms",
            "reservation": "2 hrs"
        },
        {
            "item": "Marker Pouches",
            "reservation": "2 hrs"
        },
        {
            "item": "Laptops",
            "reservation": "4 hrs"
        },
        {
            "item": "Chargers",
            "reservation": "4 hrs"
        },
        {
            "item": "Other Items",
            "reservation": "Until 11:59 PM"
        }
    ]

    return {
        "view1": top_rooms,
        "info": info,
        "updated": datetime.now(ZoneInfo("America/Los_Angeles")).isoformat()
    }


def main():

    print("Fetching USC RandR data...")

    data = fetch_rooms()

    print("Generating rooms.json...")

    output = generate_output(data)

    with open("rooms.json", "w") as f:
        json.dump(output, f, indent=2)

    print("rooms.json updated successfully")


if __name__ == "__main__":
    main()