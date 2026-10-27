
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
        points,
        key=lambda p: abs((p[0] - now).total_seconds()),
        default=None
    )

    # Prognosen för morgondagen kl. 12 svensk tid.
    target = datetime.combine(
        tomorrow, datetime.min.time(), TZ
    ).replace(hour=12)

    tomorrow_point = min(
        (p for p in points if p[0].astimezone(TZ).date() == tomorrow),
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
        "Aktuell temperatur och morgondagens temperatur kl. 12.00 "
        "i Själevad, med vädersymboler och nederbörd från SMHI."
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
        ET.SubElement(item, "title").text = f"{emoji} {label} – {temperature}"
        ET.SubElement(item, "description").text = (
            f"🌡️ Temperatur: {temperature}. "
            f"🌧️ Nederbörd: {precipitation}. "
            f"Väder: {description}. "
            f"Prognostid: {timestamp.astimezone(TZ).strftime('%Y-%m-%d %H:%M')}. "
            "Källa: SMHI."
        )
        ET.SubElement(item, "guid", isPermaLink="false").text = (
            f"sjalevad-{label.lower().replace(' ', '-')}-{today.isoformat()}"
        )
        ET.SubElement(item, "pubDate").text = format_datetime(timestamp)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(OUTPUT, encoding="utf-8", xml_declaration=True)
