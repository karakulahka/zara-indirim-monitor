import json
import os
import re
import smtplib
import requests
from bs4 import BeautifulSoup
from email.message import EmailMessage

ZARA_URL = "https://www.zara.com/tr/tr/s-erkek-indirim-l10847.html?v1=2439352"
STATE_FILE = "zara_state.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/147.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}


def fetch_products():
    response = requests.get(
        ZARA_URL,
        headers=HEADERS,
        timeout=45,
    )
    response.raise_for_status()

    html = response.text
    products = {}

    # ---------------------------------------------------------
    # 1. Önce normal HTML içindeki Zara ürün linklerini ara
    # ---------------------------------------------------------
    soup = BeautifulSoup(html, "html.parser")

    for a in soup.find_all("a", href=True):
        href = a.get("href", "")

        if ".html" not in href:
            continue

        # Zara ürün sayfalarında genellikle p0XXXXXXX.html yapısı bulunur.
        if not re.search(r"-p\d+\.html", href):
            continue

        url = href

        if url.startswith("/"):
            url = "https://www.zara.com" + url
        elif not url.startswith("http"):
            url = "https://www.zara.com/" + url

        url = url.split("?")[0]

        name = " ".join(a.get_text(" ", strip=True).split())

        if not name:
            img = a.find("img")
            if img:
                name = (
                    img.get("alt")
                    or img.get("title")
                    or ""
                ).strip()

        if not name:
            name = "Yeni Zara ürünü"

        products[url] = name

    # ---------------------------------------------------------
    # 2. Sayfada JSON-LD ürün verilerini de kontrol et
    # ---------------------------------------------------------
    for script in soup.find_all(
        "script",
        attrs={"type": "application/ld+json"}
    ):
        try:
            data = json.loads(script.string or script.get_text())
        except Exception:
            continue

        def extract_jsonld(obj):
            if isinstance(obj, dict):
                url = obj.get("url")
                name = obj.get("name")

                if (
                    isinstance(url, str)
                    and ".html" in url
                    and isinstance(name, str)
                    and name.strip()
                ):
                    clean_url = url.split("?")[0]
                    products[clean_url] = name.strip()

                for value in obj.values():
                    extract_jsonld(value)

            elif isinstance(obj, list):
                for item in obj:
                    extract_jsonld(item)

        extract_jsonld(data)

    # ---------------------------------------------------------
    # 3. Sayfanın kaynak kodunda bulunan Zara ürün URL'lerini ara
    # ---------------------------------------------------------
    url_pattern = re.compile(
        r'https?://www\.zara\.com/tr/tr/[^"\']+-p\d+\.html'
    )

    for match in url_pattern.findall(html):
        url = match.split("?")[0]

        # JSON içindeki kaçışları temizle
        url = url.replace("\\/", "/")

        if url not in products:
            products[url] = "Yeni Zara ürünü"

    # ---------------------------------------------------------
    # Sonuç yoksa hata ver
    # ---------------------------------------------------------
    if not products:
        raise RuntimeError(
            "Zara sayfasından ürün listesi okunamadı. "
            "Zara ürünleri sayfa kaynağında görünmüyor."
        )

    print(f"Zara'dan {len(products)} ürün bulundu.")

    return products


def send_mail(new_products):
    email_address = os.environ["EMAIL_ADDRESS"]
    password = os.environ["EMAIL_PASSWORD"]

    msg = EmailMessage()

    msg["Subject"] = (
        f"🚨 Zara İndirim: {len(new_products)} yeni ürün"
    )

    msg["From"] = email_address
    msg["To"] = email_address

    lines = [
        "Zara erkek indirim bölümünde yeni ürün tespit edildi!",
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

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(email_address, password)
        smtp.send_message(msg)

    print(
        f"{len(new_products)} yeni ürün için e-posta gönderildi."
    )


def load_state():
    if not os.path.exists(STATE_FILE):
        return None

    try:
        with open(
            STATE_FILE,
            "r",
            encoding="utf-8"
        ) as f:
            return json.load(f)
    except Exception:
        return None


def save_state(products):
    with open(
        STATE_FILE,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            products,
            f,
            ensure_ascii=False,
            indent=2
        )


def main():
    print("Zara ürün kontrolü başlıyor...")

    current = fetch_products()
    old = load_state()

    # ---------------------------------------------------------
    # İlk çalıştırma
    # ---------------------------------------------------------
    if old is None:
        save_state(current)

        print(
            f"İlk tarama tamamlandı: "
            f"{len(current)} ürün kaydedildi."
        )

        return

    # ---------------------------------------------------------
    # Yeni ürünleri bul
    # ---------------------------------------------------------
    new = [
        (url, current[url])
        for url in current
        if url not in old
    ]

    if new:
        print(
            f"{len(new)} yeni ürün bulundu."
        )

        send_mail(new)

    else:
        print("Yeni ürün yok.")

    # Güncel listeyi kaydet
    save_state(current)


if __name__ == "__main__":
    main()
