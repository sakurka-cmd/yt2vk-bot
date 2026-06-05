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
    """Persistent main bot menu with user-friendly button labels."""
    kb = Keyboard()
    kb.add(Text("/subscribe"), color=KeyboardButtonColor.POSITIVE)
    kb.add(Text("/dl"), color=KeyboardButtonColor.PRIMARY)
    kb.row()
    kb.add(Text("/list"), color=KeyboardButtonColor.SECONDARY)
    kb.add(Text("/albums"), color=KeyboardButtonColor.SECONDARY)
    kb.row()
    kb.add(Text("/addalbum"), color=KeyboardButtonColor.SECONDARY)
    kb.add(Text("/status"), color=KeyboardButtonColor.SECONDARY)
    kb.row()
    kb.add(Text("/help"), color=KeyboardButtonColor.SECONDARY)
    return kb

