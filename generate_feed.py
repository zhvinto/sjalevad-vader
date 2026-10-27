
import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from email.utils import format_datetime
from pathlib import Path

# Ungefärliga koordinater för Själevad
LAT = 63.29
LON = 18.59

API_URL = (
    "https://opendata-download-metfcst.smhi.se/api/"
    f"category/snow1g/version/1/geotype/point/"
    f"lon/{LON}/lat/{LAT}/data.json"
)

TZ = ZoneInfo("Europe/Stockholm")
OUTPUT = Path("docs/feed.xml")

WEATHER = {
    1: ("☀️", "Klart"),
    2: ("🌤️", "Nästan klart"),
    3: ("🌤️", "Växlande molnighet"),
    4: ("⛅", "Halvklart"),
    5: ("☁️", "Molnigt"),
    6: ("☁️", "Mulet"),
    7: ("🌫️", "Dimma"),
    8: ("🌦️", "Lätt regnskur"),
    9: ("🌧️", "Regnskur"),
    10: ("🌧️", "Kraftig regnskur"),
    11: ("⛈️", "Åskskur"),
    12: ("🌨️", "Lätt snöblandad skur"),
    13: ("🌨️", "Snöblandad skur"),
    14: ("🌨️", "Kraftig snöblandad skur"),
    15: ("🌨️", "Lätt snöby"),
    16: ("❄️", "Snöby"),
    17: ("❄️", "Kraftig snöby"),
    18: ("🌧️", "Lätt regn"),
    19: ("🌧️", "Regn"),
    20: ("🌧️", "Kraftigt regn"),
    21: ("⛈️", "Åska"),
    22: ("🌨️", "Lätt snöblandat regn"),
    23: ("🌨️", "Snöblandat regn"),
    24: ("🌨️", "Kraftigt snöblandat regn"),
    25: ("❄️", "Lätt snöfall"),
    26: ("❄️", "Snöfall"),
    27: ("❄️", "Kraftigt snöfall"),
}


def fetch_forecast():
    request = urllib.request.Request(
        API_URL,
        headers={"User-Agent": "SjalevadWeatherRSS/1.0"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def valid_number(value):
    if isinstance(value, (int, float)) and value != 9999:
        return value
    return None


def make_feed(forecast):
    now = datetime.now(timezone.utc)
    local_now = now.astimezone(TZ)
    today = local_now.date()
    tomorrow = today + timedelta(days=1)

    points = []

    for point in forecast.get("timeSeries", []):
        timestamp = datetime.fromisoformat(
            point["time"].replace("Z", "+00:00")
        )
        points.append((timestamp, point.get("data", {})))

    points.sort(key=lambda p: p[0])

    # Närmaste prognostimme till aktuell tid.
    current_point = min(
        (p for p in points if p[0] <= now + timedelta(hours=1)),
        key=lambda p: abs((p[0] - now).total_seconds()),
        default=None
    )

    # Prognosen närmast kl. 12.00 i morgon, svensk tid.
    target = datetime.combine(
        tomorrow, datetime.min.time(), TZ
    ).replace(hour=12)

    tomorrow_point = min(
        (
            p for p in points
            if p[0].astimezone(TZ).date() == tomorrow
        ),
        key=lambda p: abs(
            (p[0].astimezone(TZ) - target).total_seconds()
        ),
        default=None
    )

    root = ET.Element("rss", version="2.0")
    channel = ET.SubElement(root, "channel")
    ET.SubElement(channel, "title").text = "Väder i Själevad"
    ET.SubElement(channel, "link").text = "https://www.smhi.se/vader"
    ET.SubElement(channel, "description").text = (
        "Temperatur just nu och i morgon kl. 12.00 samt nederbörd. "
        "Prognos från SMHI."
    )
    ET.SubElement(channel, "language").text = "sv-se"
    ET.SubElement(channel, "lastBuildDate").text = format_datetime(now)

    entries = [
        ("Just nu", current_point),
        ("Imorgon kl. 12.00", tomorrow_point),
    ]

    for label, point in entries:
        if point is None:
            continue

        timestamp, data = point
        temp = valid_number(data.get("air_temperature"))
        rain = valid_number(
            data.get("precipitation_amount_mean_deterministic")
        )
        symbol_code = valid_number(data.get("symbol_code"))

        emoji, description = WEATHER.get(
            int(symbol_code) if symbol_code is not None else 0,
            ("🌡️", "Väderprognos")
        )

        temperature = (
            f"{temp:.1f} °C" if temp is not None else "Uppgift saknas"
        )
        precipitation = (
            f"{max(0, rain):.1f} mm per prognosperiod"
            if rain is not None else "Uppgift saknas"
        )

        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = (
            f"{emoji} {label} – {temperature}"
        )
        ET.SubElement(item, "description").text = (
            f"🌡️ Temperatur: {temperature}. "
            f"🌧️ Nederbörd: {precipitation}. "
            f"Väder: {description}. "
            f"Prognostid: "
            f"{timestamp.astimezone(TZ).strftime('%Y-%m-%d %H:%M')}. "
            "Källa: SMHI."
        )
        ET.SubElement(item, "guid", isPermaLink="false").text = (
            f"sjalevad-{label.lower().replace(' ', '-')}-"
            f"{today.isoformat()}"
        )
        ET.SubElement(item, "pubDate").text = format_datetime(timestamp)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(OUTPUT, encoding="utf-8", xml_declaration=True)


if __name__ == "__main__":
    make_feed(fetch_forecast())
    print(f"RSS-flödet har skapats: {OUTPUT}")
