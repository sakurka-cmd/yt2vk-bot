"""VK keyboards for yt2vk bot."""

from vkbottle import Keyboard, KeyboardButtonColor, Text


def quality_keyboard() -> Keyboard:
    """Keyboard for quality selection."""
    kb = Keyboard(inline=True)
    kb.add(Text("480p"), color=KeyboardButtonColor.SECONDARY)
    kb.row()
    kb.add(Text("720p"), color=KeyboardButtonColor.PRIMARY)
    kb.row()
    kb.add(Text("1080p"), color=KeyboardButtonColor.SECONDARY)
    kb.row()
    kb.add(Text("4K"), color=KeyboardButtonColor.SECONDARY)
    kb.row()
    kb.add(Text("Отмена"), color=KeyboardButtonColor.NEGATIVE)
    return kb


def yes_no_keyboard() -> Keyboard:
    """Keyboard for yes/no confirmation."""
    kb = Keyboard(inline=True)
    kb.add(Text("Да"), color=KeyboardButtonColor.POSITIVE)
    kb.add(Text("Нет"), color=KeyboardButtonColor.NEGATIVE)
    return kb


def cancel_keyboard() -> Keyboard:
    """Keyboard with cancel button."""
    kb = Keyboard(inline=True)
    kb.add(Text("Отмена"), color=KeyboardButtonColor.NEGATIVE)
    return kb


def main_menu_keyboard() -> Keyboard:
    """Main bot menu."""
    kb = Keyboard(one_time=True)
    kb.add(Text("/subscribe", {"cmd": "subscribe"}))
    kb.row()
    kb.add(Text("/dl", {"cmd": "dl"}))
    kb.add(Text("/list", {"cmd": "list"}))
    kb.row()
    kb.add(Text("/albums", {"cmd": "albums"}))
    kb.add(Text("/addalbum", {"cmd": "addalbum"}))
    kb.row()
    kb.add(Text("/status", {"cmd": "status"}))
    kb.add(Text("/help", {"cmd": "help"}))
    return kb
