import requests
import json
import os
from dotenv import load_dotenv
from datetime import datetime
import logging
import sys

# Konfigurasi logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Muat variabel lingkungan dari file .env
load_dotenv()

NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SENT_IDS_FILE = "id_sent.json"

def get_notion_data():
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    try:
        response = requests.post(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Notion data: {e}")
        return None

def send_to_telegram(chat_id, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        logger.info(f"Message sent to Telegram ID {chat_id}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending message to {chat_id}: {e}")

def format_datetime(iso_str):
    if not iso_str:
        return "-"
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception as e:
        return "-"

def read_sent_ids():
    if os.path.exists(SENT_IDS_FILE):
        with open(SENT_IDS_FILE, "r") as f:
            return json.load(f)
    return []

def save_sent_ids(sent_ids):
    with open(SENT_IDS_FILE, "w") as f:
        json.dump(sent_ids, f, indent=4)

def extract_text(rich_text_list, default="Tidak ada data"):
    if not rich_text_list:
        return default
    return " ".join([text.get("plain_text", "") for text in rich_text_list if "plain_text" in text])

def extract_date(prop):
    if isinstance(prop, dict):
        date_data = prop.get("date")
        if date_data and isinstance(date_data, dict):
            return date_data.get("start", "Tidak ada data")
    return "Tidak ada data"

def format_approval_date(date_str):
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception as e:
        logger.error(f"Error formatting date {date_str}: {e}")
        return date_str

def extract_formula(prop):
    if not isinstance(prop, dict):
        return "Tidak ada data"

    formula_result = prop.get("formula")
    if not formula_result:
        return "Tidak ada data"

    if formula_result.get("type") == "string" and formula_result.get("string") is not None:
        return formula_result["string"]
    if formula_result.get("type") == "number" and formula_result.get("number") is not None:
        return str(formula_result["number"])
    if formula_result.get("type") == "boolean" and formula_result.get("boolean") is not None:
        return str(formula_result["boolean"])
    if formula_result.get("type") == "date" and formula_result.get("date") is not None:
        return formula_result["date"].get("start", "Tidak ada data")

    return "Tidak ada data"

def main():
    notion_data = get_notion_data()
    if not notion_data:
        logger.info("No data returned from Notion.")
        sys.exit(0)

    results = notion_data.get("results", [])
    if not results:
        logger.info("No data found.")
        sys.exit(0)

    sent_ids = read_sent_ids()

    for item in results:
        item_id = item.get("id")
        properties = item.get("properties", {})

        id_activities = extract_text(properties.get("ID Activities", {}).get("rich_text", []))
        activities_name = extract_text(properties.get("Activities Name", {}).get("title", []))
        project_name = extract_text(properties.get("Project Name", {}).get("rich_text", []), default="-")
        work_package = extract_text(properties.get("Work Package Name", {}).get("rich_text", []))
        assignee_name = extract_text(properties.get("Assignee Name", {}).get("rich_text", []))
        est_start = extract_date(properties.get("Est.  Start", {}))
        est_duration = properties.get("Est. Duration", {}).get("number", "-")
        est_end = extract_date(properties.get("Est. End", {}))
        est_cost = properties.get("Est. Cost", {}).get("number", "-")
        user_name = extract_text(properties.get("User Name", {}).get("rich_text", []))
        assign_date_prop = properties.get("Assign Date")
        assignment_date_raw = None

        if assign_date_prop and isinstance(assign_date_prop, dict):
            date_obj = assign_date_prop.get("date")
        if date_obj and isinstance(date_obj, dict):
            assignment_date_raw = date_obj.get("start")

        assign_date = format_datetime(assignment_date_raw)

        link_activities = extract_formula(properties.get("Link Activities", {}))
        link_accepted = extract_formula(properties.get("Link Accepted", {}))

        id_kirim_tugas = extract_text(properties.get("ID Kirim Tugas", {}).get("rich_text", []))
        id_telegram_as = extract_text(properties.get("ID Telegram (As)", {}).get("rich_text", []))

        if item_id not in sent_ids and id_kirim_tugas != "Tidak ada data" and id_telegram_as != "Tidak ada data":
            message = (
                f"*PENUGASAN*\n\n"
                f"🗓 *Tanggal Penugasan:* {assign_date}\n"
                f"🏗 *Nama Project:* {project_name}\n"
                f"📦 *Work Package:* {work_package}\n"
                f"📄 *Nama Activity:* {activities_name}\n"
                f"🆔 *ID Activity:* {id_activities}\n"
                f"👤 *Ditugaskan Kepada:* {assignee_name}\n"
                f"📅 *Est. Start:* {est_start}\n"
                f"⏳ *Est. Duration:* {est_duration}\n"
                f"📆 *Est. End:* {est_end}\n"
                f"💸 *Est. Cost:* {est_cost}\n"
                f"👤 *User:* {user_name}\n"
                f"🔗 *Link Informasi Tugas:* {link_activities}\n"
                f"🔗 *Link Form Terima Tugas:* {link_accepted}"
            )
            send_to_telegram(id_telegram_as, message)
            sent_ids.append(item_id)
            save_sent_ids(sent_ids)

        logger.info("Processing completed.")
    sys.exit(0)

if __name__ == "__main__":
    main()
