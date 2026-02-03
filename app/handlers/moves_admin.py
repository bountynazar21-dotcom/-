# app/handlers/moves_admin.py
from aiogram import Router, F
from aiogram.types import CallbackQuery, InputMediaPhoto
from aiogram.exceptions import TelegramBadRequest

from ..db import moves_repo as mv_repo
from ..db import auth_repo
from ..keyboards.moves import (
    admin_moves_tabs_kb,
    admin_moves_list_kb,
    admin_move_actions_kb,
)
from ..utils.text import move_text

router = Router()


async def safe_edit(cb: CallbackQuery, text: str, reply_markup=None):
    """
    Telegram не дозволяє edit_text якщо контент/клава не змінились.
    Цей хелпер гасить "message is not modified" і не валить бота.
    """
    try:
        await cb.message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await cb.answer()
            return
        raise


def _uniq(ids: list[int]) -> list[int]:
    seen = set()
    out: list[int] = []
    for x in ids:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _participants_ids(m: dict) -> list[int]:
    """
    Учасники = всі люди прив’язані до ТТ-відправника + ТТ-отримувача
    """
    from_pid = m.get("from_point_id")
    to_pid = m.get("to_point_id")

    ids: list[int] = []
    if from_pid:
        ids += [u["telegram_id"] for u in auth_repo.get_point_users(int(from_pid)) if u.get("telegram_id")]
    if to_pid:
        ids += [u["telegram_id"] for u in auth_repo.get_point_users(int(to_pid)) if u.get("telegram_id")]

    return _uniq(ids)


async def _send_album_or_single_to_me(cb: CallbackQuery, photos: list[str], caption: str) -> None:
    """
    Адміну/оператору шлемо:
    - 1 фото: send_photo(caption)
    - 2+ фото: send_media_group з caption тільки на першому
    """
    if not photos:
        await cb.bot.send_message(cb.from_user.id, caption + "\n\n⚠️ Фото відсутні.")
        return

    if len(photos) == 1:
        try:
            await cb.bot.send_photo(cb.from_user.id, photo=photos[0], caption=caption)
        except Exception:
            await cb.bot.send_message(cb.from_user.id, caption + "\n\n⚠️ Не зміг надіслати фото.")
        return

    try:
        media = [InputMediaPhoto(media=fid) for fid in photos]
        media[0].caption = caption
        media[0].parse_mode = "HTML"
        await cb.bot.send_media_group(cb.from_user.id, media=media)
    except Exception:
        # fallback: якщо з якихось причин медіагрупа не шлеться — шлемо по одному
        for fid in photos:
            try:
                await cb.bot.send_photo(cb.from_user.id, photo=fid, caption=None)
            except Exception:
                pass
        await cb.bot.send_message(cb.from_user.id, caption + "\n\n⚠️ Альбом не відправився, відправив як вийшло.")


@router.callback_query(F.data == "mva:list")
async def mva_list(cb: CallbackQuery):
    await mva_active(cb)


@router.callback_query(F.data == "mva:active")
async def mva_active(cb: CallbackQuery):
    items = mv_repo.list_moves_active(50)
    if not items:
        await safe_edit(cb, "🟢 Активних переміщень нема.", reply_markup=admin_moves_tabs_kb(True))
        await cb.answer()
        return

    await safe_edit(
        cb,
        "🟢 <b>Активні переміщення:</b>",
        reply_markup=admin_moves_list_kb(items, "mva:active"),
    )
    await cb.answer()


@router.callback_query(F.data == "mva:closed")
async def mva_closed(cb: CallbackQuery):
    items = mv_repo.list_moves_closed(30)
    if not items:
        await safe_edit(cb, "✅ Завершених переміщень нема.", reply_markup=admin_moves_tabs_kb(False))
        await cb.answer()
        return

    await safe_edit(
        cb,
        "✅ <b>Завершені переміщення (останні):</b>",
        reply_markup=admin_moves_list_kb(items, "mva:closed"),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("mva:view_"))
async def mva_view(cb: CallbackQuery):
    move_id = int(cb.data.split("_")[-1])
    m = mv_repo.get_move(move_id)
    if not m:
        await cb.answer("Не знайдено.", show_alert=True)
        return

    back_cb = "mva:active" if (m.get("status") not in ("done", "canceled")) else "mva:closed"

    await safe_edit(
        cb,
        "📦 <b>Переміщення обране</b>\n\n" + move_text(m),
        reply_markup=admin_move_actions_kb(move_id, back_cb=back_cb),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("mva:docs_"))
async def mva_docs(cb: CallbackQuery):
    move_id = int(cb.data.split("_")[-1])
    m = mv_repo.get_move(move_id)
    if not m:
        await cb.answer("Не знайдено.", show_alert=True)
        return

    # 1) Дістаємо всі версії (V1/V2/V3...)
    try:
        invoices = mv_repo.list_invoices(move_id)
    except Exception:
        invoices = []

    # Якщо історії версій нема — зробимо фейковий список з поточної
    if not invoices:
        current_v = m.get("invoice_version") or 1
        invoices = [{"version": current_v, "photo_file_id": m.get("photo_file_id")}]

    # 2) Для кожної версії пробуємо витягнути multi-photo (move_invoice_photos).
    #    Якщо нема — fallback на move_invoices.photo_file_id або moves.photo_file_id
    sent_any = False
    for inv in invoices:
        v = int(inv.get("version") or 1)

        photos: list[str] = []
        try:
            # ✅ твій новий метод з moves_repo.py
            photos = mv_repo.list_invoice_photos(move_id, v)
        except Exception:
            photos = []

        if not photos:
            fid = inv.get("photo_file_id") or m.get("photo_file_id")
            if fid:
                photos = [fid]

        cap = f"📄 <b>Накладна V{v}</b>\n🆔 ID: <b>{move_id}</b>\n\n" + move_text(m)
        await _send_album_or_single_to_me(cb, photos, cap)
        sent_any = True

    if not sent_any:
        await cb.bot.send_message(cb.from_user.id, f"🆔 ID: <b>{move_id}</b>\n\n" + move_text(m) + "\n\n⚠️ Накладних не знайдено.")

    # 3) Коригування — окремо (як було)
    if (m.get("correction_status") or "none") != "none":
        caption_corr = (
            f"⚠️ <b>Коригування</b>\n🆔 ID: <b>{move_id}</b>\n"
            f"Статус: <b>{m.get('correction_status')}</b>\n"
        )
        if (m.get("correction_note") or "").strip():
            caption_corr += f"Коментар: {m.get('correction_note')}\n"

        if m.get("correction_photo_file_id"):
            try:
                await cb.bot.send_photo(cb.from_user.id, photo=m["correction_photo_file_id"], caption=caption_corr)
            except Exception:
                await cb.bot.send_message(cb.from_user.id, caption_corr + "\n⚠️ Не зміг надіслати фото коригування.")
        else:
            await cb.bot.send_message(cb.from_user.id, caption_corr + "\n⚠️ Фото коригування відсутнє.")

    await cb.answer("📄 Накладні відправив у чат", show_alert=True)


@router.callback_query(F.data.startswith("mva:close_"))
async def mva_close(cb: CallbackQuery):
    move_id = int(cb.data.split("_")[-1])
    m = mv_repo.get_move(move_id)
    if not m:
        await cb.answer("Не знайдено.", show_alert=True)
        return

    mv_repo.set_status(move_id, "done")
    m = mv_repo.get_move(move_id) or m

    msg = (
        "✅ <b>Переміщення закрито оператором</b>\n"
        f"🆔 ID: <b>{move_id}</b>\n\n"
        f"📤 Відправник: <b>{m.get('from_point_name') or '—'}</b>\n"
        f"📥 Отримувач: <b>{m.get('to_point_name') or '—'}</b>\n"
    )

    participants = _participants_ids(m)
    delivered = 0
    for uid in participants:
        try:
            await cb.bot.send_message(uid, msg)
            delivered += 1
        except Exception:
            pass

    op_id = m.get("operator_id") or m.get("created_by")
    if op_id:
        try:
            await cb.bot.send_message(op_id, msg + f"\n📨 Повідомлень доставлено учасникам: <b>{delivered}</b>")
        except Exception:
            pass

    await cb.answer("Closed ✅", show_alert=True)
    await mva_active(cb)

