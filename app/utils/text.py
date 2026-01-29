def cities_text(items: list[tuple[int, str, int]]) -> str:
    # (city_id, name, points_count)
    if not items:
        return "Поки що міст нема. Додай через кнопку або /addcity."
    lines = ["🏙 <b>Міста:</b>"]
    for _, name, cnt in items:
        lines.append(f"• <b>{name}</b> — {cnt} ТТ")
    return "\n".join(lines)
def move_text(m: dict) -> str:
    from_part = "—" if not m.get("from_point_name") else f"{m.get('from_city_name','?')} / {m.get('from_point_name')}"
    to_part = "—" if not m.get("to_point_name") else f"{m.get('to_city_name','?')} / {m.get('to_point_name')}"
    note = (m.get("note") or "").strip()

    lines = [
        f"📦 <b>Переміщення #{m['id']}</b>",
        f"Статус: <b>{m.get('status')}</b>",
        f"Звідки: <b>{from_part}</b>",
        f"Куди: <b>{to_part}</b>",
    ]
    if note:
        lines.append(f"Коментар: {note}")
    lines.append(f"Створено: {m.get('created_at')}")
    return "\n".join(lines)

