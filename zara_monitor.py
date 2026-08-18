import json
import os
import smtplib
import requests
from bs4 import BeautifulSoup
from email.message import EmailMessage

ZARA_URL = "https://www.zara.com/tr/tr/s-erkek-indirim-l10847.html?v1=2439352"
STATE_FILE = "zara_state.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/147 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
}


def fetch_products():
    r = requests.get(ZARA_URL, headers=HEADERS, timeout=45)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    products = {}
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if ".html" not in href or "/p0" not in href:
            continue
        url = href if href.startswith("http") else "https://www.zara.com" + href
        name = " ".join(a.get_text(" ", strip=True).split())
        if not name:
            img = a.find("img")
            name = (img.get("alt") if img else "") or "Yeni Zara ürünü"
        products[url] = name
    if not products:
        raise RuntimeError("Zara sayfasından ürün listesi okunamadı.")
    return products


def send_mail(new_products):
    email_address = os.environ["EMAIL_ADDRESS"]
    password = os.environ["EMAIL_PASSWORD"]
    msg = EmailMessage()
    msg["Subject"] = f"🚨 Zara İndirim: {len(new_products)} yeni ürün"
    msg["From"] = email_address
    msg["To"] = email_address
    lines = ["Zara erkek indirim bölümüne yeni ürün geldi!", "", ZARA_URL, ""]
    for url, name in new_products[:30]:
        lines.append(f"• {name}")
        lines.append(url)
        lines.append("")
    msg.set_content("\n".join(lines))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(email_address, password)
        smtp.send_message(msg)


def load_state():
    if not os.path.exists(STATE_FILE):
        return None
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(products):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)


def main():
    current = fetch_products()
    old = load_state()
    if old is None:
        save_state(current)
        print(f"İlk tarama tamamlandı: {len(current)} ürün kaydedildi.")
        return
    new = [(url, current[url]) for url in current if url not in old]
    if new:
        send_mail(new)
        print(f"{len(new)} yeni ürün için e-posta gönderildi.")
    else:
        print("Yeni ürün yok.")
    save_state(current)

if __name__ == "__main__":
    main()
