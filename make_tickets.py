"""Render synthetic, photo-like parking ticket and sign images (issue #3)."""
import json, os, random
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageChops

W, H = 800, 1200
FD = "/usr/share/fonts/truetype/dejavu/"


def font(size, bold=False, mono=False):
    name = ("DejaVuSansMono" if mono else "DejaVuSans") + ("-Bold" if bold else "") + ".ttf"
    try:
        return ImageFont.truetype(FD + name, size)
    except OSError:
        return ImageFont.load_default()


def wrap(draw, text, f, width):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=f) <= width:
            cur = t
        else:
            lines.append(cur)
            cur = w
    return lines + [cur]


def paper(w, h, color=(244, 241, 232)):
    img = Image.new("RGB", (w, h), color)
    noise = Image.effect_noise((w, h), 14).convert("RGB")
    return ImageChops.blend(img, noise, 0.07)


def shadow(img, rng):
    w, h = img.size
    g = Image.linear_gradient("L").resize((w, h))
    if rng.random() < 0.5:
        g = g.rotate(90 * rng.randint(0, 3))
    g = g.point(lambda v: int(v * 0.28))
    return Image.composite(Image.new("RGB", (w, h), (20, 20, 25)), img, g)


def crease(img):
    w, h = img.size
    band = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(band)
    d.line([(0, 330), (330, 0)], fill=120, width=26)
    band = band.filter(ImageFilter.GaussianBlur(7))
    return Image.composite(Image.new("RGB", (w, h), (60, 55, 50)), img, band)


def photoize(img, rng, angle, blur, contrast=1.0, do_crease=False, bg=(78, 82, 86)):
    img = shadow(img, rng)
    if do_crease:
        img = crease(img)
    canvas = Image.new("RGB", (W + 160, H + 160), bg)
    canvas.paste(img, (80, 80))
    canvas = canvas.rotate(angle, resample=Image.BICUBIC, expand=False, fillcolor=bg)
    canvas = canvas.crop((80, 80, 80 + W, 80 + H))
    canvas = canvas.filter(ImageFilter.GaussianBlur(blur))
    return ImageEnhance.Contrast(canvas).enhance(contrast)


def render_ticket(c, rng):
    img = paper(W, H)
    d = ImageDraw.Draw(img)
    ink = (28, 28, 34)
    private = c["issuer_type"] == "private"
    header = "KONTROLAFGIFT" if private else "PARKERINGSAFGIFT"
    d.rectangle([0, 0, W, 150], fill=(215, 190, 40) if private else (30, 70, 140))
    d.text((W // 2, 62), header, font=font(52, True), fill=(20, 20, 20) if private else (255, 255, 255), anchor="mm")
    d.text((W // 2, 118), c["issuer_name"], font=font(30), fill=(20, 20, 20) if private else (255, 255, 255), anchor="mm")
    y = 200
    rows = [("Afgiftsnr.", c["ticket_number"]), ("Reg.nr.", c["plate"]), ("Dato", c["date"]),
            ("Kl.", c["time"]), ("Sted", c["location"]), ("Overtrædelse", c["reason_on_ticket"])]
    lf, vf = font(22), font(28, True, mono=True)
    for label, val in rows:
        d.text((50, y), label, font=lf, fill=(95, 95, 100))
        lines = wrap(d, str(val), vf, W - 300)
        for ln in lines:
            d.text((250, y - 4), ln, font=vf, fill=ink)
            y += 38
        y += 14
        d.line([(50, y - 6), (W - 50, y - 6)], fill=(200, 196, 185), width=1)
    y += 20
    d.text((50, y), f"Beløb: {c['amount_dkk']} kr.", font=font(52, True), fill=ink)
    y += 100
    d.text((50, y), "Betaling / indsigelse", font=font(26, True), fill=ink)
    y += 42
    text = (f"Beløbet bedes indbetalt til {c['issuer_name']} inden 14 dage. Du kan gøre indsigelse "
            f"skriftligt til {c['issuer_name']}, Postboks 100, 2100 Testkøbing, inden 21 dage fra "
            f"afgiftens dato. Oplys afgiftsnr. og reg.nr. ved henvendelse.")
    sf = font(21)
    for ln in wrap(d, text, sf, W - 100):
        d.text((50, y), ln, font=sf, fill=ink)
        y += 30
    x, by = 50, H - 200
    while x < W - 50:
        bw = rng.choice([2, 3, 4, 6])
        d.rectangle([x, by, x + bw - 1, by + 100], fill=ink)
        x += bw + rng.choice([2, 3, 5])
    d.text((W // 2, by + 125), c["ticket_number"].replace("-", ""), font=font(20, mono=True), fill=ink, anchor="mm")
    return img


def make_tickets():
    cases = json.load(open("data/sample_cases.json", encoding="utf-8"))
    os.makedirs("data/tickets", exist_ok=True)
    rng = random.Random(42)
    out = []
    for i, c in enumerate(cases):
        angle = rng.choice([-1, 1]) * rng.uniform(1, 4)
        photo = photoize(render_ticket(c, rng), rng, angle, blur=rng.uniform(0.5, 1.3),
                         contrast=0.65 if i == 1 else 1.0, do_crease=(i == 2))
        p = f"data/tickets/{i}_{c['ticket_number']}.png"
        photo.save(p)
        out.append(p)
    return out


def render_sign(hidden, rng):
    img = Image.new("RGB", (W, H), (150, 185, 215))
    d = ImageDraw.Draw(img)
    for yy in range(H):  # sky gradient + ground
        g = int(185 + 50 * yy / H)
        d.line([(0, yy), (W, yy)], fill=(140, g, 235))
    d.rectangle([0, 1020, W, H], fill=(95, 100, 95))
    d.rectangle([385, 150, 415, 1040], fill=(120, 122, 126))  # pole
    d.rounded_rectangle([225, 90, 575, 440], radius=30, fill=(20, 80, 170), outline=(255, 255, 255), width=10)
    d.text((400, 265), "P", font=font(250, True), fill=(255, 255, 255), anchor="mm")
    d.rectangle([215, 470, 585, 760], fill=(250, 250, 250), outline=(30, 30, 30), width=5)
    d.text((400, 510), "Betalingsparkering", font=font(30, True), fill=(20, 20, 20), anchor="mm")
    d.text((400, 590), "08-20", font=font(44, True), fill=(20, 20, 20), anchor="mm")
    d.text((400, 650), "25 kr/time", font=font(36, True), fill=(20, 20, 20), anchor="mm")
    d.text((400, 715), "NordPark ApS", font=font(30), fill=(20, 20, 20), anchor="mm")
    if hidden:
        bush = Image.new("L", (W, H), 0)
        bd = ImageDraw.Draw(bush)
        for _ in range(60):
            cx, cy, r = rng.randint(150, 470), rng.randint(380, 800), rng.randint(40, 90)
            bd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
        bush = bush.filter(ImageFilter.GaussianBlur(3))
        leaves = Image.effect_noise((W, H), 40).convert("RGB")
        green = ImageChops.blend(Image.new("RGB", (W, H), (40, 110, 45)), leaves, 0.15)
        img = Image.composite(green, img, bush)
        img = ImageEnhance.Brightness(img).enhance(0.65)
    img = img.filter(ImageFilter.GaussianBlur(1.2 if hidden else 0.6))
    img = ImageChops.blend(img, Image.effect_noise((W, H), 12).convert("RGB"), 0.05)
    img = ImageEnhance.Contrast(img).enhance(0.7 if hidden else 1.0)
    return img


def make_signs():
    os.makedirs("data/tickets/signs", exist_ok=True)
    rng = random.Random(7)
    out = []
    for name, hidden in (("sign_clear", False), ("sign_hidden", True)):
        p = f"data/tickets/signs/{name}.png"
        render_sign(hidden, rng).save(p)
        out.append(p)
    return out


if __name__ == "__main__":
    for p in make_tickets() + make_signs():
        print(p)
