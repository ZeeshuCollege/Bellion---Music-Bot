import io
from typing import Optional
from PIL import Image, ImageDraw, ImageFont

def generate_ping_card(latency_ms: int, guild_count: int = 1) -> io.BytesIO:
    """
    Generates a high-quality dark themed image displaying bot latency and system stats.
    """
    width = 720
    height = 290
    
    # Base background: Deep Space Slate
    img = Image.new("RGB", (width, height), color=(11, 14, 22))
    draw = ImageDraw.Draw(img)

    # Outer border with neon blue glow
    draw.rounded_rectangle(
        [(8, 8), (width - 8, height - 8)],
        radius=20,
        outline=(47, 114, 246),
        width=2
    )

    # Inner container card
    draw.rounded_rectangle(
        [(22, 22), (width - 22, height - 22)],
        radius=16,
        fill=(17, 22, 34)
    )

    # Header section
    draw.text((45, 40), "BELLION AUDIO ENGINE", fill=(47, 114, 246))
    draw.text((width - 195, 40), "SYSTEM DIAGNOSTICS", fill=(120, 135, 160))

    # Divider line
    draw.line([(45, 68), (width - 45, 68)], fill=(30, 38, 56), width=1)

    # Latency metric display
    draw.text((45, 88), "GATEWAY LATENCY", fill=(140, 155, 180))

    if latency_ms < 90:
        color = (46, 204, 113)  # Emerald green
        status_text = "OPTIMAL"
    elif latency_ms < 180:
        color = (241, 196, 15)  # Amber gold
        status_text = "MODERATE"
    else:
        color = (231, 76, 60)   # Coral red
        status_text = "HIGH"

    # Big latency value
    draw.text((45, 115), f"{latency_ms} ms", fill=color)

    # Status badge box
    draw.rounded_rectangle(
        [(45, 195), (205, 235)],
        radius=8,
        fill=(25, 34, 52),
        outline=color,
        width=1
    )
    draw.text((60, 207), f"STATUS: {status_text}", fill=color)

    # Right side stat box
    draw.rounded_rectangle(
        [(width - 310, 95), (width - 45, 235)],
        radius=12,
        fill=(22, 28, 42),
        outline=(38, 48, 70),
        width=1
    )
    
    draw.text((width - 290, 115), "PLATFORM", fill=(110, 125, 150))
    draw.text((width - 290, 135), "Discord Components V2", fill=(220, 230, 245))

    draw.text((width - 290, 165), "SERVERS CONNECTED", fill=(110, 125, 150))
    draw.text((width - 290, 185), f"{guild_count} Active Guild(s)", fill=(220, 230, 245))

    # Footer
    draw.text((45, 250), "• ılı.lıllılı.ıllı • Bellion Core System", fill=(80, 95, 120))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
