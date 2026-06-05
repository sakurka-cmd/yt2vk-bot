"""VK bot handlers for yt2vk bot."""

import asyncio
import logging

from vkbottle import Bot
from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import CommandRule, PayloadRule, FuncRule

from bot import database as db
from bot.states import States, ProcessingStatus
from bot.downloader import (
    download_video, extract_video_id, extract_channel_id,
    get_video_info, get_channel_info, cleanup_file,
)
from bot.uploader import upload_video, create_album, list_albums
from bot.keyboards import (
    quality_keyboard, yes_no_keyboard, cancel_keyboard, main_menu_keyboard,
)
from bot.config import DEFAULT_QUALITY, QUALITIES, VK_GROUP_ID

logger = logging.getLogger(__name__)


def register_handlers(bot: Bot):
    """Register all message handlers on the bot."""

    # ── Helper: check if user is admin ───────────────────────
    from bot.config import ADMIN_IDS

    def is_admin(msg: Message) -> bool:
        if not ADMIN_IDS:
            return True  # No restriction if no admins configured
        return msg.from_id in ADMIN_IDS

    # ── /start ──────────────────────────────────────────────
    @bot.on.message(CommandRule("start", ["/!"]))
    async def cmd_start(msg: Message):
        await msg.answer(
            "Бот для сохранения видео с YouTube в альбомы сообщества VK.\n\n"
            "Команды:\n"
            "/subscribe — подписаться на YouTube-канал\n"
            "/dl <url> — скачать видео по ссылке\n"
            "/list — список подписок\n"
            "/albums — список альбомов\n"
            "/addalbum — создать альбом\n"
            "/status — статус загрузки\n"
            "/help — помощь",
            keyboard=main_menu_keyboard(),
        )

    # ── "Начать" button (VK start button) ──
    @bot.on.message(FuncRule(lambda msg: msg.text and msg.text.strip() == "Начать"))
    async def cmd_nachat(msg: Message):
        await msg.answer(
            "Бот для сохранения видео с YouTube в альбомы сообщества VK.\n\n"
            "Команды:\n"
            "/subscribe — подписаться на YouTube-канал\n"
            "/dl <url> — скачать видео по ссылке\n"
            "/list — список подписок\n"
            "/albums — список альбомов\n"
            "/addalbum — создать альбом\n"
            "/status — статус загрузки\n"
            "/help — помощь",
            keyboard=main_menu_keyboard(),
        )

    # ── /help ────────────────────────────────────────────────
    @bot.on.message(CommandRule("help", ["/!"]))
    async def cmd_help(msg: Message):
        await msg.answer(
            "Бот сохраняет видео с YouTube в альбомы сообщества VK.\n\n"
            "Подписка на канал:\n"
            "  /subscribe — бот будет проверять канал по RSS\n"
            "  и автоматически загружать новые видео\n\n"
            "Разовая загрузка:\n"
            "  /dl https://youtube.com/watch?v=XXXXX\n\n"
            "Качество: 480p, 720p (по умолчанию), 1080p, 4K\n\n"
            "Управление:\n"
            "  /list — подписки\n"
            "  /unsub — отписаться\n"
            "  /quality — изменить качество\n"
            "  /albums — список альбомов\n"
            "  /addalbum — создать альбом\n"
            "  /status — статус текущей загрузки\n\n"
            "Ограничения VK:\n"
            "  Макс. размер файла — 4 ГБ\n"
            "  Форматы: MP4, MOV, AVI, MKV, FLV, WMV",
            keyboard=cancel_keyboard(),
        )

    # ── /albums ─────────────────────────────────────────────
    @bot.on.message(CommandRule("albums", ["/!"]))
    async def cmd_albums(msg: Message):
        albums = await list_albums()
        if not albums:
            await msg.answer("В сообществе нет видеоальбомов.\nСоздайте: /addalbum")
            return

        lines = [f"Альбомы сообщества ({len(albums)}):"]
        for a in albums:
            count = a.get("count", 0)
            aid = a.get("id", "")
            title = a.get("title", "Без названия")
            lines.append(f"  [{aid}] {title} — {count} видео")

        await msg.answer("\n".join(lines))

    # ── /addalbum ──────────────────────────────────────────
    @bot.on.message(CommandRule("addalbum", ["/!"]))
    async def cmd_addalbum(msg: Message):
        if not is_admin(msg):
            await msg.answer("Доступ только для администраторов.")
            return
        await db.save_fsm_state(msg.peer_id, States.ALBUM_ASK_TITLE, {})
        await msg.answer("Введите название нового альбома:", keyboard=cancel_keyboard())

    @bot.on.message(PayloadRule({"cmd": "cancel"}))
    async def on_cancel(msg: Message):
        await db.clear_fsm_state(msg.peer_id)
        ProcessingStatus.current_task = ""
        await msg.answer("Отменено.", keyboard=main_menu_keyboard())

    # ── FSM: Album creation ─────────────────────────────────
    @bot.on.message(state=States.ALBUM_ASK_TITLE)
    async def fsm_album_title(msg: Message):
        title = msg.text.strip()
        if not title or len(title) > 255:
            await msg.answer("Название должно быть 1-255 символов. Попробуйте ещё раз:")
            return

        result = await create_album(title)
        if result:
            await db.clear_fsm_state(msg.peer_id)
            await msg.answer(
                f"Альбом создан: [{result['album_id']}] {title}",
                keyboard=main_menu_keyboard(),
            )
        else:
            await msg.answer("Ошибка создания альбома. Проверьте права группы.")

    # ── /subscribe ─────────────────────────────────────────
    @bot.on.message(CommandRule("subscribe", ["/!"]))
    async def cmd_subscribe(msg: Message):
        if not is_admin(msg):
            await msg.answer("Доступ только для администраторов.")
            return
        await db.save_fsm_state(msg.peer_id, States.SUB_ASK_URL, {})
        await msg.answer(
            "Отправьте ссылку на YouTube-канал для подписки.\n"
            "Пример: https://www.youtube.com/@SomeChannel",
            keyboard=cancel_keyboard(),
        )

    # ── FSM: Subscribe — ask URL ────────────────────────────
    @bot.on.message(state=States.SUB_ASK_URL)
    async def fsm_sub_url(msg: Message):
        url = msg.text.strip()
        channel_id = extract_channel_id(url) or url

        # Get channel info
        info = await get_channel_info(url)
        if info:
            channel_title = info.get("title", channel_id)
            await db.save_fsm_state(msg.peer_id, States.SUB_ASK_QUALITY, {
                "channel_id": channel_id,
                "channel_title": channel_title,
            })
            await msg.answer(
                f"Канал: {channel_title}\n"
                f"Выберите качество видео:",
                keyboard=quality_keyboard(),
            )
        else:
            # Still allow proceeding with raw ID
            await db.save_fsm_state(msg.peer_id, States.SUB_ASK_QUALITY, {
                "channel_id": channel_id,
                "channel_title": url,
            })
            await msg.answer(
                f"Не удалось получить информацию о канале.\n"
                f"ID: {channel_id}\n\n"
                f"Выберите качество видео:",
                keyboard=quality_keyboard(),
            )

    # ── FSM: Subscribe — ask quality ─────────────────────────
    @bot.on.message(state=States.SUB_ASK_QUALITY)
    async def fsm_sub_quality(msg: Message):
        quality_map = {"480": "480", "720": "720", "1080": "1080", "4k": "4k"}
        text = msg.text.strip().lower().replace("p", "").replace("к", "k")

        if text == "отмена":
            await db.clear_fsm_state(msg.peer_id)
            await msg.answer("Отменено.", keyboard=main_menu_keyboard())
            return

        quality = quality_map.get(text)
        if not quality:
            await msg.answer("Выберите качество из предложенных вариантов:")
            return

        state, data = await db.get_fsm_state(msg.peer_id)
        data["quality"] = quality

        # Show albums for selection
        albums = await list_albums()
        if not albums:
            await msg.answer(
                "В сообществе нет альбомов. Сначала создайте: /addalbum"
            )
            await db.clear_fsm_state(msg.peer_id)
            return

        lines = [f"Канал: {data['channel_title']}", f"Качество: {quality}p" if quality != "4k" else f"Качество: 4K", "", "Выберите альбом:"]
        for a in albums:
            lines.append(f"  [{a.get('id', '')}] {a.get('title', 'Без названия')}")

        lines.append("")
        lines.append("Или отправьте 'новый' для создания нового альбома.")

        await db.save_fsm_state(msg.peer_id, States.SUB_ASK_ALBUM, data)
        await msg.answer("\n".join(lines), keyboard=cancel_keyboard())

    # ── FSM: Subscribe — ask album ──────────────────────────
    @bot.on.message(state=States.SUB_ASK_ALBUM)
    async def fsm_sub_album(msg: Message):
        text = msg.text.strip()

        if text.lower() in ("отмена", "cancel"):
            await db.clear_fsm_state(msg.peer_id)
            await msg.answer("Отменено.", keyboard=main_menu_keyboard())
            return

        state, data = await db.get_fsm_state(msg.peer_id)
        album_id = None
        album_title = ""

        # Check if user typed "новый" or a number
        if text.lower() in ("новый", "new"):
            await db.save_fsm_state(msg.peer_id, States.ALBUM_ASK_TITLE, {"sub_data": data})
            await msg.answer("Введите название нового альбома:")
            return

        # Try to parse album ID from message
        import re
        nums = re.findall(r"\d+", text)
        if nums:
            album_id = int(nums[0])
            # Verify album exists
            albums = await list_albums()
            found = None
            for a in albums:
                if a.get("id") == album_id:
                    found = a
                    break
            if found:
                album_title = found.get("title", "")
            else:
                await msg.answer("Альбом не найден. Выберите из списка:")
                return
        else:
            # Search by title
            albums = await list_albums()
            for a in albums:
                if text.lower() in a.get("title", "").lower():
                    album_id = a.get("id")
                    album_title = a.get("title", "")
                    break
            if not album_id:
                await msg.answer("Альбом не найден. Введите ID или название:")
                return

        data["album_id"] = album_id
        data["album_title"] = album_title

        # Show confirmation
        quality_text = f"{data['quality']}p" if data['quality'] != '4k' else "4K"
        await msg.answer(
            f"Подтвердите подписку:\n\n"
            f"Канал: {data['channel_title']}\n"
            f"Альбом: [{album_id}] {album_title}\n"
            f"Качество: {quality_text}\n\n"
            f"Подписаться?",
            keyboard=yes_no_keyboard(),
        )
        await db.save_fsm_state(msg.peer_id, States.SUB_CONFIRM, data)

    # ── FSM: Subscribe — confirm ────────────────────────────
    @bot.on.message(state=States.SUB_CONFIRM)
    async def fsm_sub_confirm(msg: Message):
        text = msg.text.strip().lower()
        state, data = await db.get_fsm_state(msg.peer_id)

        if text in ("да", "yes", "д"):
            sub_id = await db.add_subscription(
                channel_id=data["channel_id"],
                channel_title=data["channel_title"],
                album_id=data["album_id"],
                quality=data["quality"],
            )
            await db.clear_fsm_state(msg.peer_id)
            await msg.answer(
                f"Подписка оформлена! (#{sub_id})\n\n"
                f"Бот будет проверять канал и загружать новые видео\n"
                f"в альбом: [{data['album_id']}] {data['album_title']}",
                keyboard=main_menu_keyboard(),
            )
        else:
            await db.clear_fsm_state(msg.peer_id)
            await msg.answer("Отменено.", keyboard=main_menu_keyboard())

    # ── /list ────────────────────────────────────────────────
    @bot.on.message(CommandRule("list", ["/!"]))
    async def cmd_list(msg: Message):
        subs = await db.list_subscriptions()
        if not subs:
            await msg.answer("Нет подписок.\nДобавьте: /subscribe")
            return

        lines = [f"Подписки ({len(subs)}):"]
        for s in subs:
            status = "ON" if s["active"] else "OFF"
            quality = f"{s['quality']}p" if s["quality"] != "4k" else "4K"
            last = s.get("last_check", "") or "never"
            lines.append(
                f"  #{s['id']} [{status}] {s['channel_title']}\n"
                f"    Альбом: {s['album_id']} | Качество: {quality} | Последняя проверка: {last}"
            )

        lines.append("\nУправление: /unsub, /quality")

        # Build inline keyboard for toggling
        from vkbottle import Keyboard, KeyboardButtonColor, Text
        from vkbottle.bot import CallbackQuery
        kb = Keyboard(inline=True)
        for s in subs:
            label = f"{'✅' if s['active'] else '❌'} #{s['id']} {s['channel_title'][:20]}"
            kb.add(Text(label, {"action": "toggle", "id": s["id"]}), color=KeyboardButtonColor.SECONDARY)
            kb.row()
        kb.add(Text("Закрыть", {"action": "close"}), color=KeyboardButtonColor.NEGATIVE)
        await msg.answer("\n".join(lines), keyboard=kb)

    # ── /unsub ──────────────────────────────────────────────
    @bot.on.message(CommandRule("unsub", ["/!"]))
    async def cmd_unsub(msg: Message):
        if not is_admin(msg):
            await msg.answer("Доступ только для администраторов.")
            return
        subs = await db.list_subscriptions()
        if not subs:
            await msg.answer("Нет подписок.")
            return

        from vkbottle import Keyboard, KeyboardButtonColor, Text
        kb = Keyboard(inline=True)
        for s in subs:
            label = f"#{s['id']} {s['channel_title'][:25]}"
            kb.add(Text(label, {"action": "unsub", "id": s["id"]}), color=KeyboardButtonColor.NEGATIVE)
            kb.row()
        kb.add(Text("Отмена", {"action": "cancel"}), color=KeyboardButtonColor.SECONDARY)
        await msg.answer("Выберите подписку для удаления:", keyboard=kb)

    # ── /quality ───────────────────────────────────────────
    @bot.on.message(CommandRule("quality", ["/!"]))
    async def cmd_quality(msg: Message):
        subs = await db.list_subscriptions()
        if not subs:
            await msg.answer("Нет подписок.")
            return

        from vkbottle import Keyboard, KeyboardButtonColor, Text
        kb = Keyboard(inline=True)
        for s in subs:
            q = f"{s['quality']}p" if s['quality'] != "4k" else "4K"
            label = f"#{s['id']} {s['channel_title'][:20]} ({q})"
            kb.add(Text(label, {"action": "sel_qual", "id": s["id"]}), color=KeyboardButtonColor.SECONDARY)
            kb.row()
        kb.add(Text("Отмена", {"action": "cancel"}), color=KeyboardButtonColor.SECONDARY)
        await db.save_fsm_state(msg.peer_id, States.QUALITY_SELECT, {})
        await msg.answer("Выберите подписку для изменения качества:", keyboard=kb)

    # ── /dl ──────────────────────────────────────────────────
    @bot.on.message(CommandRule("dl", ["/!"]))
    async def cmd_dl(msg: Message):
        if not is_admin(msg):
            await msg.answer("Доступ только для администраторов.")
            return

        # Check if URL was in the same message: /dl https://...
        url = msg.text.strip()
        parts = url.split()
        if len(parts) > 1:
            url = parts[1]
            video_id = extract_video_id(url)
            if video_id:
                await db.save_fsm_state(msg.peer_id, States.DL_ASK_QUALITY, {"url": url})
                await msg.answer(
                    f"Видео: {url}\nВыберите качество:",
                    keyboard=quality_keyboard(),
                )
                return

        await db.save_fsm_state(msg.peer_id, States.DL_ASK_URL, {})
        await msg.answer(
            "Отправьте ссылку на YouTube-видео:\n"
            "https://youtube.com/watch?v=XXXXX",
            keyboard=cancel_keyboard(),
        )

    # ── FSM: Download — ask URL ─────────────────────────────
    @bot.on.message(state=States.DL_ASK_URL)
    async def fsm_dl_url(msg: Message):
        url = msg.text.strip()
        video_id = extract_video_id(url)
        if not video_id:
            await msg.answer("Это не похоже на ссылку YouTube. Попробуйте ещё раз:")
            return

        await db.save_fsm_state(msg.peer_id, States.DL_ASK_QUALITY, {"url": url})
        await msg.answer(f"Видео: {url}\nВыберите качество:", keyboard=quality_keyboard())

    # ── FSM: Download — ask quality ─────────────────────────
    @bot.on.message(state=States.DL_ASK_QUALITY)
    async def fsm_dl_quality(msg: Message):
        quality_map = {"480": "480", "720": "720", "1080": "1080", "4k": "4k"}
        text = msg.text.strip().lower().replace("p", "").replace("к", "k")

        if text == "отмена":
            await db.clear_fsm_state(msg.peer_id)
            await msg.answer("Отменено.", keyboard=main_menu_keyboard())
            return

        quality = quality_map.get(text)
        if not quality:
            await msg.answer("Выберите качество из предложенных вариантов:")
            return

        state, data = await db.get_fsm_state(msg.peer_id)
        data["quality"] = quality

        # Show albums
        albums = await list_albums()
        if not albums:
            await msg.answer("В сообществе нет альбомов. Сначала создайте: /addalbum")
            await db.clear_fsm_state(msg.peer_id)
            return

        lines = ["Выберите альбом для загрузки:"]
        for a in albums:
            lines.append(f"  [{a.get('id', '')}] {a.get('title', 'Без названия')}")
        lines.append("\nИли отправьте 'новый' для создания нового альбома.")

        await db.save_fsm_state(msg.peer_id, States.DL_ASK_ALBUM, data)
        await msg.answer("\n".join(lines), keyboard=cancel_keyboard())

    # ── FSM: Download — ask album ───────────────────────────
    @bot.on.message(state=States.DL_ASK_ALBUM)
    async def fsm_dl_album(msg: Message):
        text = msg.text.strip()

        if text.lower() in ("отмена", "cancel"):
            await db.clear_fsm_state(msg.peer_id)
            await msg.answer("Отменено.", keyboard=main_menu_keyboard())
            return

        state, data = await db.get_fsm_state(msg.peer_id)

        if text.lower() in ("новый", "new"):
            await db.save_fsm_state(msg.peer_id, States.ALBUM_ASK_TITLE, {"dl_data": data})
            await msg.answer("Введите название нового альбома:")
            return

        # Parse album ID
        import re
        nums = re.findall(r"\d+", text)
        album_id = None
        if nums:
            album_id = int(nums[0])
        else:
            albums = await list_albums()
            for a in albums:
                if text.lower() in a.get("title", "").lower():
                    album_id = a.get("id")
                    break

        if not album_id:
            await msg.answer("Альбом не найден. Введите ID или название:")
            return

        data["album_id"] = album_id

        # Start download in background
        await db.clear_fsm_state(msg.peer_id)
        asyncio.create_task(_process_download(msg.peer_id, data["url"], album_id, data["quality"]))
        quality_text = f"{data['quality']}p" if data['quality'] != "4k" else "4K"
        await msg.answer(
            f"Загрузка началась...\n"
            f"URL: {data['url']}\n"
            f"Качество: {quality_text}\n"
            f"Альбом: {album_id}\n\n"
            f"Проверяйте статус: /status",
            keyboard=main_menu_keyboard(),
        )

    # ── /status ─────────────────────────────────────────────
    @bot.on.message(CommandRule("status", ["/!"]))
    async def cmd_status(msg: Message):
        if ProcessingStatus.current_task:
            await msg.answer(
                f"Текущая задача: {ProcessingStatus.current_task}\n"
                f"URL: {ProcessingStatus.current_url}\n"
                f"Видео: {ProcessingStatus.current_title}\n"
                f"Статус: {ProcessingStatus.progress}"
            )
        else:
            # Show last completed tasks
            d = get_db()
            cur = await d.execute(
                "SELECT * FROM oneoff_tasks ORDER BY id DESC LIMIT 3"
            )
            rows = await cur.fetchall()
            if rows:
                lines = ["Последние задачи:"]
                for r in rows:
                    lines.append(
                        f"  [{r['status']}] {r.get('title', r.get('url', ''))[:50]}"
                    )
                await msg.answer("\n".join(lines))
            else:
                await msg.answer("Нет активных и недавних задач.")


# ── Background task: download + upload ──────────────────────

async def _process_download(peer_id: int, url: str, album_id: int, quality: str):
    """Background task: download video and upload to VK."""
    from bot import database as db
    from bot.downloader import download_video, get_video_info, cleanup_file
    from bot.uploader import upload_video

    ProcessingStatus.current_task = "downloading"
    ProcessingStatus.current_url = url

    # Get video info
    info = await get_video_info(url)
    title = info.get("title", "Untitled") if info else "Untitled"
    yt_id = info.get("id", "") if info else ""

    ProcessingStatus.current_title = title

    if not info:
        logger.error("Cannot get video info for %s", url)
        ProcessingStatus.current_task = ""
        ProcessingStatus.error = "Не удалось получить информацию о видео"
        return

    # Create task record
    task_id = await db.create_task(peer_id, url, yt_id, album_id, quality, title)

    # Download
    ProcessingStatus.progress = "Скачивание..."
    file_path = await download_video(url, quality)

    if not file_path:
        ProcessingStatus.current_task = ""
        ProcessingStatus.error = "Скачивание не удалось"
        await db.update_task_status(task_id, "failed", error="Download failed")
        return

    if file_path == "TOO_LARGE":
        ProcessingStatus.current_task = ""
        ProcessingStatus.error = "Файл слишком большой"
        await db.update_task_status(task_id, "failed", error="File too large")
        return

    # Upload
    ProcessingStatus.current_task = "uploading"
    ProcessingStatus.progress = "Загрузка в VK..."

    result = await upload_video(file_path, title, album_id=album_id)
    cleanup_file(file_path)

    if result:
        ProcessingStatus.current_task = ""
        ProcessingStatus.progress = "Готово"
        await db.update_task_status(
            task_id, "completed",
            vk_video_id=result["video_id"],
            vk_owner_id=result["owner_id"],
        )
        logger.info("Task %d completed: video-%d_%d", task_id,
                     result["owner_id"], result["video_id"])
    else:
        ProcessingStatus.current_task = ""
        ProcessingStatus.error = "Загрузка в VK не удалась"
        await db.update_task_status(task_id, "failed", error="VK upload failed")
