
import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import format_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

MENU_URL = (
    "https://menu.matildaplatform.com/meals/week/"
    "68b52fddced7b30d63498017_sjalevadskolan"
)

TIMEZONE = ZoneInfo("Europe/Stockholm")
TODAY = datetime.now(TIMEZONE).date()
OUTPUT = Path(os.environ.get("RSS_OUTPUT", "docs/lunch.xml"))


def fetch_menu():
    request = urllib.request.Request(
        MENU_URL,
        headers={"User-Agent": "SjalevadskolanLunchRSS/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8")

    match = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    )
    if not match:
        raise RuntimeError("Hittade inte Matildas menydata i webbsidan.")

    data = json.loads(match.group(1))
    return data["props"]["pageProps"]["meals"]


def get_dishes(meals):
    dishes = []

    def walk(value):
        if isinstance(value, dict):
            date_value = value.get("date")
            if isinstance(date_value, str) and date_value[:10] == str(TODAY):
                name = value.get("name")
                if isinstance(name, str) and name.strip():
                    dishes.append(name.strip())

                courses = value.get("courses", [])
                if isinstance(courses, list):
                    for course in courses:
                        if isinstance(course, dict):
                            course_name = course.get("name")
                            if isinstance(course_name, str) and course_name.strip():
                                dishes.append(course_name.strip())
                return

            for child in value.values():
                walk(child)

        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(meals)

    # Ta bort eventuella dubbletter och behåll ordningen.
    return list(dict.fromkeys(dishes))


def create_rss(dishes):
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")

    ET.SubElement(channel, "title").text = (
        "Dagens lunch – Själevadskolan"
    )
    ET.SubElement(channel, "link").text = MENU_URL
    ET.SubElement(channel, "description").text = (
        "Dagens lunch från Själevadskolan i Matilda Menu."
    )
    ET.SubElement(channel, "language").text = "sv-se"
    ET.SubElement(channel, "lastBuildDate").text = format_datetime(
        datetime.now(TIMEZONE)
    )

    if dishes:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = (
            f"Dagens lunch {TODAY.strftime('%Y-%m-%d')}"
        )
        ET.SubElement(item, "description").text = "\n".join(dishes)
        ET.SubElement(item, "link").text = MENU_URL
        ET.SubElement(item, "guid", isPermaLink="false").text = (
            f"sjalevadskolan-lunch-{TODAY}"
        )
        ET.SubElement(item, "pubDate").text = format_datetime(
            datetime.now(TIMEZONE)
        )

    else:
        print(f"Ingen maträtt hittades för {TODAY}.")

    ET.indent(rss, space="  ")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(rss).write(
        OUTPUT, encoding="utf-8", xml_declaration=True
    )
    print(f"RSS uppdaterat: {OUTPUT}")


if __name__ == "__main__":
    create_rss(get_dishes(fetch_menu()))
