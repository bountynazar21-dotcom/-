from aiogram.fsm.state import State, StatesGroup


class MoveStates(StatesGroup):
    choosing_from_city = State()
    choosing_from_point = State()

    choosing_to_city = State()
    choosing_to_point = State()

    # старий режим (якщо десь ще використовується)
    waiting_photo = State()

    # новий режим: збір багатьох фото (пачка)
    waiting_photos = State()

    waiting_note = State()

