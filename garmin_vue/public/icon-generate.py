"""
Gera os ícones PNG necessários para o PWA.
Execute uma vez: python public/icon-generate.py
Requer: pip install Pillow
"""
from PIL import Image, ImageDraw, ImageFont
import os

def make_icon(size, path):
    img = Image.new("RGBA", (size, size), (15, 17, 27, 255))  # fundo #0f111b
    draw = ImageDraw.Draw(img)
    # círculo de fundo azul
    margin = size // 8
    draw.ellipse([margin, margin, size - margin, size - margin], fill=(37, 99, 235, 255))
    # emoji 🏃 como texto
    try:
        fsize = int(size * 0.55)
        font = ImageFont.truetype("/System/Library/Fonts/Apple Color Emoji.ttc", fsize)
        draw.text((size // 2, size // 2), "🏃", font=font, anchor="mm")
    except Exception:
        pass
    img.save(path)
    print(f"Gerado: {path}")

os.makedirs("public", exist_ok=True)
make_icon(192, "public/icon-192.png")
make_icon(512, "public/icon-512.png")
make_icon(180, "public/apple-touch-icon.png")
print("Ícones gerados!")
