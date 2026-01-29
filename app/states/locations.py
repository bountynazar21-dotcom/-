from aiogram.fsm.state import State, StatesGroup

class LocationsStates(StatesGroup):
    add_city = State()
    add_point_choose_city = State()
    add_point_enter_name = State()
