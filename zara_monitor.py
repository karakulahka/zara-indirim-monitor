import json
import os
import re
import smtplib
import requests
from email.message import EmailMessage

ZARA_URL = "https://www.zara.com/tr/tr/s-erkek-indirim-l10847.html?v1=2439352"
STATE_FILE = "zara_state.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/147.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
}


def fetch_products():
    print("Zara sayfası indiriliyor...")

    response = requests.get(
        ZARA_URL,
        headers=HEADERS,
        timeout=45
    )

    response.raise_for_status()

    html = response.text

    print(f"Sayfa alındı: {len(html)} karakter")

    products = {}

    # Zara ürün URL'lerini bul
    pattern = re.compile(
        r'(?:https?:)?//www\.zara\.com/tr/tr/[^"\']+?-p\d+\.html'
    )

    matches = pattern.findall(html)

    print(f"Kaynak kodunda {len(matches)} ürün bağlantısı bulundu.")

    for url in matches:

        if url.startswith("//"):
            url = "https:" + url

        url = url.replace("\\/", "/")

        # Query parametrelerini kaldır
        url = url.split("?")[0]

        # Aynı URL'leri tekrar ekleme
        products[url] = "Zara ürünü"

    # Eğer kaynak kodunda ürün yoksa farklı bir URL deseni dene
    if not products:

        pattern2 = re.compile(
            r'https?://www\.zara\.com/tr/tr/[^"\']*p\d+\.html'
        )

        matches2 = pattern2.findall(html)

        print(
            f"Alternatif aramada {len(matches2)} bağlantı bulundu."
        )

        for url in matches2:
            url = url.replace("\\/", "/")
            url = url.split("?")[0]
            products[url] = "Zara ürünü"

    if not products:
        raise RuntimeError(
            "Zara ürün bağlantıları bulunamadı."
        )

    print(
        f"Toplam {len(products)} benzersiz ürün bulundu."
    )

    return products


def send_mail(new_products):

    email_address = os.environ["EMAIL_ADDRESS"]
    password = os.environ["EMAIL_PASSWORD"]

    msg = EmailMessage()

    msg["Subject"] = (
        f"🚨 Zara İndirim - {len(new_products)} yeni ürün"
    )

    msg["From"] = email_address
    msg["To"] = email_address

    lines = [
        "Zara erkek indirim bölümüne yeni ürün eklendi!",
        "",
        ZARA_URL,
        "",
        "Yeni ürünler:",
        ""
    ]

    for url, name in new_products[:30]:

        lines.append(f"• {name}")
        lines.append(url)
        lines.append("")

    msg.set_content("\n".join(lines))

    print("Gmail'e bildirim gönderiliyor...")

    with smtplib.SMTP_SSL(
        "smtp.gmail.com",
        465
    ) as smtp:

        smtp.login(
            email_address,
            password
        )

        smtp.send_message(msg)

    print("E-posta başarıyla gönderildi.")


def load_state():

    if not os.path.exists(STATE_FILE):
        return None

    try:

        with open(
            STATE_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    except Exception:

        return None


def save_state(products):

    with open(
        STATE_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            products,
            file,
            ensure_ascii=False,
            indent=2
        )


def main():

    print("===================================")
    print("ZARA MONITOR BAŞLADI")
    print("===================================")

    current = fetch_products()

    old = load_state()

    # İlk çalışma
    if old is None:

        save_state(current)

        print(
            f"İlk tarama tamamlandı. "
            f"{len(current)} ürün kaydedildi."
        )

        print(
            "Bu çalışmada e-posta gönderilmeyecek."
        )

        return

    # Daha önce görülmeyen ürünleri bul
    new_products = []

    for url in current:

        if url not in old:

            new_products.append(
                (url, current[url])
            )

    if new_products:

        print(
            f"{len(new_products)} YENİ ÜRÜN BULUNDU!"
        )

        send_mail(new_products)

    else:

        print(
            "Yeni ürün yok."
        )

    # Güncel listeyi kaydet
    save_state(current)

    print("Tarama tamamlandı.")


if __name__ == "__main__":
    main()
