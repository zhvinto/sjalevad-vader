
import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from email.utils import format_datetime
from pathlib import Path

# Ungefärliga koordinater för Själevad.
LAT = 63.29
LON = 18.59

API_URL = (
    "https://opendata-download-metfcst.smhi.se/api/"
    f"category/snow1g/version/1/geotype/point/lon/{LON}/lat/{LAT}/data.json"
)

TZ = ZoneInfo("Europe/Stockholm")
OUTPUT = Path("docs/feed.xml")


def fetch_forecast():
    request = urllib.request.Request(
        API_URL,
        headers={"User-Agent": "SjalevadWeatherRSS/1.0"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def get_value(data, key):
    value = data.get(key)
    if isinstance(value, (int, float)):
        return value
    return None


def make_feed(forecast):
    now = datetime.now(timezone.utc)
    days = {}

    for item in forecast.get("timeSeries", []):
        timestamp = datetime.fromisoformat(
            item["time"].replace("Z", "+00:00")
        )
        if timestamp < now:
            continue

        local_time = timestamp.astimezone(TZ)
        day_key = local_time.date().isoformat()
        data = item.get("data", {})

        day = days.setdefault(day_key, {
            "date": local_time.date(),
            "temps": [],
            "winds": [],
            "rain_probs": [],
            "hours": 0,
        })

        temp = get_value(data, "air_temperature")
        wind = get_value(data, "wind_speed")
        rain = get_value(data, "probability_of_precipitation")

        if temp is not None:
            day["temps"].append(temp)
        if wind is not None:
            day["winds"].append(wind)
        if rain is not None:
            day["rain_probs"].append(rain)

        day["hours"] += 1

    root = ET.Element("rss", version="2.0")
    channel = ET.SubElement(root, "channel")

    ET.SubElement(channel, "title").text = "Vädret i Själevad"
    ET.SubElement(channel, "link").text = (
        "https://www.smhi.se/vader"
    )
    ET.SubElement(channel, "description").text = (
        "Dagsprognoser för Själevad baserade på SMHI:s öppna väderdata."
    )
    ET.SubElement(channel, "language").text = "sv-se"
    ET.SubElement(channel, "lastBuildDate").text = format_datetime(
        now
    )

    for day_key, day in sorted(days.items())[:10]:
        date_text = day["date"].strftime("%A %d %B %Y")
        details = []

        if day["temps"]:
            details.append(
                f"Temperatur: {min(day['temps']):.1f} till "
                f"{max(day['temps']):.1f} °C"
            )
        if day["winds"]:
            details.append(
                f"Vind: som mest {max(day['winds']):.1f} m/s"
            )
        if day["rain_probs"]:
            details.append(
                "Sannolikhet för nederbörd: som högst "
                f"{max(day['rain_probs']):.0f} %"
            )

        if not details:
            details.append("Inga vädervärden tillgängliga.")

        item = ET.SubElement(channel, "item")
        title = f"Väder i Själevad – {date_text}"
        ET.SubElement(item, "title").text = title
        ET.SubElement(item, "description").text = " | ".join(details)
        ET.SubElement(item, "guid", isPermaLink="false").text = (
            f"sjalevad-weather-{day_key}"
        )
        ET.SubElement(item, "pubDate").text = format_datetime(now)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(OUTPUT, encoding="utf-8", xml_declaration=True)


if __name__ == "__main__":
    make_feed(fetch_forecast())
    print(f"RSS-flödet har skapats: {OUTPUT}")

