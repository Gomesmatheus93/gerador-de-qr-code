from io import BytesIO

import qrcode
from PIL import Image, ImageDraw
from qrcode.image.svg import SvgPathImage
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


SIZES = (500, 1000, 2000)


def qr_image(url: str, fmt: str, size: int) -> tuple[bytes, str]:
    if size not in SIZES:
        raise ValueError("Resolução inválida.")
    code = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
    code.add_data(url)
    code.make(fit=True)
    if fmt == "svg":
        stream = BytesIO()
        code.make_image(image_factory=SvgPathImage).save(stream)
        return stream.getvalue(), "image/svg+xml"
    matrix = code.get_matrix()
    module_size = max(1, size // len(matrix))
    offset = (size - module_size * len(matrix)) // 2
    image = Image.new("RGB", (size, size), "white")
    draw = ImageDraw.Draw(image)
    for row_index, row in enumerate(matrix):
        for column_index, filled in enumerate(row):
            if filled:
                x = offset + column_index * module_size
                y = offset + row_index * module_size
                draw.rectangle((x, y, x + module_size - 1, y + module_size - 1), fill="black")
    stream = BytesIO()
    image.save(stream, format="PNG", optimize=True)
    if fmt == "png":
        return stream.getvalue(), "image/png"
    if fmt == "pdf":
        result = BytesIO()
        page = canvas.Canvas(result, pagesize=A4)
        width, height = A4
        side = min(width - 72, height - 144)
        page.drawImage(ImageReader(image), (width - side) / 2, (height - side) / 2 + 25, side, side)
        page.setFont("Helvetica", 8)
        page.drawCentredString(width / 2, 65, url)
        page.showPage()
        page.save()
        return result.getvalue(), "application/pdf"
    raise ValueError("Formato inválido.")
