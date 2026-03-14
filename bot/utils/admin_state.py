from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.states.admin_panel import AdminPanelStates


async def cancel_admin_broadcast_flow(message: Message, state: FSMContext) -> bool:
    current_state = await state.get_state()
    if current_state != AdminPanelStates.waiting_broadcast_text.state:
        return False

    data = await state.get_data()
    prompt_message_id = data.get("admin_broadcast_prompt_message_id")
    if prompt_message_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=prompt_message_id)
        except Exception:
            pass

    await state.clear()
    return True
