import json
import os
import re
import smtplib
from email.message import EmailMessage
from playwright.sync_api import sync_playwright

ZARA_URL = "https://www.zara.com/tr/tr/s-erkek-indirim-l10847.html?v1=2439352"
STATE_FILE = "zara_state.json"


def fetch_products():
    print("===================================")
    print("ZARA DIAGNOSTIC BAŞLADI")
    print("===================================")

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

        responses = []

        def capture_response(response):
            url = response.url
            if any(x in url.lower() for x in ["api", "graphql", "product", "catalog", "search", "category"]):
                responses.append(f"{response.status} {url}")

        page.on("response", capture_response)

        try:
            response = page.goto(ZARA_URL, wait_until="domcontentloaded", timeout=60000)
            print(f"HTTP durum kodu: {response.status if response else 'bilinmiyor'}")
            print(f"Sayfa başlığı: {page.title()}")
            page.wait_for_timeout(10000)

            print(f"Sayfa URL'si: {page.url}")
            print(f"DOM karakter sayısı: {len(page.content())}")

            body_text = page.locator("body").inner_text(timeout=10000)
            print(f"BODY metin uzunluğu: {len(body_text)}")
            print("BODY ilk 1500 karakter:")
            print(body_text[:1500])

            html = page.content()
            with open("zara_debug.html", "w", encoding="utf-8") as f:
                f.write(html)

            page.screenshot(path="zara_debug.png", full_page=True)

            print("\nÖNEMLİ AĞ İSTEKLERİ:")
            if responses:
                for item in responses[:100]:
                    print(item)
            else:
                print("İlgili API/catalog/product isteği yakalanmadı.")

            print("\nSAYFADA ANAHTAR KELİME KONTROLÜ:")
            for word in ["product", "catalog", "article", "indirim", "erkek", "ZARA"]:
                print(f"{word}: {html.lower().count(word.lower())}")

            # Görünür ürün linklerini ayrıca kontrol et
            links = page.locator("a")
            link_count = links.count()
            print(f"Toplam <a> etiketi: {link_count}")

            for i in range(min(link_count, 5000)):
                href = links.nth(i).get_attribute("href")
                if not href:
                    continue
                if "-p" in href and ".html" in href:
                    url = href
                    if url.startswith("/"):
                        url = "https://www.zara.com" + url
                    url = url.split("?")[0]
                    name = "Zara ürünü"
                    try:
                        name = " ".join(links.nth(i).inner_text(timeout=500).split()) or name
                    except Exception:
                        pass
                    products[url] = name

            print(f"Ürün linki adayı: {len(products)}")

        finally:
            browser.close()

    if not products:
        print("Ürün bulunamadı; teşhis dosyaları artifact olarak kaydedilecek.")
        # Teşhis amacıyla başarısız olmasına izin veriyoruz.
        return {}

    return products


def send_mail(new_products):
    email_address = os.environ["EMAIL_ADDRESS"]
    password = os.environ["EMAIL_PASSWORD"]
    msg = EmailMessage()
    msg["Subject"] = f"🚨 Zara İndirim - {len(new_products)} yeni ürün"
    msg["From"] = email_address
    msg["To"] = email_address
    lines = ["Zara erkek indirim bölümüne yeni ürün eklendi!", "", ZARA_URL, "", "Yeni ürünler:", ""]
    for url, name in new_products[:30]:
        lines.extend([f"• {name}", url, ""])
    msg.set_content("\n".join(lines))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(email_address, password)
        smtp.send_message(msg)


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
    current = fetch_products()
    if not current:
        raise RuntimeError("Teşhis tamamlandı: Zara ürünleri görünür DOM'a gelmedi.")
    old = load_state()
    if old is None:
        save_state(current)
        print(f"İlk tarama tamamlandı: {len(current)} ürün kaydedildi.")
        return
    new_products = [(url, current[url]) for url in current if url not in old]
    if new_products:
        print(f"{len(new_products)} YENİ ÜRÜN BULUNDU!")
        send_mail(new_products)
    else:
        print("Yeni ürün yok.")
    save_state(current)


if __name__ == "__main__":
    main()
