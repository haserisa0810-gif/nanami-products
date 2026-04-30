from datetime import datetime

def build_transit_block(transit_raw):
    key_periods = []
    important_dates = []
    active_aspects = []

    for item in transit_raw:
        orb = item.get("orb", 99)
        date = item.get("date")

        if orb <= 0.5:
            level = "high"
        elif orb <= 1.0:
            level = "medium"
        else:
            continue

        aspect_data = {
            "transit_body": item["transit"],
            "natal_body": item["natal"],
            "aspect": item["aspect"],
            "orb": orb,
            "date": date,
        }

        important_dates.append({
            "date": date,
            "level": level,
            "theme": item.get("theme", ""),
            "aspects": [aspect_data],
            "advice": item.get("advice", "")
        })

        active_aspects.append({
            "transit_body": item["transit"],
            "natal_body": item["natal"],
            "aspect": item["aspect"],
            "peak_date": date,
            "orb": orb,
        })

    return {
        "period": {"days": 30},
        "key_periods": important_dates[:5],
        "important_dates": important_dates[:8],
        "active_aspects": active_aspects[:12],
    }
