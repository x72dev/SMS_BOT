# -*- coding: utf-8 -*-
"""SMS Bot v6 — 授权管理（对接 Auth Server）"""

import asyncio, logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from bot.handlers.common import get_cfg, get_state
from bot.utils.keyboard import kb

log = logging.getLogger(__name__)

ST_WAIT_KEY = 100


def register(app):
    app.add_handler(CommandHandler("activate", cmd_activate))
    app.add_handler(CommandHandler("machine_id", cmd_machine_id))
    app.add_handler(CallbackQueryHandler(cb_license_panel, pattern=r"^cb_license$"))
    app.add_handler(CallbackQueryHandler(cb_license_verify, pattern=r"^cb_lic_verify$"))
    app.add_handler(CallbackQueryHandler(cb_license_activate, pattern=r"^cb_lic_activate$"))
    app.add_handler(CallbackQueryHandler(cb_license_input_cancel, pattern=r"^cb_lic_cancel$"))


def _license_kb(state):
    """授权管理面板键盘"""
    rows = [
        [("🔄 重新验证", "cb_lic_verify"), ("🔑 输入卡密", "cb_lic_activate")],
        [("🔙 主菜单", "menu_main")],
    ]
    return kb(*rows)


def _build_license_text(license_mgr, state) -> str:
    """构建授权信息面板"""
    mid = license_mgr.machine_id
    vr = license_mgr.last_verify_result or {}

    lines = [
        "🔑 *授权管理*",
        "━━━━━━━━━━━━━━━━━",
        "",
        f"🖥 机器码：`{mid}`",
    ]

    if state.license_blocked:
        lines.append("")
        lines.append("🔴 *状态：未激活*")
        msg = vr.get("msg", "")
        if msg:
            lines.append(f"原因：{msg}")
    elif vr.get("trial"):
        hours = vr.get("trial_hours_left", 0)
        lines.append("")
        lines.append(f"🔵 *状态：试用中*（剩余 {hours} 小时）")
    elif license_mgr.expires == "permanent":
        lines.append("")
        lines.append("🟢 *状态：永久授权*")
    elif license_mgr.expires:
        days = vr.get("days_left", 0)
        lines.append("")
        lines.append(f"🟢 *状态：已授权*")
        lines.append(f"📅 到期：{license_mgr.expires}（剩 {days} 天）")
    else:
        lines.append("")
        lines.append("⚪ *状态：未知*")

    # 管理员联系方式
    if license_mgr.admin_contact:
        lines.append("")
        lines.append(f"👤 管理员：{license_mgr.admin_link}")

    # 公告
    announcement = license_mgr.announcement
    if announcement:
        lines.append("")
        lines.append(f"📢 {announcement}")

    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━")
    lines.append("💡 点击「输入卡密」激活/续期")

    return "\n".join(lines)


async def cb_license_panel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """授权管理面板（从主菜单进入）"""
    q = update.callback_query
    await q.answer()

    cfg = get_cfg(ctx)
    uid = q.from_user.id if q.from_user else 0
    if uid not in cfg.allowed_user_ids:
        await q.answer("⛔ 无权限", show_alert=True)
        return

    state = get_state(ctx)
    license_mgr = ctx.bot_data.get("license_mgr")
    if not license_mgr or not license_mgr._api_url:
        await q.edit_message_text("⚠️ 授权系统未配置", reply_markup=kb([("🔙 主菜单", "menu_main")]))
        return

    await q.edit_message_text(
        _build_license_text(license_mgr, state),
        parse_mode="Markdown",
        reply_markup=_license_kb(state),
    )


async def cb_license_verify(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """重新联网验证"""
    q = update.callback_query
    await q.answer("验证中...")

    state = get_state(ctx)
    license_mgr = ctx.bot_data.get("license_mgr")

    ok, msg = license_mgr.full_verify()
    if ok:
        state.license_blocked = False
        # 验证成功后启动监控
        if not state.monitor_active:
            monitor_svc = ctx.bot_data.get("monitor_svc")
            if monitor_svc:
                asyncio.create_task(monitor_svc.run(ctx.application.bot))

    await q.edit_message_text(
        _build_license_text(license_mgr, state),
        parse_mode="Markdown",
        reply_markup=_license_kb(state),
    )


async def cb_license_activate(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """提示输入卡密"""
    q = update.callback_query
    await q.answer()
    ctx.user_data["waiting_license_key"] = True
    await q.edit_message_text(
        "🔑 *请发送卡密*\n\n"
        "格式：`SMS-XXXXX-XXXXX-XXXXX-XXXXX`\n\n"
        "直接发送卡密文本即可，或发 /activate 取消",
        parse_mode="Markdown",
        reply_markup=kb([("❌ 取消", "cb_lic_cancel")]),
    )


async def cb_license_input_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """取消输入卡密"""
    q = update.callback_query
    await q.answer()
    ctx.user_data.pop("waiting_license_key", None)

    state = get_state(ctx)
    license_mgr = ctx.bot_data.get("license_mgr")
    await q.edit_message_text(
        _build_license_text(license_mgr, state),
        parse_mode="Markdown",
        reply_markup=_license_kb(state),
    )


async def cmd_activate(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    /activate        — 重新联网验证
    /activate XXXX   — 用卡密激活
    """
    cfg = get_cfg(ctx)
    uid = update.effective_user.id if update.effective_user else 0
    if uid not in cfg.allowed_user_ids:
        await update.message.reply_text("⛔ 无权限")
        return

    license_mgr = ctx.bot_data.get("license_mgr")
    if not license_mgr:
        await update.message.reply_text("⚠️ 授权系统未初始化")
        return

    state = get_state(ctx)
    ctx.user_data.pop("waiting_license_key", None)

    args = update.message.text.split(maxsplit=1)
    if len(args) > 1:
        license_key = args[1].strip()
        await _do_activate(update.message, ctx, license_mgr, state, license_key)
        return

    # 无卡密参数 → 显示授权面板
    await update.message.reply_text(
        _build_license_text(license_mgr, state),
        parse_mode="Markdown",
        reply_markup=_license_kb(state),
    )


async def _do_activate(message, ctx, license_mgr, state, license_key):
    """执行卡密激活"""
    tip = await message.reply_text("⏳ 正在激活卡密...")
    ok, msg = license_mgr.activate(license_key)

    if ok:
        state.license_blocked = False
        vr = license_mgr.last_verify_result or {}
        days = vr.get("days_left", 0)
        await tip.edit_text(
            f"✅ *卡密激活成功*\n"
            f"━━━━━━━━━━━━━━━\n\n"
            f"🔑 卡密：`{license_key}`\n"
            f"📅 到期：{license_mgr.expires}（剩 {days} 天）\n"
            f"🖥 机器码：`{license_mgr.machine_id}`\n\n"
            f"发送 /start 开始使用",
            parse_mode="Markdown",
        )
        log.info(f"卡密激活成功: {license_key}")

        if not state.monitor_active:
            monitor_svc = ctx.bot_data.get("monitor_svc")
            if monitor_svc:
                asyncio.create_task(monitor_svc.run(ctx.application.bot))
    else:
        await tip.edit_text(
            f"❌ *激活失败*\n"
            f"━━━━━━━━━━━━━━━\n\n"
            f"🔑 卡密：`{license_key}`\n"
            f"原因：{msg}\n\n"
            f"请检查卡密是否正确",
            parse_mode="Markdown",
            reply_markup=kb([("🔙 授权管理", "cb_license")]),
        )


async def cmd_machine_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """显示本机机器码"""
    cfg = get_cfg(ctx)
    uid = update.effective_user.id if update.effective_user else 0
    if uid not in cfg.allowed_user_ids:
        await update.message.reply_text("⛔ 无权限")
        return

    license_mgr = ctx.bot_data.get("license_mgr")
    if not license_mgr:
        await update.message.reply_text("⚠️ 授权系统未初始化")
        return

    await update.message.reply_text(
        f"🔑 *本机机器码*\n\n`{license_mgr.machine_id}`\n\n"
        f"💡 激活方式：`/activate 你的卡密`\n"
        f"👉 联系 {license_mgr.admin_link} 购买",
        parse_mode="Markdown",
        reply_markup=kb([("🔑 授权管理", "cb_license")]),
    )


async def show_license_blocked(bot, cfg, license_mgr):
    """启动时授权未通过 — 发送提示"""
    mid = license_mgr.machine_id
    vr = license_mgr.last_verify_result or {}
    msg = vr.get("msg", "")
    admin = license_mgr.admin_link

    if vr.get("trial"):
        text = (
            "⏰ *24小时试用已结束*\n"
            "━━━━━━━━━━━━━━━\n\n"
            f"机器码：`{mid}`\n\n"
            f"💡 发送 /activate 或点击下方按钮激活\n"
            f"👉 联系 {admin} 购买授权"
        )
    elif "过期" in msg:
        text = (
            "🔴 *授权已过期*\n"
            "━━━━━━━━━━━━━━━\n\n"
            f"机器码：`{mid}`\n"
            f"{msg}\n\n"
            f"💡 发送 /activate 或点击下方按钮续期\n"
            f"👉 联系 {admin} 续费"
        )
    elif "封禁" in msg:
        text = (
            "🚫 *设备已被封禁*\n"
            "━━━━━━━━━━━━━━━\n\n"
            f"机器码：`{mid}`\n\n"
            f"👉 联系 {admin} 解决"
        )
    else:
        text = (
            "🔒 *软件未激活*\n"
            "━━━━━━━━━━━━━━━\n\n"
            f"机器码：`{mid}`\n\n"
            f"💡 发送 /activate 或点击下方按钮激活\n"
            f"👉 联系 {admin} 获取授权"
        )

    await bot.send_message(
        chat_id=cfg.notify_user_id,
        text=text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔑 授权管理", callback_data="cb_license")],
        ]),
    )
