"""
plugins/__init__.py — All Telegram handlers (commands + callbacks).
This is the ONLY file that registers handlers — root __init__.py is empty.
"""
import logging
from pyrogram import filters, Client as bot
from module import (
    awadhfree, ifasfree, verbalfree, cdsfree, icsfree, pw, khan, kd, cp, neon,
    appx_master, testlivefree, utk, kaksha, pwfree, khanfree, iq,
    vision, nidhi, cpfree, allen, iqfree, ifas, pathfree,
    allenv2, abhinavfree, vajiram, qualityfree, jrffree, cw, nlogin,
    appxfree
)
import master.key as key
import msg
from config import Config
import buttom

LOGGER = logging.getLogger(__name__)


# ── Channel Membership Guard ──────────────────────────────────────────────────

async def check_channel_membership(client, user_id: int) -> bool:
    """Return True if user is a member of CHANNEL, or CHANNEL is 0 (disabled)."""
    if not Config.CHANNEL:
        return True
    try:
        member = await client.get_chat_member(Config.CHANNEL, user_id)
        return member.status not in ("left", "kicked")
    except Exception:
        return True   # on error, don't block the user


async def ensure_joined(client, user_id: int, reply_target) -> bool:
    """Reply with join prompt and return False if user hasn't joined."""
    if not await check_channel_membership(client, user_id):
        await reply_target.reply_text(
            "<b>⚠️ Please join our channel to use this bot.</b>",
            reply_markup=key.join_user()
        )
        return False
    return True


# ── Command Handlers ──────────────────────────────────────────────────────────

@bot.on_message(filters.command("start") & filters.private)
async def start_msg(client, m):
    user_id = m.from_user.id
    if not await ensure_joined(client, user_id, m):
        return
    await client.send_photo(
        m.chat.id,
        photo=await key.send_random_photo(),
        caption=msg.START.format(m.from_user.mention),
        reply_markup=key.join_user()
    )


@bot.on_message(filters.command("upgrade") & filters.private)
async def upgrade_msg(client, m):
    if not await ensure_joined(client, m.from_user.id, m):
        return
    await client.send_photo(
        m.chat.id,
        photo=await key.send_random_photo(),
        caption=msg.UPGRADE,
        reply_markup=key.contact()
    )


@bot.on_message(filters.command("app") & filters.private)
async def start_app(client, m):
    if not await ensure_joined(client, m.from_user.id, m):
        return
    await client.send_photo(
        chat_id=m.chat.id,
        photo=await key.send_random_photo(),
        caption=msg.APP,
        reply_markup=buttom.home()
    )


# ── Callback Query Handler ────────────────────────────────────────────────────

@bot.on_callback_query()
async def callback_handler(client, callback_query):
    user_id  = callback_query.from_user.id
    call_msg = callback_query.message
    data     = callback_query.data
    answer   = callback_query.answer

    if not await ensure_joined(client, user_id, call_msg):
        return

    # ── Navigation ────────────────────────────────────────────────────────────
    if data == "home":
        await call_msg.edit_reply_markup(buttom.home())

    elif data == "close":
        await call_msg.delete()

    elif data == "none":
        await answer("ℹ️ This is just a label.", show_alert=False)

    elif data.startswith("ack_page_"):
        page = int(data.split("_")[-1]) - 1
        await call_msg.edit_reply_markup(buttom.gen_app_kb(page))

    elif data.startswith("page_"):
        page = int(data.split("_")[1])
        await call_msg.edit_reply_markup(buttom.gen_app_kb(page))

    elif data.startswith("ext_page_"):
        page = int(data.split("_")[-1]) + 1
        await call_msg.edit_reply_markup(buttom.gen_app_kb(page))

    # ── APPX Free — paginated app list ────────────────────────────────────────
    elif data == "appxfree":
        await answer("Congrats! Extracting all APPX batches..", show_alert=True)
        markup = await key.gen_apps_free_kb(page=0)   # single return value
        await call_msg.edit_reply_markup(reply_markup=markup)

    elif data.startswith("appx_page_"):
        page   = int(data.split("_")[-1])
        markup = await key.gen_apps_free_kb(page=page)
        await call_msg.edit_reply_markup(reply_markup=markup)

    elif data.startswith("forward_"):
        page = int(data.split("_")[1])
        await key.appx_page(call_msg, page)   # fixed: 2-arg call

    elif data.startswith("previous_"):
        page = int(data.split("_")[1])
        await key.appx_page(call_msg, page)   # fixed: 2-arg call

    elif data.startswith("free_"):
        app_info = key.get_handle_appx_free_data(data)
        if app_info:
            await answer(f"🔄 Extracting {app_info['app_name']}...", show_alert=True)
            await appxfree.handle_appxfree_logic(
                client, call_msg, app_info["app_name"], app_info["api_url"]
            )
        else:
            await answer("❌ App not found — send /app to reload.", show_alert=True)

    # ── Free extractors (no login) ────────────────────────────────────────────
    elif data == "abhinavfree":
        await answer("Abhinav Maths — No Login Required", show_alert=True)
        await abhinavfree.abhinav_math_free(client, call_msg)

    elif data == "cpfree":
        await answer("⚠️ ClassPlus: PDF URLs not extractable, Video URLs only", show_alert=True)
        await cpfree.handle_cpfree_logic(client, call_msg)

    elif data == "pathsalafree":
        await answer("My Pathsala — No Login Required", show_alert=True)
        await pathfree.handle_pathfree_logic(client, call_msg)

    elif data == "awadhfree":
        await answer("Awadh Ojha Sir — No Login Required", show_alert=True)
        await awadhfree.awadh_ojha_free(client, call_msg)

    elif data == "pwfree":
        await answer("⚠️ Physics Wallah: PDF URLs not extractable", show_alert=True)
        await pwfree.handle_pwfree_logic(client, call_msg)

    elif data == "iqfree":
        await answer("Study IQ — No Login Required", show_alert=True)
        await iqfree.iqfree_logic(client, call_msg)

    elif data == "khanfree":
        await answer("Khan GS — No Login Required", show_alert=True)
        await khanfree.handle_khan_free_logic(client, call_msg)

    elif data == "cdsfree":
        await answer("CDS Journey — Random Login", show_alert=True)
        await cdsfree.handle_cds_logic(client, call_msg)

    elif data == "testpaperlivefree":
        await answer("Test Paper Live — No Login Required", show_alert=True)
        await testlivefree.handle_test_logic(client, call_msg)

    elif data == "icsfree":
        await answer("ICS Coaching — Random Login", show_alert=True)
        await icsfree.handle_ics_logic(client, call_msg)

    elif data == "qualityfree":
        await answer("Quality Education — No Login Required", show_alert=True)
        await qualityfree.handle_quality_logic(client, call_msg)

    elif data == "verbalfree":
        await answer("Verbal Maths — No Login Required", show_alert=True)
        await verbalfree.verbal_math(client, call_msg)

    elif data == "ifasfree":
        await answer("IFAS Academy — Random Login", show_alert=True)
        await ifasfree.ifas_logic(client, call_msg)

    elif data == "jrffree":
        await answer("JRF Adda — No Login Required", show_alert=True)
        await jrffree.jrf_adda_free(client, call_msg)

    elif data == "nlogin":
        await answer("Nursing Next — Login Required", show_alert=True)
        await nlogin.nlogin_logic(client, call_msg)

    # ── Premium extractors ────────────────────────────────────────────────────
    elif data == "careerwill":
        await answer("CareerWill", show_alert=True)
        await cw.handle_cw_logic(client, call_msg)

    elif data == "vajiram":
        await answer("Vajiram IAS", show_alert=True)
        await vajiram.vajiram_ias(client, call_msg)

    elif data == "iq":
        await answer("Study IQ", show_alert=True)
        await iq.handle_iq_logic(client, call_msg)

    elif data == "ifas":
        await answer("IFAS Online", show_alert=True)
        await ifas.ifas_logic(client, call_msg)

    elif data == "vision":
        await answer("Vision IAS", show_alert=True)
        await vision.handle_vision_logic(client, call_msg)

    elif data == "nidhi":
        await answer("Nidhi Academy", show_alert=True)
        await nidhi.handle_nidhi_logic(client, call_msg)

    elif data == "master":
        await answer("Master AppxApi", show_alert=True)
        await appx_master.handle_app_paid(client, call_msg)

    elif data == "pw":
        await answer("Physics Wallah", show_alert=True)
        await pw.handle_pw_logic(client, call_msg)

    elif data == "cp":
        await answer("ClassPlus", show_alert=True)
        await cp.handle_cp_logic(client, call_msg)

    elif data == "allen":
        await answer("Allen Institute", show_alert=True)
        await allen.handle_allen_logic(client, call_msg)

    elif data == "allenv2":
        await answer("Allen Institute V2", show_alert=True)
        await allenv2.handle_allenV2_logic(client, call_msg)

    elif data == "khan":
        await answer("Khan GS", show_alert=True)
        await khan.handle_khan_logic(client, call_msg)

    elif data == "kd":
        await answer("KD Campus Live", show_alert=True)
        await kd.handle_kd_logic(client, call_msg)

    elif data == "neon":
        await answer("Neon Classes", show_alert=True)
        await neon.handle_neon_logic(client, call_msg)

    elif data == "utk":
        await answer("Utkarsh", show_alert=True)
        await utk.handle_utk_logic(client, call_msg)

    elif data == "kaksha":
        await answer("Apni Kaksha", show_alert=True)
        await kaksha.handle_kaksha_logic(client, call_msg)

    # ── Work In Progress stubs ────────────────────────────────────────────────
    elif data in ("sunyafree", "testbookfree", "forumfree", "edukemy",
                  "adda", "dsl", "token", "tarun", "path", "rising",
                  "nursing", "ics", "sunya", "forum", "insight", "level",
                  "next", "madeeasy", "webs", "spayee", "addafree"):
        await answer("🚧 Work In Progress — Coming Soon!", show_alert=True)

    else:
        await answer("❓ Unknown action.", show_alert=True)
        LOGGER.warning(f"Unhandled callback data: '{data}' from user {user_id}")
