"""Onaylı teklif için PDF belge çıktısı.

``reportlab`` varsa onu kullanır; yoksa geçerli, metin içeren minimal
bir PDF üretir (stdlib). Her iki yolda da çıktı ``%PDF`` ile başlar.
Dışa aktarma kuralı (onaysız teklif yok) çağıran uç noktada denetlenir;
bu modül yalnızca belgeyi çizer.
"""

from __future__ import annotations

from typing import Any


def _lines_text(document: dict[str, Any]) -> list[str]:
    lines = [
        "LINEVORA TEKLIF",
        f"Musteri: {document.get('customer', '')}",
        f"Baslik: {document.get('title', '')}",
        f"Teklif: {document.get('quote_id', '')}  Durum: {document.get('status', '')}",
        "",
        "Kalemler:",
    ]
    for line in document.get("lines", []):
        lines.append(
            f"- {line.get('product_code', '')} x{line.get('quantity', '')} "
            f"= {line.get('amount', '')} {line.get('currency', '')}"
        )
    lines.append("")
    for total in document.get("totals", []):
        lines.append(f"Toplam ({total.get('currency', '')}): {total.get('amount', '')}")
    terms = document.get("terms") or {}
    if terms:
        lines += ["", f"Sartlar: {terms.get('name', '')}", str(terms.get("text", ""))]
    lines += [
        "",
        f"Hazirlayan: {document.get('prepared_by', '')}",
        f"Onaylayan: {document.get('approved_by', '') or ''}",
    ]
    return lines


def render_quote_pdf(document: dict[str, Any]) -> bytes:
    text_lines = _lines_text(document)
    try:
        return _render_reportlab(text_lines)
    except Exception:
        return _render_minimal(text_lines)


def _render_reportlab(text_lines: list[str]) -> bytes:
    import io

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    y = A4[1] - 50
    for line in text_lines:
        pdf.drawString(50, y, line[:110])
        y -= 16
        if y < 50:
            pdf.showPage()
            y = A4[1] - 50
    pdf.save()
    return buffer.getvalue()


def _escape(text: str) -> str:
    return (
        text.encode("latin-1", "replace")
        .decode("latin-1")
        .replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )


def _render_minimal(text_lines: list[str]) -> bytes:
    content_lines = ["BT /F1 11 Tf 50 800 Td"]
    for index, line in enumerate(text_lines):
        if index:
            content_lines.append("0 -16 Td")
        content_lines.append(f"({_escape(line)}) Tj")
    content_lines.append("ET")
    content = "\n".join(content_lines).encode("latin-1", "replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n"
    ).encode()
    return bytes(out)
