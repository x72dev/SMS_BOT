# -*- coding: utf-8 -*-
"""SMS Bot v6 — 授权命令（已对齐 SMSBOT-Auth-Server）。"""

import asyncio
import logging

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from bot.handlers.common import get_cfg, get_state

log = logging.getLogger(__name__)


def register(app):
    app.add_handler(CommandHandler("activate", cmd_activate))
    app.add_handler(CommandHandler("machine_id", cmd_machine_id))


async def cmd_activate(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """无参重新验证，有参按卡密激活。"""
    cfg = get_cfg(ctx)
    uid = update.effective_user.id if update.effective_user else 0
    if uid not in cfg.allowed_user_ids:
        await update.message.reply_text("⛔ 无权限")
        return

    license_mgr = ctx.bot_data.get("license_mgr")
    if not license_mgr:
        await update.message.reply_text("⚠️ 授权系统未初始化")
        return

    license_key = " ".join(ctx.args).strip()
    tip_text = "⏳ 正在验证授权..." if not license_key else "⏳ 正在激活卡密..."
    tip = await update.message.reply_text(tip_text)

    if license_key:
        ok, msg = license_mgr.activate(license_key)
    else:
        ok, msg = license_mgr.full_verify()

    state = get_state(ctx)
    vr = license_mgr.last_verify_result or {}

    if ok:
        state.license_blocked = False
        extra = ""
        if vr.get("trial"):
            hours = vr.get("trial_hours_left", 24)
            extra = f"\n🔵 试用模式（剩余 {hours} 小时）"
        elif license_mgr.expires:
            days = vr.get("days_left", 0)
            extra = f"\n🟢 授权至 {license_mgr.expires}（剩 {days} 天）"

        title = "激活成功" if license_key else "验证成功"
        await tip.edit_text(
            f"✅ *{title}*\n"
            f"━━━━━━━━━━━━━━━\n\n"
            f"设备ID：`{license_mgr.machine_id}`"
            f"{extra}\n\n"
            f"{msg}\n\n"
            f"发送 /start 开始使用",
            parse_mode="Markdown",
        )
        log.info(f"授权通过: {license_mgr.machine_id} | {msg}")

        if not state.monitor_active:
            monitor_svc = ctx.bot_data.get("monitor_svc")
            if monitor_svc:
                asyncio.create_task(monitor_svc.run(ctx.application.bot))
        ensure_license_watch = ctx.bot_data.get("ensure_license_watch")
        if ensure_license_watch:
            ensure_license_watch(ctx.application)
        return

    await tip.edit_text(
        f"❌ *授权失败*\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"设备ID：`{license_mgr.machine_id}`\n"
        f"原因：{msg}\n\n"
        f"先联系管理员获取卡密\n"
        f"👉 {license_mgr.admin_link}\n\n"
        f"拿到卡密后发送：`/activate 你的卡密`",
        parse_mode="Markdown",
    )


async def cmd_machine_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """显示本机设备ID。"""
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
        f"🔑 *本机设备ID*\n\n`{license_mgr.machine_id}`\n\n"
        f"联系管理员获取卡密\n👉 {license_mgr.admin_link}\n\n"
        f"拿到卡密后发送：`/activate 你的卡密`",
        parse_mode="Markdown",
    )


async def show_license_blocked(bot, cfg, license_mgr):
    """启动时授权未通过。"""
    mid = license_mgr.machine_id
    vr = license_mgr.last_verify_result or {}
    msg = vr.get("message") or vr.get("msg") or ""
    admin = license_mgr.admin_link

    if vr.get("trial"):
        text = (
            "⏰ *24小时试用已结束*\n"
            "━━━━━━━━━━━━━━━\n\n"
            f"设备ID：`{mid}`\n\n"
            f"请联系管理员购买卡密\n"
            f"👉 {admin}\n\n"
            "拿到卡密后发送 `/activate 你的卡密`"
        )
    elif "过期" in msg or "expired" in msg.lower():
        text = (
            "🔴 *授权已过期*\n"
            "━━━━━━━━━━━━━━━\n\n"
            f"设备ID：`{mid}`\n"
            f"{msg}\n\n"
            f"请联系管理员获取续期卡密\n"
            f"👉 {admin}\n\n"
            "拿到卡密后发送 `/activate 你的卡密`"
        )
    else:
        text = (
            "🔒 *软件未激活*\n"
            "━━━━━━━━━━━━━━━\n\n"
            f"设备ID：`{mid}`\n\n"
            f"请联系管理员获取卡密\n"
            f"👉 {admin}\n\n"
            "拿到卡密后发送 `/activate 你的卡密`"
        )

    await bot.send_message(
        chat_id=cfg.notify_user_id,
        text=text,
        parse_mode="Markdown",
    )
