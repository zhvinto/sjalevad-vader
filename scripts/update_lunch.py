
import json
import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from datetime import datetime, timedelta
from email.utils import format_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

MENU_URL = (
    "https://menu.matildaplatform.com/meals/week/"
    "68b52fddced7b30d63498017_sjalevadskolan"
)

API_URL = "https://menu.matildaplatform.com/api/menu"
TIMEZONE = ZoneInfo("Europe/Stockholm")
OUTPUT = Path(os.environ.get("RSS_OUTPUT", "docs/lunch.xml"))


def fetch_menu():
    today = datetime.now(TIMEZONE).date()

    # Hämta innevarande vecka och nästa vecka.
    start_date = today - timedelta(days=today.weekday())
    end_date = start_date + timedelta(days=13)

    # Hämta distributörens ID från den publika menyadressen.
    distributor_id = MENU_URL.rstrip("/").split("/")[-1].split("_")[0]

    params = urllib.parse.urlencode({
        "distributorId": distributor_id,
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "lang": "sv",
    })

    request = urllib.request.Request(
        f"{API_URL}?{params}",
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))

    if not isinstance(data.get("meals"), list):
        raise RuntimeError("Matilda returnerade inget giltigt menyformat.")

    return data["meals"]


def get_todays_dishes(meals):
    today = datetime.now(TIMEZONE).date()
    dishes = []

    for meal in meals:
        date_text = meal.get("date", "")

        try:
            meal_date = datetime.fromisoformat(date_text).date()
        except (ValueError, TypeError):
            continue

        if meal_date != today:
            continue

        for course in meal.get("courses", []):
            name = course.get("name")

            if isinstance(name, str) and name.strip():
                dishes.append(name.strip())

    # Ta bort dubbletter men behåll ordningen.
    return list(dict.fromkeys(dishes))


def create_rss(dishes):
    now = datetime.now(TIMEZONE)
    today = now.date()

    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")

    ET.SubElement(channel, "title").text = "Dagens lunch"
    ET.SubElement(channel, "link").text = MENU_URL
    ET.SubElement(channel, "description").text = (
        "Dagens lunchmeny."
    )
    ET.SubElement(channel, "language").text = "sv-se"
    ET.SubElement(channel, "lastBuildDate").text = format_datetime(now)

    if not dishes:
        raise RuntimeError(
            f"Inga maträtter hittades för {today}. "
            "RSS-filen lämnas oförändrad."
        )

    item = ET.SubElement(channel, "item")

    ET.SubElement(item, "title").text = (
        f"Dagens lunch {today.strftime('%Y-%m-%d')}"
    )
    ET.SubElement(item, "description").text = "\n".join(dishes)
    ET.SubElement(item, "link").text = MENU_URL
    ET.SubElement(item, "guid", isPermaLink="false").text = (
        f"dagens-lunch-{today.isoformat()}"
    )
    ET.SubElement(item, "pubDate").text = format_datetime(now)

    ET.indent(rss, space="  ")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    temp_output = OUTPUT.with_suffix(".tmp")
    ET.ElementTree(rss).write(
        temp_output,
        encoding="utf-8",
        xml_declaration=True,
    )
    temp_output.replace(OUTPUT)

    print(f"RSS uppdaterat: {OUTPUT}")
    print("Dagens maträtter:")
    for dish in dishes:
        print(f"- {dish}")


if __name__ == "__main__":
    menu = fetch_menu()
    dishes = get_todays_dishes(menu)
    create_rss(dishes)
