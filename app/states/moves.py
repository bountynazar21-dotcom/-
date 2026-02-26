from aiogram.fsm.state import State, StatesGroup


class MoveStates(StatesGroup):
    choosing_from_city = State()
    choosing_from_point = State()

    choosing_to_city = State()
    choosing_to_point = State()

    waiting_photos = State()   # ✅ збір багатьох фото (альбом)
    waiting_pdf = State()      # ✅ окремо: PDF накладної
    waiting_note = State()