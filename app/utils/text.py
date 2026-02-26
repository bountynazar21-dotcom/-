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

    status = (m.get("status") or "—").lower()

    # --- attachments summary ---
    pdf_ok = bool(m.get("invoice_pdf_file_id"))

    # якщо десь підкладемо invoice_photos_count — покажемо точно
    photos_count = m.get("invoice_photos_count")
    if isinstance(photos_count, int):
        photos_line = f"📷 Фото накладної: <b>{photos_count}</b>"
    else:
        # fallback: хоча б "є/нема"
        photos_line = "📷 Фото накладної: <b>є</b>" if m.get("photo_file_id") else "📷 Фото накладної: <b>нема</b>"

    pdf_line = "📄 PDF накладної: <b>є</b>" if pdf_ok else "📄 PDF накладної: <b>нема</b>"

    lines = [
        f"📦 <b>Переміщення #{m['id']}</b> (V{inv_v})",
        f"Статус: <b>{status}</b>",
        f"Звідки: <b>{from_part}</b>",
        f"Куди: <b>{to_part}</b>",
        "",
        photos_line,
        pdf_line,
        "",
        f"📤 Віддав: <b>{handed_by}</b> • {handed_at}",
        f"📥 Отримав: <b>{received_by}</b> • {received_at}",
    ]

    if note:
        lines.append(f"\nКоментар: {note}")

    lines.append(f"\nСтворено: {m.get('created_at')}")
    return "\n".join(lines)