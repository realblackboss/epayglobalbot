import logging
import requests
import asyncio
import qrcode
from io import BytesIO
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
)
import re
from datetime import datetime, timezone, timedelta
import os
from babel.dates import format_datetime
from babel.numbers import format_currency
import json

# ======= CONFIGURAÇÕES =======
BOT_TOKEN = "7857548379:AAHK9-6TZHp03bXHhz6DeLJZgtEGAVFuvWQ"
API_KEY = "91904044-39d8-441b-8d20-8f38d6d96680"
SECRET_KEY = "1115afa69a324ef1c8d8c152fd657ad00601591719afa92e36d6863656873648"
BASE_URL = "https://api.p27pay.com.br"
LINK_PAGAMENTO = "https://portal.p27pay.com.br/pay/7a4bba9d"
SUPORTE_CONTATO = "https://suporte.p27pay.com.br"

ADMIN_MASTER_IDS = [
    1609656649, 1005515503, 5451123398, 0000000000
]
ADMINS_FILE = "admins.txt"

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

bot_start_time = datetime.now(timezone.utc)
ultimo_recebimento_time = None
protocolo_counter = 1
ultimo_extrato_id_enviado = None
ultimo_alerta_inatividade = None

# =========== DADOS DE SALDO ===========
SALDO_FILE = "saldos.json"
ACUMULADO_EXTRATO_FILE = "acumulado_extrato.json"
ADMTRABALHO_FILE = "admtrabalho.json"
PROTOCOLO_FILE = "protocolo.txt"

def load_saldos():
    if os.path.exists(SALDO_FILE):
        with open(SALDO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"saldo_adm": 0.0}

def save_saldos(data):
    with open(SALDO_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)

def load_acumulado_extrato():
    if os.path.exists(ACUMULADO_EXTRATO_FILE):
        with open(ACUMULADO_EXTRATO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"saldo_extrato": 0.0}

def save_acumulado_extrato(data):
    with open(ACUMULADO_EXTRATO_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)

def load_admtrabalho():
    if os.path.exists(ADMTRABALHO_FILE):
        with open(ADMTRABALHO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_admtrabalho(data):
    with open(ADMTRABALHO_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)

def load_protocolo():
    if os.path.exists(PROTOCOLO_FILE):
        try:
            with open(PROTOCOLO_FILE, "r") as f:
                return int(f.read().strip())
        except: pass
    return 1

def save_protocolo(valor):
    with open(PROTOCOLO_FILE, "w") as f:
        f.write(str(valor))

SALDO = load_saldos()
ACUMULADO_EXTRATO = load_acumulado_extrato()
ADMTRABALHO = load_admtrabalho()
ADMTRABALHO_PAGINAS = {}
protocolo_counter = load_protocolo()

# ======= MULTI-IDIOMA =========
TRANSLATIONS = {
    'restricted_command': {
        'pt': "🚫 Comando restrito para administradores.",
        'en': "🚫 Command restricted to administrators.",
        'zh': "🚫 此命令仅限于管理员使用。"
    },
    'invalid_format': {
        'pt': "Use o formato correto: <b>/+ valor</b> (exemplo: /+ 100)",
        'en': "Use the correct format: <b>/+ amount</b> (example: /+ 100)",
        'zh': "请使用正确的格式: <b>/+ 金额</b> (例如: /+ 100)"
    },
    'payment_request': {
        'pt': "✅ <b>Pagamento solicitado com sucesso!</b>",
        'en': "✅ <b>Payment requested successfully!</b>",
        'zh': "✅ <b>付款请求成功!</b>"
    },
    'admin_master_only': {
        'pt': "❌ Apenas ADMs Master podem usar este comando.",
        'en': "❌ Only Master ADMs can use this command.",
        'zh': "❌ 只有主管理员可以使用此命令。"
    },
    'admin_added': {
        'pt': "✅ Admin <code>{}</code> adicionado!",
        'en': "✅ Admin <code>{}</code> added!",
        'zh': "✅ 管理员 <code>{}</code> 已添加!"
    },
    'admin_removed': {
        'pt': "✅ Admin <code>{}</code> removido.",
        'en': "✅ Admin <code>{}</code> removed.",
        'zh': "✅ 管理员 <code>{}</code> 已移除。"
    },
    'admin_not_found': {
        'pt': "⚠️ Admin não encontrado.",
        'en': "⚠️ Admin not found.",
        'zh': "⚠️ 未找到管理员。"
    },
    'admin_list': {
        'pt': "🔒 <b>Admins atuais:</b>",
        'en': "🔒 <b>Current admins:</b>",
        'zh': "🔒 <b>当前管理员:</b>"
    },
    'inactivity_alert': {
        'pt': "⚠️ <b>ALERTA DE INATIVIDADE</b> ⚠️\n\nNão foram detectados novos recebimentos nos últimos 15 minutos.",
        'en': "⚠️ <b>INACTIVITY ALERT</b> ⚠️\n\nNo new payments detected in the last 15 minutes.",
        'zh': "⚠️ <b>不活跃警报</b> ⚠️\n\n15分钟内未检测到新付款。"
    },
    'contact_support': {
        'pt': "🔗 <a href='{}'>Contatar Suporte</a>",
        'en': "🔗 <a href='{}'>Contact Support</a>",
        'zh': "🔗 <a href='{}'>联系支持</a>"
    },
    'payment_link': {
        'pt': "🔗 <a href='{}'>Clique aqui para acessar o pagamento</a>",
        'en': "🔗 <a href='{}'>Click here to access payment</a>",
        'zh': "🔗 <a href='{}'>点击这里访问付款</a>"
    },
    'operating_admin': {
        'pt': "👤 <b>ADM Operante:</b>",
        'en': "👤 <b>Operating Admin:</b>",
        'zh': "👤 <b>操作管理员:</b>"
    },
    'id': {'pt': "ID", 'en': "ID", 'zh': "ID"},
    'name': {'pt': "Nome", 'en': "Name", 'zh': "名字"},
    'username': {'pt': "Username", 'en': "Username", 'zh': "用户名"},
    'date_time': {'pt': "Data/Hora", 'en': "Date/Time", 'zh': "日期/时间"},
    'protocol': {'pt': "Protocolo", 'en': "Protocol", 'zh': "协议"},
    'request_amount': {'pt': "Valor do Pedido", 'en': "Request Amount", 'zh': "请求金额"},
    'wait_confirmation': {
        'pt': "<b>Seu pedido foi registrado, aguarde a confirmação do extrato.</b>",
        'en': "<b>Your request has been registered, wait for statement confirmation.</b>",
        'zh': "<b>您的请求已注册，等待对账单确认。</b>"
    },
    'bot_started': {
        'pt': "Bot de recebimentos iniciado em",
        'en': "Payments bot started at",
        'zh': "收款机器人启动于"
    },
    'only_new_payments': {
        'pt': "A partir de agora, somente novos recebimentos serão notificados.",
        'en': "From now on, only new payments will be notified.",
        'zh': "从现在开始，只会通知新付款。"
    },
    'inactivity_warning': {
        'pt': "Alertas de inatividade serão enviados a cada 15 minutos sem recebimentos.",
        'en': "Inactivity alerts will be sent every 15 minutes without payments.",
        'zh': "每15分钟无付款将发送不活动警报。"
    },
    'receipt_statement': {
        'pt': "EXTRATO DE RECEBIMENTO",
        'en': "PAYMENT STATEMENT",
        'zh': "付款记录"
    },
    'status': {'pt': "Status", 'en': "Status", 'zh': "状态"},
    'amount': {'pt': "Valor", 'en': "Amount", 'zh': "金额"},
    'date': {'pt': "Data", 'en': "Date", 'zh': "日期"},
    'payer': {'pt': "Pagador", 'en': "Payer", 'zh': "付款人"},
    'payer_document': {'pt': "Documento Pagador", 'en': "Payer Document", 'zh': "付款人文件"},
    'type': {'pt': "Tipo", 'en': "Type", 'zh': "类型"},
    'available_commands': {'pt': "Comandos disponíveis", 'en': "Available commands", 'zh': "可用命令"},
    'add_admin': {'pt': "Adiciona admin", 'en': "Add admin", 'zh': "添加管理员"},
    'remove_admin': {'pt': "Remove admin", 'en': "Remove admin", 'zh': "移除管理员"},
    'list_admins': {'pt': "Lista todos admins", 'en': "List all admins", 'zh': "列出所有管理员"},
    'already_admin': {'pt': "já é admin", 'en': "is already admin", 'zh': "已经是管理员"},
    'already_master': {'pt': "já é um ADM Master", 'en': "is already a Master ADM", 'zh': "已经是主管理员"},
    'you_are_master': {'pt': "Você é um ADM Master!", 'en': "You are a Master ADM!", 'zh': "你是主管理员!"},
    'setlang_usage': {
        'pt': "Idiomas disponíveis: <b>pt</b> | <b>en</b> | <b>zh</b>\nUse: /setlang pt | en | zh",
        'en': "Available languages: <b>pt</b> | <b>en</b> | <b>zh</b>\nUse: /setlang pt | en | zh",
        'zh': "可用语言: <b>pt</b> | <b>en</b> | <b>zh</b>\n用法: /setlang pt | en | zh"
    },
    'setlang_success': {
        'pt': "Idioma definido para: <b>{}</b>",
        'en': "Language set to: <b>{}</b>",
        'zh': "语言设置为: <b>{}</b>"
    },
    'saldo_total': {
        'pt': "💰 Saldo acumulado dos ADM: {adm}\n💰 Saldo acumulado dos extratos: {extrato}",
        'en': "💰 ADM total balance: {adm}\n💰 Statement total balance: {extrato}",
        'zh': "💰 管理员累计余额: {adm}\n💰 提取累计余额: {extrato}"
    },
    'saldo_adm_limpo': {
        'pt': "Saldo dos ADM zerado!",
        'en': "ADM balance reset!",
        'zh': "管理员余额已清零！"
    },
    'saldo_extrato_limpo': {
        'pt': "Saldo dos extratos zerado!",
        'en': "Statements balance reset!",
        'zh': "提取余额已清零！"
    },
    'admtrabalho_header': {
        'pt': "Lista de ADM com pedidos acumulados:",
        'en': "List of ADM with accumulated requests:",
        'zh': "已累计请求的管理员列表："
    },
    'admtrabalho_paginacao': {
        'pt': "\nDigite /passar para a próxima página ou /voltar para a anterior.",
        'en': "\nType /passar for next page or /voltar for previous.",
        'zh': "\n输入 /passar 查看下一页或 /voltar 返回上一页。"
    },
    'admtrabalho_footer': {
        'pt': "Até 10 admins por página. Use /passar ou /voltar.",
        'en': "Up to 10 admins per page. Use /passar or /voltar.",
        'zh': "每页最多10个管理员，使用 /passar 或 /voltar。"
    },
    'admtrabalho_limpo': {
        'pt': "✅ Contagem de pedidos dos ADM foi zerada.",
        'en': "✅ ADM request counts have been reset.",
        'zh': "✅ 管理员请求计数已清零。"
    },
    'no_more_pages': {
        'pt': "Não há mais páginas.",
        'en': "No more pages.",
        'zh': "没有更多页面。"
    },
    'first_page': {
        'pt': "Você já está na primeira página.",
        'en': "You are already on the first page.",
        'zh': "你已经在第一页了。"
    },
    'about': {
        'pt': (
            "<b>🤖 Sobre o Bot de Recebimentos e ADM</b>\n"
            "O bot organiza, registra e gerencia pedidos, pagamentos e administradores de forma segura e prática.\n\n"
            "<b>🔹 Função Geral:</b>\n"
            "• Registrar pedidos de pagamento via comando (/+ valor)\n"
            "• Somar saldos de administradores e extratos\n"
            "• Gerenciar e listar administradores\n"
            "• Paginador para relatórios de ADMs\n"
            "• Multilíngue automático\n"
            "• Suporte fácil e rápido\n\n"
            "<b>📋 Comandos de Pedido e Saldos</b>\n"
            "• <b>/+ valor</b> — Registrar um novo pedido de pagamento para o ADM.\n"
            "• <b>/total</b> — Exibe o saldo acumulado dos ADMs e dos extratos (entradas Pix/API).\n"
            "• <b>/limparsaldo</b> — Zera o saldo acumulado dos ADMs (pedidos feitos).\n"
            "• <b>/limparacumulado</b> — Zera o saldo acumulado dos extratos recebidos.\n\n"
            "<b>👑 Comandos Administrativos</b>\n"
            "• <b>/adm</b> — Adiciona, remove ou lista administradores (somente ADM Master).\n"
            "• <b>/masters</b> — Lista IDs dos ADMs Master.\n"
            "• <b>/setlang [idioma]</b> — Troca o idioma do bot.\n\n"
            "<b>📊 Relatório e Organização dos ADM</b>\n"
            "• <b>/admtrabalho</b> — Lista ADMs com a quantidade de pedidos realizados (até 10 por página).\n"
            "• <b>/passar</b> — Avança para a próxima página do relatório de ADMs.\n"
            "• <b>/voltar</b> — Volta para a página anterior do relatório de ADMs.\n"
            "• <b>/limparadmtrabalho</b> — Zera a contagem de pedidos de todos os ADMs.\n\n"
            "<b>🆘 Ajuda & Suporte</b>\n"
            "• <b>/about</b> — Exibe esta mensagem com as principais informações e comandos.\n"
            f"• Dúvidas? <a href='{SUPORTE_CONTATO}'>Clique aqui para suporte</a>\n"
            "<i>Obs: Comandos administrativos funcionam apenas para usuários autorizados.</i>"
        ),
        'en': (
            "<b>🤖 About the Payments & ADM Bot</b>\n"
            "This bot organizes, registers, and manages requests, payments, and admins in a safe and practical way.\n\n"
            "<b>🔹 General Features:</b>\n"
            "• Register payment requests using /+ amount\n"
            "• Sum admin balances and payment statement balances\n"
            "• Manage and list administrators\n"
            "• Pagination for admin reports\n"
            "• Automatic multi-language support\n"
            "• Quick and easy support\n\n"
            "<b>📋 Payment & Balance Commands</b>\n"
            "• <b>/+ amount</b> — Register a new payment request for the admin.\n"
            "• <b>/total</b> — Shows the accumulated balances of admins and payment statements.\n"
            "• <b>/limparsaldo</b> — Resets the accumulated admin balance (requests made).\n"
            "• <b>/limparacumulado</b> — Resets the accumulated statement balance received.\n\n"
            "<b>👑 Administrative Commands</b>\n"
            "• <b>/adm</b> — Add, remove, or list administrators (Master ADM only).\n"
            "• <b>/masters</b> — List Master ADM IDs.\n"
            "• <b>/setlang [lang]</b> — Change the bot's language.\n\n"
            "<b>📊 ADM Organization & Report</b>\n"
            "• <b>/admtrabalho</b> — List ADM with the number of requests made (up to 10 per page).\n"
            "• <b>/passar</b> — Next page in the ADM report.\n"
            "• <b>/voltar</b> — Previous page in the ADM report.\n"
            "• <b>/limparadmtrabalho</b> — Reset the ADM requests count.\n\n"
            "<b>🆘 Help & Support</b>\n"
            "• <b>/about</b> — Shows this message with main info and commands.\n"
            f"• Questions? <a href='{SUPORTE_CONTATO}'>Click here for support</a>\n"
            "<i>Note: Administrative commands work only for authorized users.</i>"
        ),
        'zh': (
            "<b>🤖 关于收款与管理员（ADM）机器人</b>\n"
            "该机器人可以安全高效地组织、登记和管理收款请求、付款和管理员。\n\n"
            "<b>🔹 主要功能：</b>\n"
            "• 通过命令（/+ 金额）登记付款请求\n"
            "• 汇总管理员余额和收款明细余额\n"
            "• 管理和列出管理员\n"
            "• 管理员报告分页\n"
            "• 自动多语言支持\n"
            "• 快速简便的支持\n\n"
            "<b>📋 付款与余额命令</b>\n"
            "• <b>/+ 金额</b> — 为管理员登记新的付款请求。\n"
            "• <b>/total</b> — 显示管理员和收款明细的累计余额。\n"
            "• <b>/limparsaldo</b> — 重置管理员累计余额（已登记的请求）。\n"
            "• <b>/limparacumulado</b> — 重置收到的累计收款明细余额。\n\n"
            "<b>👑 管理命令</b>\n"
            "• <b>/adm</b> — 添加、移除或列出管理员（仅限主管理员）。\n"
            "• <b>/masters</b> — 列出主管理员ID。\n"
            "• <b>/setlang [语言]</b> — 更改机器人的语言。\n\n"
            "<b>📊 管理员报告与组织</b>\n"
            "• <b>/admtrabalho</b> — 列出各管理员的请求数量（每页最多10个）。\n"
            "• <b>/passar</b> — 查看管理员报告的下一页。\n"
            "• <b>/voltar</b> — 返回管理员报告的上一页。\n"
            "• <b>/limparadmtrabalho</b> — 重置所有管理员的请求计数。\n\n"
            "<b>🆘 帮助与支持</b>\n"
            "• <b>/about</b> — 显示本消息及主要信息和命令。\n"
            f"• 有疑问？<a href='{SUPORTE_CONTATO}'>点击此处寻求支持</a>\n"
            "<i>注意：管理命令仅对授权用户开放。</i>"
        ),
    }
}

USER_LANGS_FILE = "user_langs.json"
SUPPORTED_LANGS = ['pt', 'en', 'zh']
SUPPORTED_LANGS_EXT = [
    'pt', 'en', 'zh', 'es', 'fr', 'de', 'it', 'ru', 'ar', 'ja', 'ko',
    'hi', 'tr', 'nl', 'pl', 'sv', 'uk', 'vi', 'th', 'he', 'id', 'el', 'fa'
]

def load_user_langs():
    if not os.path.exists(USER_LANGS_FILE):
        return {}
    with open(USER_LANGS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_user_langs(langs):
    with open(USER_LANGS_FILE, "w", encoding="utf-8") as f:
        json.dump(langs, f, ensure_ascii=False, indent=2)

USER_LANGS = load_user_langs()

def translate_google(text, target_lang):
    if target_lang in SUPPORTED_LANGS:
        return text
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={target_lang}&dt=t&q={requests.utils.quote(text)}"
        resp = requests.get(url, timeout=6)
        data = resp.json()
        if data and isinstance(data, list) and data[0] and isinstance(data[0], list) and data[0][0]:
            return data[0][0][0]
        return text
    except Exception as e:
        logger.error(f"Erro ao traduzir via Google: {str(e)}")
        return text

def get_translation(key, lang, format_args=None):
    base = TRANSLATIONS.get(key, {})
    translation = base.get(lang) or base.get('en') or base.get('pt') or next(iter(base.values()), f"[MISSING: {key}]")
    if lang not in SUPPORTED_LANGS:
        translation = translate_google(base.get('en', translation), lang)
    if format_args:
        try:
            if isinstance(format_args, (list, tuple)):
                return translation.format(*format_args)
            return translation.format(format_args)
        except Exception as e:
            logger.error(f"Erro ao formatar tradução '{key}' ({lang}): {e}")
            return translation
    return translation

async def get_user_language(user):
    user_id = str(user.id)
    if user_id in USER_LANGS:
        return USER_LANGS[user_id]
    try:
        lang = getattr(user, "language_code", None) or getattr(user, "lang", None)
        if lang:
            lang_code = lang.split('-')[0].lower()
            return lang_code if lang_code in SUPPORTED_LANGS_EXT else lang_code
        if hasattr(user, "get_chat"):
            chat = await user.get_chat()
            lang = getattr(chat, "language_code", None)
            if lang:
                lang_code = lang.split('-')[0].lower()
                return lang_code if lang_code in SUPPORTED_LANGS_EXT else lang_code
    except Exception as e:
        logger.error(f"Erro ao detectar idioma: {str(e)}")
    return 'en'

async def setlang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user = update.effective_user
    lang = await get_user_language(user)
    if len(context.args) != 1 or context.args[0].lower() not in SUPPORTED_LANGS_EXT:
        await update.message.reply_text(
            get_translation('setlang_usage', lang),
            parse_mode=ParseMode.HTML
        )
        return
    new_lang = context.args[0].lower()
    USER_LANGS[user_id] = new_lang
    save_user_langs(USER_LANGS)
    await update.message.reply_text(
        get_translation('setlang_success', new_lang, new_lang),
        parse_mode=ParseMode.HTML
    )

def load_admins():
    if not os.path.exists(ADMINS_FILE):
        with open(ADMINS_FILE, "w") as f:
            for master_id in ADMIN_MASTER_IDS:
                f.write(f"{master_id}\n")
        return set(ADMIN_MASTER_IDS)
    with open(ADMINS_FILE, "r") as f:
        admin_ids = {int(line.strip()) for line in f if line.strip().isdigit()}
    for master_id in ADMIN_MASTER_IDS:
        admin_ids.add(master_id)
    return admin_ids

def save_admins(admin_ids):
    with open(ADMINS_FILE, "w") as f:
        for adm_id in sorted(admin_ids):
            f.write(f"{adm_id}\n")
ADMIN_IDS = load_admins()

def formatar_extrato_recebimento(tx, lang='pt'):
    try:
        amount = format_currency(float(tx.get('amount', 0)), tx.get('currency', 'BRL'), locale=lang)
        date = format_datetime(
            datetime.strptime(tx.get('created_at', ''), "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc),
            locale=lang
        ) if tx.get('created_at') else '-'
    except:
        amount = tx.get('amount', '-')
        date = tx.get('created_at', '-')
    return (
        f"🧾 <b>{get_translation('receipt_statement', lang)}</b>\n\n"
        f"<b>{get_translation('id', lang)}:</b> <code>{tx.get('transaction_id', '-')}</code>\n"
        f"<b>{get_translation('status', lang)}:</b> <code>{tx.get('status', '-')}</code>\n"
        f"<b>{get_translation('amount', lang)}:</b> <code>{amount}</code>\n"
        f"<b>{get_translation('date', lang)}:</b> <code>{date}</code>\n"
        f"<b>{get_translation('payer', lang)}:</b> <code>{tx.get('debtor_name', '-')}</code>\n"
        f"<b>{get_translation('payer_document', lang)}:</b> <code>{tx.get('debtor_document', '-')}</code>\n"
        f"<b>End-to-End ID:</b> <code>{tx.get('end_to_end_id', '-')}</code>\n"
        f"<b>{get_translation('type', lang)}:</b> <code>{tx.get('type', '-')}</code>"
    )

def buscar_recebimentos():
    global ultimo_recebimento_time
    headers = {
        "x-api-key": API_KEY,
        "x-secret-key": SECRET_KEY,
        "Content-Type": "application/json"
    }
    try:
        resp = requests.get(f"{BASE_URL}/api/banking/statement", headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        recebimentos = []
        for tx in data.get("transactions", []):
            tx_type = (tx.get("type") or "").upper()
            tx_status = (tx.get("status") or "").upper()
            tx_date_str = tx.get("created_at")
            try:
                tx_date = datetime.strptime(tx_date_str, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
            except:
                continue
            if (tx_type == "DEPOSIT" and 
                tx_status in ["PAID", "COMPLETED"] and
                tx_date > bot_start_time):
                recebimentos.append(tx)
                ultimo_recebimento_time = datetime.now(timezone.utc)
        return recebimentos
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro na requisição: {str(e)}")
    except Exception as e:
        logger.error(f"Erro ao processar extratos: {str(e)}")
    return []

async def enviar_alerta_inatividade(app, lang='pt'):
    for admin_id in ADMIN_IDS:
        try:
            user_lang = await get_user_language(await app.bot.get_chat(admin_id))
            await app.bot.send_message(
                chat_id=admin_id,
                text=(
                    f"{get_translation('inactivity_alert', user_lang)}\n"
                    f"{get_translation('contact_support', user_lang).format(SUPORTE_CONTATO)}"
                ),
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Erro ao enviar alerta para admin {admin_id}: {str(e)}")

async def monitorar_recebimentos(app):
    global ultimo_recebimento_time, ultimo_extrato_id_enviado, ADMIN_IDS, ultimo_alerta_inatividade, ACUMULADO_EXTRATO
    if ultimo_recebimento_time is None:
        ultimo_recebimento_time = datetime.now(timezone.utc)
    if ultimo_alerta_inatividade is None:
        ultimo_alerta_inatividade = datetime.now(timezone.utc) - timedelta(minutes=15)
    while True:
        try:
            ADMIN_IDS = load_admins()
            recebimentos = buscar_recebimentos()
            if recebimentos:
                logger.info(f"Encontrados {len(recebimentos)} novos recebimentos")
                recebimentos.sort(key=lambda x: x.get("created_at"))
                novos = []
                for tx in recebimentos:
                    tid = str(tx.get("transaction_id") or tx.get("id") or "")
                    if not tid:
                        continue
                    if ultimo_extrato_id_enviado is None or tid > ultimo_extrato_id_enviado:
                        novos.append(tx)
                if novos:
                    ultimo_extrato_id_enviado = str(novos[-1].get("transaction_id") or novos[-1].get("id") or "")
                    for tx in novos:
                        try:
                            valor_extrato = float(tx.get('amount', 0))
                            ACUMULADO_EXTRATO["saldo_extrato"] += valor_extrato
                            save_acumulado_extrato(ACUMULADO_EXTRATO)
                        except Exception as e:
                            logger.error(f"Erro ao acumular extrato: {str(e)}")
                    for master_id in ADMIN_MASTER_IDS:
                        try:
                            user_lang = await get_user_language(await app.bot.get_chat(master_id))
                            for tx in novos:
                                msg = formatar_extrato_recebimento(tx, user_lang)
                                await app.bot.send_message(
                                    chat_id=master_id,
                                    text=msg,
                                    parse_mode=ParseMode.HTML
                                )
                        except Exception as e:
                            logger.error(f"Erro ao enviar para ADM Master {master_id}: {str(e)}")
                ultimo_recebimento_time = datetime.now(timezone.utc)
            tempo_sem_recebimentos = datetime.now(timezone.utc) - ultimo_recebimento_time
            tempo_desde_alerta = datetime.now(timezone.utc) - ultimo_alerta_inatividade
            if tempo_sem_recebimentos > timedelta(minutes=15) and tempo_desde_alerta > timedelta(minutes=15):
                await enviar_alerta_inatividade(app, 'pt')
                ultimo_alerta_inatividade = datetime.now(timezone.utc)
            await asyncio.sleep(30)
        except Exception as e:
            logger.error(f"Erro no monitoramento: {str(e)}")
            await asyncio.sleep(60)

def gerar_pix_p27pay(valor_centavos: int):
    url = f"{BASE_URL}/api/banking/quote-transaction"
    headers = {
        "x-api-key": API_KEY,
        "x-secret-key": SECRET_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "value": valor_centavos,
        "simulation": False,
        "receiverAddress": "0xaabaafcd77d1828689bf2f196bb4fe6c9e5e2bb7"
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=15)
    logger.info(f"Status: {resp.status_code} | Resp: {resp.text[:500]}")
    if resp.status_code not in (200, 201):
        try:
            erro = resp.json().get("error", "")
        except Exception:
            erro = ""
        raise Exception(f"Erro {resp.status_code} - {erro or resp.text[:300]}")
    data = resp.json()
    qr_copiaecola = data.get("qrCode") or data.get("qr_code") or ""
    if not qr_copiaecola:
        raise Exception("Resposta inesperada: campo qrCode não encontrado.")
    return qr_copiaecola

async def pedido_pagamento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global protocolo_counter, ADMIN_IDS, SALDO, ADMTRABALHO
    ADMIN_IDS = load_admins()
    user = update.effective_user
    lang = await get_user_language(user)
    if user.id not in ADMIN_IDS:
        await update.message.reply_text(get_translation('restricted_command', lang))
        return
    texto = update.message.text.strip()
    match = re.match(r"^(?:\/?\+)\s*(\d+[\d.,]*)", texto)
    if not match:
        await update.message.reply_text(
            get_translation('invalid_format', lang),
            parse_mode=ParseMode.HTML
        )
        return
    valor = match.group(1).replace(",", ".")
    try:
        valor_float = float(valor)
    except Exception:
        valor_float = 0.0
    SALDO["saldo_adm"] += valor_float
    save_saldos(SALDO)

    adm_id = str(user.id)
    if adm_id not in ADMTRABALHO:
        ADMTRABALHO[adm_id] = 0
    ADMTRABALHO[adm_id] += 1
    save_admtrabalho(ADMTRABALHO)

    protocolo_str = f"{protocolo_counter:04d}"
    protocolo_counter += 1
    save_protocolo(protocolo_counter)
    try:
        agora = format_datetime(datetime.now(), locale=lang)
        valor_formatado = format_currency(float(valor), 'BRL', locale=lang)
    except:
        agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        valor_formatado = f"R$ {valor}"
    msg = (
        f"{get_translation('payment_request', lang)}\n\n"
        f"{get_translation('operating_admin', lang)}\n"
        f"• {get_translation('id', lang)}: <code>{user.id}</code>\n"
        f"• {get_translation('name', lang)}: <code>{user.full_name}</code>\n"
        f"• {get_translation('username', lang)}: <code>@{user.username or '-'}</code>\n"
        f"📅 <b>{get_translation('date_time', lang)}:</b> <code>{agora}</code>\n"
        f"🔢 <b>{get_translation('protocol', lang)}:</b> <code>{protocolo_str}</code>\n"
        f"💰 <b>{get_translation('request_amount', lang)}:</b> <code>{valor_formatado}</code>\n\n"
        f"{get_translation('wait_confirmation', lang)}\n\n"
        "🔗 Clique aqui para acessar o pagamento: <a href='https://t.me/Epayglobabot'>t.me/Epayglobabot</a>"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

    try:
        valor_centavos = int(round(float(valor.replace(",", ".")) * 100))
        copiaecola = gerar_pix_p27pay(valor_centavos)
        img = qrcode.make(copiaecola)
        bio = BytesIO()
        img.save(bio, format="PNG")
        bio.seek(0)
        await context.bot.send_photo(
            chat_id=user.id,
            photo=bio,
            caption=f"<b>Pague com Pix Copia e Cola:</b>\n<code>{copiaecola}</code>",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await context.bot.send_message(
            chat_id=user.id,
            text=f"Erro ao gerar Pix: {str(e)}",
            parse_mode=ParseMode.HTML
        )

async def comando_total(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = await get_user_language(user)
    saldo_adm = SALDO.get("saldo_adm", 0.0)
    saldo_extrato = ACUMULADO_EXTRATO.get("saldo_extrato", 0.0)
    saldo_adm_fmt = format_currency(saldo_adm, 'BRL', locale=lang)
    saldo_extrato_fmt = format_currency(saldo_extrato, 'BRL', locale=lang)
    await update.message.reply_text(
        get_translation('saldo_total', lang).format(adm=saldo_adm_fmt, extrato=saldo_extrato_fmt),
        parse_mode=ParseMode.HTML
    )

async def comando_limparsaldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = await get_user_language(user)
    SALDO["saldo_adm"] = 0.0
    save_saldos(SALDO)
    await update.message.reply_text(get_translation('saldo_adm_limpo', lang), parse_mode=ParseMode.HTML)

async def comando_limparacumulado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = await get_user_language(user)
    ACUMULADO_EXTRATO["saldo_extrato"] = 0.0
    save_acumulado_extrato(ACUMULADO_EXTRATO)
    await update.message.reply_text(get_translation('saldo_extrato_limpo', lang), parse_mode=ParseMode.HTML)

ADMTRABALHO_PAGINAS = {}

async def comando_admtrabalho(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = await get_user_language(user)
    if user.id not in ADMIN_MASTER_IDS:
        await update.message.reply_text(get_translation('admin_master_only', lang))
        return

    pagina = 0
    ADMTRABALHO_PAGINAS[user.id] = pagina
    await mostrar_pagina_admtrabalho(update, lang, pagina, user.id)

async def mostrar_pagina_admtrabalho(update, lang, pagina, user_id):
    ADM_IDS = sorted(list(ADMIN_IDS))
    start = pagina * 10
    end = start + 10
    lista = []
    bot = update.get_bot() if hasattr(update, "get_bot") else update.application.bot

    for i, adm_id in enumerate(ADM_IDS[start:end], start=1+start):
        adm_id_str = str(adm_id)
        contagem = ADMTRABALHO.get(adm_id_str, 0)
        try:
            if adm_id == 0:
                raise Exception("ID inválido")
            chat = await bot.get_chat(adm_id)
            username = f"@{chat.username}" if chat.username else "(sem username)"
        except Exception:
            username = "(ADM inválido ou não encontrado)"
        lista.append(f"{i}. {username} | ID: <code>{adm_id}</code> | {get_translation('request_amount', lang)}: <b>{contagem}</b>")
    header = f"<b>{get_translation('admtrabalho_header', lang)}</b>\n"
    texto = header + "\n".join(lista)
    total_adms = len(ADM_IDS)
    if end < total_adms:
        texto += "\n" + get_translation('admtrabalho_paginacao', lang)
    texto += "\n\n" + get_translation('admtrabalho_footer', lang)
    await update.message.reply_text(texto, parse_mode=ParseMode.HTML)

async def comando_passar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = await get_user_language(user)
    if user.id not in ADMIN_MASTER_IDS:
        await update.message.reply_text(get_translation('admin_master_only', lang))
        return
    pagina = ADMTRABALHO_PAGINAS.get(user.id, 0) + 1
    ADM_IDS = list(ADMIN_IDS)
    if pagina * 10 >= len(ADM_IDS):
        await update.message.reply_text(get_translation('no_more_pages', lang))
        return
    ADMTRABALHO_PAGINAS[user.id] = pagina
    await mostrar_pagina_admtrabalho(update, lang, pagina, user.id)

async def comando_voltar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = await get_user_language(user)
    if user.id not in ADMIN_MASTER_IDS:
        await update.message.reply_text(get_translation('admin_master_only', lang))
        return
    pagina = ADMTRABALHO_PAGINAS.get(user.id, 0)
    if pagina <= 0:
        await update.message.reply_text(get_translation('first_page', lang))
        return
    pagina -= 1
    ADMTRABALHO_PAGINAS[user.id] = pagina
    await mostrar_pagina_admtrabalho(update, lang, pagina, user.id)

async def comando_limparadmtrabalho(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = await get_user_language(user)
    if user.id not in ADMIN_MASTER_IDS:
        await update.message.reply_text(get_translation('admin_master_only', lang))
        return
    ADMTRABALHO.clear()
    save_admtrabalho(ADMTRABALHO)
    await update.message.reply_text(get_translation('admtrabalho_limpo', lang), parse_mode=ParseMode.HTML)

async def comando_adm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ADMIN_IDS
    ADMIN_IDS = load_admins()
    user = update.effective_user
    lang = await get_user_language(user)
    if user.id not in ADMIN_MASTER_IDS:
        await update.message.reply_text(get_translation('admin_master_only', lang))
        return
    if len(context.args) == 1 and context.args[0].lower() == 'lista':
        admins = sorted(ADMIN_IDS)
        admins_list = []
        for aid in admins:
            if aid in ADMIN_MASTER_IDS:
                admins_list.append(f"👑 <code>{aid}</code> (Master)")
            else:
                admins_list.append(f"• <code>{aid}</code>")
        await update.message.reply_text(
            f"{get_translation('admin_list', lang)}\n" + "\n".join(admins_list),
            parse_mode=ParseMode.HTML
        )
        return
    if len(context.args) == 2 and context.args[0].lower() == 'remove':
        try:
            remove_id = int(context.args[1])
        except:
            await update.message.reply_text(
                f"⚠️ {get_translation('invalid_format', lang)}",
                parse_mode=ParseMode.HTML
            )
            return
        if remove_id in ADMIN_MASTER_IDS:
            await update.message.reply_text("❌ Não é possível remover um ADM Master diretamente.")
            return
        if remove_id in ADMIN_IDS:
            ADMIN_IDS.remove(remove_id)
            save_admins(ADMIN_IDS)
            await update.message.reply_text(
                get_translation('admin_removed', lang, remove_id),
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text(get_translation('admin_not_found', lang))
        return
    if len(context.args) == 1:
        try:
            novo_id = int(context.args[0])
        except:
            await update.message.reply_text(
                f"⚠️ {get_translation('invalid_format', lang)}",
                parse_mode=ParseMode.HTML
            )
            return
        if novo_id in ADMIN_IDS:
            if novo_id in ADMIN_MASTER_IDS:
                await update.message.reply_text(
                    f"⚠️ <code>{novo_id}</code> {get_translation('already_master', lang)}",
                    parse_mode=ParseMode.HTML
                )
            else:
                await update.message.reply_text(
                    f"⚠️ <code>{novo_id}</code> {get_translation('already_admin', lang)}",
                    parse_mode=ParseMode.HTML
                )
        else:
            ADMIN_IDS.add(novo_id)
            save_admins(ADMIN_IDS)
            await update.message.reply_text(
                get_translation('admin_added', lang, novo_id),
                parse_mode=ParseMode.HTML
            )
        return
    help_text = (
        f"{get_translation('available_commands', lang)}:\n"
        f"<b>/adm ID</b> - {get_translation('add_admin', lang)}\n"
        f"<b>/adm remove ID</b> - {get_translation('remove_admin', lang)}\n"
        f"<b>/adm lista</b> - {get_translation('list_admins', lang)}"
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)

async def comando_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = await get_user_language(user)
    if lang not in ['pt', 'en', 'zh']:
        lang = 'en'
    about_text = get_translation('about', lang)
    await update.message.reply_text(about_text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

async def comando_masters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = await get_user_language(user)
    if user.id not in ADMIN_MASTER_IDS:
        await update.message.reply_text(get_translation('admin_master_only', lang))
        return
    masters_list = "\n".join(f"• <code>{mid}</code>" for mid in ADMIN_MASTER_IDS)
    await update.message.reply_text(
        f"👑 <b>ADMs Masters ativos:</b>\n{masters_list}",
        parse_mode=ParseMode.HTML
    )

async def on_startup(app):
    global bot_start_time, ultimo_recebimento_time, ultimo_alerta_inatividade
    bot_start_time = datetime.now(timezone.utc)
    ultimo_recebimento_time = bot_start_time
    ultimo_alerta_inatividade = bot_start_time - timedelta(minutes=15)
    for master_id in ADMIN_MASTER_IDS:
        try:
            chat = await app.bot.get_chat(master_id)
            lang = await get_user_language(chat)
            startup_msg = (
                f"🤖 {get_translation('bot_started', lang)} {bot_start_time.strftime('%d/%m/%Y %H:%M:%S')} (UTC)\n"
                f"👑 <b>{get_translation('you_are_master', lang)}</b>\n"
                f"📌 {get_translation('only_new_payments', lang)}\n"
                f"⚠️ {get_translation('inactivity_warning', lang)}"
            )
            await app.bot.send_message(
                chat_id=master_id,
                text=startup_msg,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Erro ao notificar ADM Master {master_id}: {str(e)}")
    asyncio.create_task(monitorar_recebimentos(app))

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("adm", comando_adm))
    app.add_handler(CommandHandler("setlang", setlang))
    app.add_handler(CommandHandler("total", comando_total))
    app.add_handler(CommandHandler("limparsaldo", comando_limparsaldo))
    app.add_handler(CommandHandler("limparacumulado", comando_limparacumulado))
    app.add_handler(CommandHandler("admtrabalho", comando_admtrabalho))
    app.add_handler(CommandHandler("limparadmtrabalho", comando_limparadmtrabalho))
    app.add_handler(CommandHandler("passar", comando_passar))
    app.add_handler(CommandHandler("voltar", comando_voltar))
    app.add_handler(CommandHandler("about", comando_about))
    app.add_handler(CommandHandler("masters", comando_masters))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^(\/?\+)\s*\d"), pedido_pagamento))
    app.post_init = on_startup
    try:
        logger.info("Iniciando bot com multilíngue automático...")
        app.run_polling(drop_pending_updates=True)
    except Exception as e:
        logger.error(f"Erro fatal: {str(e)}")
        raise

if __name__ == "__main__":
    main()
