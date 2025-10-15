import os
import re
import requests
from bs4 import BeautifulSoup
import pandas as pd
import datetime

# =========================
# Config (sin datos personales)
# =========================
current_date = datetime.datetime.now().strftime("%Y-%m-%d")
plat = "Cetrogar"
pais = "Argentina"

# Directorio de salida configurable por variable de entorno (fallback: ./outputs)
OUTPUT_DIR = os.getenv("OUTPUT_DIR", os.path.join(".", "outputs"))
os.makedirs(OUTPUT_DIR, exist_ok=True)
nombre_archivo = os.path.join(OUTPUT_DIR, f"{current_date} {plat} SOS.xlsx")

# Categorías a recorrer (tal como aparecen en la URL)
categorias = [
    "Tecnología",
    "Electrodomésticos",
    "Bazar-y-decoración",
    # "belleza-y-cuidado-personal",
    # "hogar",
    # "Herramientas",
    # "Deportes-y-fitness",
    # "Bebés-y-ninos",
    # "Otras-categorías",
]

# Headers genéricos (sin cookies / tokens)
headers = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "es-ES,es;q=0.9",
    "cache-control": "no-cache",
    "referer": "https://www.cetrogar.com.ar/",
    "sec-ch-ua": '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133")',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
}

# =========================
# Scrape
# =========================
productos_data = []

for cat in categorias:
    bucle = False
    page = 1
    orden = 1
    first_prod = None

    while True:
        url = f"https://www.cetrogar.com.ar/{cat}.html?p={page}"
        try:
            response = requests.get(url, headers=headers, timeout=30)
        except requests.RequestException as e:
            print(f"Error de conexión a {url}: {e}")
            break

        if response.status_code != 200:
            print(f"Error HTTP {response.status_code} en {url}")
            break

        soup = BeautifulSoup(response.text, "html.parser")

        # tarjetas
        productos = soup.select("div.info-container")
        print(f"[{cat}] Página {page}: {len(productos)} productos")

        if not productos:
            print(f"No hay más productos en {cat}. Fin.")
            break

        for prod in productos:
            # ID de producto (si existe)
            price_box = prod.select_one(".price-box")
            product_id = price_box.get("data-product-id", "") if price_box else ""

            # detectar loop de paginación por repetición del primer ID
            if orden == 1 and product_id:
                first_prod = product_id
            elif first_prod and product_id == first_prod:
                bucle = True
                break

            # Nombre del producto
            name_el = prod.select_one(".product-item-name")
            nombre = name_el.get_text(strip=True) if name_el else ""

            # Link preferentemente desde el <a>, si no, fallback con slug
            a_el = prod.select_one(".product-item-name a")
            if a_el and a_el.get("href"):
                href = a_el.get("href").strip()
            else:
                # Fallback: construir slug a partir del nombre (puede fallar si el sitio cambia)
                nombre_link = re.sub(r"[^a-zA-Z0-9-]+", "-", nombre.replace(" ", "-")).strip("-")
                href = f"https://www.cetrogar.com.ar/{nombre_link}.html" if nombre_link else ""

            # Precios / descuento
            old_price_tag = prod.select_one(".old-price .price-wrapper")
            final_price_tag = prod.select_one(".price-container [data-price-type='finalPrice']")
            special_discount_tag = prod.select_one(".special-price-discount")
            tag_label_el = prod.select_one(".amlabel-text")

            old_price = old_price_tag.get("data-price-amount", "") if old_price_tag else ""
            final_price = final_price_tag.get("data-price-amount", "") if final_price_tag else ""
            special_discount = (
                special_discount_tag.get_text(strip=True).replace("OFF", "").strip()
                if special_discount_tag else ""
            )
            tag_label = tag_label_el.get_text(strip=True) if tag_label_el and tag_label_el.text else ""

            productos_data.append({
                "Fecha": current_date,
                "Producto": nombre,
                "Precio Venta": final_price,
                "Precio Neto": old_price,
                "Descuento": special_discount,
                "Promocion": tag_label,
                "Link": href,
                "Plataforma": plat,
                "Categoria": cat,
                "Página": page,
                "Orden": orden,
                "Pais": pais,
            })

            orden += 1

        if bucle:
            print(f"Detección de bucle en {cat} (ID repetido). Corto paginación.")
            break

        page += 1

# =========================
# Salida
# =========================
df = pd.DataFrame(productos_data).drop_duplicates().reset_index(drop=True)

column_order = [
    "Fecha", "Producto", "Precio Venta", "Precio Neto", "Descuento",
    "Promocion", "Link", "Plataforma", "Categoria", "Página",
    "Orden", "Pais"
]
df = df.reindex(columns=column_order)

df.to_excel(nombre_archivo, index=False)
print(f"Scrapeo finalizado. Guardado en: {nombre_archivo}")
