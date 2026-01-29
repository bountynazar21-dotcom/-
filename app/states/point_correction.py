from aiogram.fsm.state import State, StatesGroup

class PointCorrectionStates(StatesGroup):
    waiting_note = State()
    waiting_photo = State()
