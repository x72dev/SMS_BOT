# -*- coding: utf-8 -*-
"""SMS Bot v6 — 授权命令（对接 Auth Server）"""

import asyncio, logging
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from bot.handlers.common import get_cfg, get_state

log = logging.getLogger(__name__)


def register(app):
    app.add_handler(CommandHandler("activate", cmd_activate))
    app.add_handler(CommandHandler("machine_id", cmd_machine_id))


async def cmd_activate(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    /activate        — 重新联网验证
    /activate XXXX   — 用卡密激活
    """
    cfg = get_cfg(ctx)
    uid = update.effective_user.id if update.effective_user else 0
    if uid not in cfg.allowed_user_ids:
        await update.message.reply_text("⛔ 无权限"); return

    license_mgr = ctx.bot_data.get("license_mgr")
    if not license_mgr:
        await update.message.reply_text("⚠️ 授权系统未初始化"); return

    state = get_state(ctx)

    # 检查是否带卡密参数
    args = update.message.text.split(maxsplit=1)
    if len(args) > 1:
        license_key = args[1].strip()
        tip = await update.message.reply_text("⏳ 正在激活卡密...")
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

            # 如果监控未启动，启动它
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
            )
        return

    # 无卡密参数 → 重新联网验证
    tip = await update.message.reply_text("⏳ 正在验证授权...")
    ok, msg = license_mgr.full_verify()

    if ok:
        state.license_blocked = False
        vr = license_mgr.last_verify_result or {}
        extra = ""
        if vr.get("trial"):
            hours = vr.get("trial_hours_left", 24)
            extra = f"\n🔵 试用模式（剩余 {hours} 小时）"
        elif license_mgr.expires == "permanent":
            extra = "\n🟢 永久授权"
        elif license_mgr.expires:
            days = vr.get("days_left", 0)
            extra = f"\n🟢 授权至 {license_mgr.expires}（剩 {days} 天）"

        await tip.edit_text(
            f"✅ *验证成功*\n"
            f"━━━━━━━━━━━━━━━\n\n"
            f"机器码：`{license_mgr.machine_id}`"
            f"{extra}\n\n"
            f"💡 使用卡密激活：`/activate 卡密`\n"
            f"发送 /start 开始使用",
            parse_mode="Markdown",
        )
        log.info(f"验证成功: {license_mgr.machine_id} | {msg}")

        if not state.monitor_active:
            monitor_svc = ctx.bot_data.get("monitor_svc")
            if monitor_svc:
                asyncio.create_task(monitor_svc.run(ctx.application.bot))
    else:
        await tip.edit_text(
            f"❌ *验证失败*\n"
            f"━━━━━━━━━━━━━━━\n\n"
            f"机器码：`{license_mgr.machine_id}`\n"
            f"原因：{msg}\n\n"
            f"💡 如有卡密，发送：`/activate 你的卡密`\n"
            f"👉 联系 {license_mgr.admin_link} 获取授权",
            parse_mode="Markdown",
        )


async def cmd_machine_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """显示本机机器码"""
    cfg = get_cfg(ctx)
    uid = update.effective_user.id if update.effective_user else 0
    if uid not in cfg.allowed_user_ids:
        await update.message.reply_text("⛔ 无权限"); return

    license_mgr = ctx.bot_data.get("license_mgr")
    if not license_mgr:
        await update.message.reply_text("⚠️ 授权系统未初始化"); return

    await update.message.reply_text(
        f"🔑 *本机机器码*\n\n`{license_mgr.machine_id}`\n\n"
        f"💡 激活方式：`/activate 你的卡密`\n"
        f"👉 联系 {license_mgr.admin_link} 购买",
        parse_mode="Markdown",
    )


async def show_license_blocked(bot, cfg, license_mgr):
    """启动时授权未通过"""
    mid = license_mgr.machine_id
    vr = license_mgr.last_verify_result or {}
    msg = vr.get("msg", "")
    admin = license_mgr.admin_link

    if vr.get("trial"):
        text = (
            "⏰ *24小时试用已结束*\n"
            "━━━━━━━━━━━━━━━\n\n"
            f"机器码：`{mid}`\n\n"
            f"💡 激活方式：`/activate 你的卡密`\n"
            f"👉 联系 {admin} 购买授权"
        )
    elif "过期" in msg:
        text = (
            "🔴 *授权已过期*\n"
            "━━━━━━━━━━━━━━━\n\n"
            f"机器码：`{mid}`\n"
            f"{msg}\n\n"
            f"💡 续期：`/activate 新卡密`\n"
            f"👉 联系 {admin} 续费"
        )
    else:
        text = (
            "🔒 *软件未激活*\n"
            "━━━━━━━━━━━━━━━\n\n"
            f"机器码：`{mid}`\n\n"
            f"💡 激活方式：`/activate 你的卡密`\n"
            f"👉 联系 {admin} 获取授权"
        )

    await bot.send_message(
        chat_id=cfg.notify_user_id,
        text=text,
        parse_mode="Markdown",
    )
