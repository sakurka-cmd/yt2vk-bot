"""FSM states for VK bot."""

from vkbottle.dispatch import BaseStateGroup


class States(BaseStateGroup):
    """FSM states — must extend BaseStateGroup for vkbottle 4.9.0 StateRule compatibility."""
    IDLE = ""
    # Subscribe flow
    SUB_ASK_URL = "sub_ask_url"
    SUB_ASK_QUALITY = "sub_ask_quality"
    SUB_ASK_ALBUM = "sub_ask_album"
    SUB_CONFIRM = "sub_confirm"
    # One-off download flow
    DL_ASK_URL = "dl_ask_url"
    DL_ASK_QUALITY = "dl_ask_quality"
    DL_ASK_ALBUM = "dl_ask_album"
    # Unsubscribe flow
    UNSUB_SELECT = "unsub_select"
    # Quality change flow
    QUALITY_SELECT = "quality_select"
    QUALITY_VALUE = "quality_value"
    # Album creation
    ALBUM_ASK_TITLE = "album_ask_title"


class ProcessingStatus:
    """Track status of current video processing (for /status command)."""
    current_task: str = ""
    current_url: str = ""
    current_title: str = ""
    progress: str = ""
    error: str = ""

