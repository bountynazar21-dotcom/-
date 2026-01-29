from aiogram.fsm.state import State, StatesGroup

class ReinvoiceStates(StatesGroup):
    waiting_photo = State()
