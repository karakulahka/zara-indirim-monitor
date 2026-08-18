import json
import os
import re
import smtplib
from email.message import EmailMessage

from playwright.sync_api import sync_playwright

ZARA_URL = "https://www.zara.com/tr/tr/s-erkek-indirim-l10847.html?v1=2439352"
STATE_FILE = "zara_state.json"
PRODUCT_PATTERN = re.compile(r"/tr/tr/[^\"']+-p\d+\.html(?:\?|$)")


def fetch_products():
    print("Zara gerçek tarayıcı ile açılıyor...")

    products = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            locale="tr-TR",
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/139.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 1200},
        )

        try:
            page.goto(ZARA_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(7000)

            # Zara katalogu sayfayı aşağı kaydırdıkça daha fazla ürün yükleyebilir.
            previous_count = 0
            stable_rounds = 0

            for _ in range(12):
                links = page.locator('a[href*="-p"]')
                count = await_count = links.count()

                for i in range(count):
                    href = links.nth(i).get_attribute("href")
                    if not href:
                        continue

                    match = PRODUCT_PATTERN.search(href)
                    if not match:
                        continue

                    url = match.group(0)
                    if url.startswith("/"):
                        url = "https://www.zara.com" + url
                    url = url.split("?")[0]

                    try:
                        name = links.nth(i).inner_text(timeout=1000).strip()
                    except Exception:
                        name = "Zara ürünü"

                    name = " ".join(name.split()) or "Zara ürünü"
                    products[url] = name

                if len(products) == previous_count:
                    stable_rounds += 1
                else:
                    stable_rounds = 0
                    previous_count = len(products)

                if stable_rounds >= 2:
                    break

                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(2500)

            print(f"Tarayıcıda toplam {len(products)} ürün bulundu.")

        finally:
            browser.close()

    if not products:
        raise RuntimeError(
            "Zara sayfası tarayıcı ile açıldı ancak ürün bağlantısı bulunamadı."
        )

    return products


def send_mail(new_products):
    email_address = os.environ["EMAIL_ADDRESS"]
    password = os.environ["EMAIL_PASSWORD"]

    msg = EmailMessage()
    msg["Subject"] = f"🚨 Zara İndirim - {len(new_products)} yeni ürün"
    msg["From"] = email_address
    msg["To"] = email_address

    lines = [
        "Zara erkek indirim bölümüne yeni ürün eklendi!",
        "",
        "İndirim sayfası:",
        ZARA_URL,
        "",
        "Yeni ürünler:",
        "",
    ]

    for url, name in new_products[:30]:
        lines.append(f"• {name}")
        lines.append(url)
        lines.append("")

    msg.set_content("\n".join(lines))

    print("Gmail'e bildirim gönderiliyor...")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(email_address, password)
        smtp.send_message(msg)

    print("E-posta başarıyla gönderildi.")


def load_state():
    if not os.path.exists(STATE_FILE):
        return None

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return None


def save_state(products):
    with open(STATE_FILE, "w", encoding="utf-8") as file:
        json.dump(products, file, ensure_ascii=False, indent=2)


def main():
    print("===================================")
    print("ZARA MONITOR BAŞLADI")
    print("===================================")

    current = fetch_products()
    old = load_state()

    if old is None:
        save_state(current)
        print(f"İlk tarama tamamlandı: {len(current)} ürün kaydedildi.")
        print("İlk çalışmada e-posta gönderilmeyecek.")
        return

    new_products = [
        (url, current[url])
        for url in current
        if url not in old
    ]

    if new_products:
        print(f"{len(new_products)} YENİ ÜRÜN BULUNDU!")
        send_mail(new_products)
    else:
        print("Yeni ürün yok.")

    save_state(current)
    print("Tarama tamamlandı.")


if __name__ == "__main__":
    main()
