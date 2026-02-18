import logging
import json
from typing import Dict, Any, Optional

from vkbottle.bot import Bot, Message
from vkbottle import Keyboard, Text, OpenLink

from . import content

log = logging.getLogger(__name__)

# Сколько элементов показываем на одной странице клавиатуры
PAGE_SIZE = 8

# Память на уровне процесса (норм для простого бота).
USER_STATE: Dict[int, Dict[str, Any]] = {}
# state:
# {
#   "current_list": 1 or 2,
#   "page": int
# }


def _set_state(peer_id: int, *, current_list: Optional[int] = None, page: Optional[int] = None) -> None:
    st = USER_STATE.setdefault(peer_id, {"current_list": None, "page": 0})
    if current_list is not None:
        st["current_list"] = current_list
    if page is not None:
        st["page"] = page


def _get_state(peer_id: int) -> Dict[str, Any]:
    return USER_STATE.setdefault(peer_id, {"current_list": None, "page": 0})


def _main_menu_keyboard() -> Keyboard:
    kb = Keyboard(one_time=False, inline=False)
    kb.add(Text(content.MAIN_LIST1_BUTTON_TEXT, payload={"cmd": "open_list", "list": 1}))
    kb.row()
    kb.add(Text(content.MAIN_LIST2_BUTTON_TEXT, payload={"cmd": "open_list", "list": 2}))
    kb.row()
    kb.add(OpenLink(content.MAIN_URL, content.MAIN_URL_BUTTON_TEXT))
    return kb


def _list_keyboard(list_no: int, page: int) -> Keyboard:
    items = content.LIST1_ITEMS if list_no == 1 else content.LIST2_ITEMS
    total = len(items)

    start = page * PAGE_SIZE
    end = min(start + PAGE_SIZE, total)
    chunk = items[start:end]

    kb = Keyboard(one_time=False, inline=False)

    # Кнопки элементов (по одной в строке, чтобы подписи не “ломались”)
    for it in chunk:
        kb.add(Text(it["label"], payload={"cmd": "open_item", "list": list_no, "label": it["label"]}))
        kb.row()

    # Навигация страниц
    nav_added = False
    if page > 0:
        kb.add(Text("⬅ Назад", payload={"cmd": "page", "list": list_no, "page": page - 1}))
        nav_added = True

    if end < total:
        kb.add(Text("Далее ➡", payload={"cmd": "page", "list": list_no, "page": page + 1}))
        nav_added = True

    if nav_added:
        kb.row()

    # В меню
    kb.add(Text(content.BACK_TO_MENU_TEXT, payload={"cmd": "menu"}))
    return kb


def _item_keyboard(list_no: int) -> Keyboard:
    kb = Keyboard(one_time=False, inline=False)
    kb.add(Text(content.SEARCH_MORE_TEXT, payload={"cmd": "back_to_list", "list": list_no}))
    kb.row()
    kb.add(Text(content.BACK_TO_MENU_TEXT, payload={"cmd": "menu"}))
    return kb


def _list_title(list_no: int) -> str:
    return content.LIST1_TEXT if list_no == 1 else content.LIST2_TEXT


def _find_item_text(list_no: int, label: str) -> Optional[str]:
    items = content.LIST1_ITEMS if list_no == 1 else content.LIST2_ITEMS
    for it in items:
        if it["label"] == label:
            return it["text"]
    return None


async def _show_main_menu(message: Message) -> None:
    _set_state(message.peer_id, current_list=None, page=0)
    await message.answer(content.MAIN_MENU_TEXT, keyboard=_main_menu_keyboard())


async def _show_list(message: Message, list_no: int, page: int = 0) -> None:
    _set_state(message.peer_id, current_list=list_no, page=page)
    await message.answer(_list_title(list_no), keyboard=_list_keyboard(list_no, page))


async def _show_item(message: Message, list_no: int, label: str) -> None:
    text = _find_item_text(list_no, label) or "Текст не найден для этого пункта."
    _set_state(message.peer_id, current_list=list_no)  # запомним, откуда пришли
    await message.answer(text, keyboard=_item_keyboard(list_no))


def _payload_dict(message: Message) -> Optional[dict]:
    """
    В vkbottle message.payload может быть:
    - dict
    - str (JSON)
    - None
    """
    payload = getattr(message, "payload", None)
    if payload is None:
        return None
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str) and payload.strip():
        try:
            data = json.loads(payload)
            return data if isinstance(data, dict) else None
        except Exception:
            log.warning("Failed to json.loads(payload): %r", payload)
            return None
    return None


def register_handlers(bot: Bot, settings) -> None:
    @bot.on.message()
    async def router(message: Message):
        """
        Единый роутер:
        - обрабатываем payload от кнопок
        - обрабатываем текст, если человек пишет руками
        """
        text = (message.text or "").strip()
        payload = _payload_dict(message)

        # 1) Кнопки (payload)
        if payload:
            cmd = payload.get("cmd")

            if cmd == "menu":
                return await _show_main_menu(message)

            if cmd == "open_list":
                list_no = int(payload.get("list", 1))
                return await _show_list(message, list_no=list_no, page=0)

            if cmd == "page":
                list_no = int(payload.get("list", 1))
                page = int(payload.get("page", 0))
                return await _show_list(message, list_no=list_no, page=page)

            if cmd == "open_item":
                list_no = int(payload.get("list", 1))
                label = str(payload.get("label", ""))
                return await _show_item(message, list_no=list_no, label=label)

            if cmd == "back_to_list":
                list_no = int(payload.get("list", 1))
                st = _get_state(message.peer_id)
                page = int(st.get("page", 0))
                return await _show_list(message, list_no=list_no, page=page)

        # 2) Текстовые команды (fallback)
        low = text.lower()

        if low in ("/start", "start", "начать"):
            return await _show_main_menu(message)

        # Кнопки главного меню текстом
        if text == content.MAIN_LIST1_BUTTON_TEXT:
            return await _show_list(message, list_no=1, page=0)

        if text == content.MAIN_LIST2_BUTTON_TEXT:
            return await _show_list(message, list_no=2, page=0)

        if text == content.BACK_TO_MENU_TEXT:
            return await _show_main_menu(message)

        # На всякий случай — если VK прислал только текст без payload
        if "далее" in low:
            st = _get_state(message.peer_id)
            list_no = st.get("current_list")
            page = int(st.get("page", 0))
            if list_no in (1, 2):
                return await _show_list(message, list_no=list_no, page=page + 1)

        if "назад" in low:
            st = _get_state(message.peer_id)
            list_no = st.get("current_list")
            page = int(st.get("page", 0))
            if list_no in (1, 2):
                return await _show_list(message, list_no=list_no, page=max(0, page - 1))

        if text == content.SEARCH_MORE_TEXT:
            st = _get_state(message.peer_id)
            list_no = st.get("current_list")
            if list_no in (1, 2):
                return await _show_list(message, list_no=list_no, page=int(st.get("page", 0)))
            return await _show_main_menu(message)

        # Выбор элемента текстом (если payload не дошёл)
        st = _get_state(message.peer_id)
        list_no = st.get("current_list")
        if list_no in (1, 2):
            found = _find_item_text(list_no, text)
            if found is not None:
                return await _show_item(message, list_no=list_no, label=text)

        # 3) Фолбэк
        log.info("Unknown message text=%r peer=%s -> show menu", text, message.peer_id)
        return await _show_main_menu(message)
