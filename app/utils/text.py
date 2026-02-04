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

    inv_v = m.get("invoice_version") or 1

    handed_by = m.get("handed_by") or "—"
    handed_at = m.get("handed_at") or "—"
    received_by = m.get("received_by") or "—"
    received_at = m.get("received_at") or "—"

    lines = [
        f"📦 <b>Переміщення #{m['id']}</b> (V{inv_v})",
        f"Статус: <b>{m.get('status')}</b>",
        f"Звідки: <b>{from_part}</b>",
        f"Куди: <b>{to_part}</b>",
        "",
        f"📤 Віддав: <b>{handed_by}</b> • {handed_at}",
        f"📥 Отримав: <b>{received_by}</b> • {received_at}",
    ]

    if note:
        lines.append(f"\nКоментар: {note}")

    lines.append(f"\nСтворено: {m.get('created_at')}")
    return "\n".join(lines)

