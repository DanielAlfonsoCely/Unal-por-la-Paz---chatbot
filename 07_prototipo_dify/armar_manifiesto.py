"""
Arma el manifiesto de descarga de los PDFs del prototipo (INCLUIR 2011-2021).

Cruza la DB del prototipo con pesos_archivos.csv (03_medicion_pesos), que ya
trae la URL de descarga, el tamano y el md5 de cada archivo. No consulta la API.

Reglas:
  - Solo se bajan archivos del paquete ORIGINAL con extension .pdf.
  - Nombre destino: "Titulo (anio).pdf". Si un item tiene varios PDF, los
    siguientes llevan " - parte 2", " - parte 3"... Si dos items distintos
    dan el mismo nombre, se agrega " [unal-ID]" para que no se pisen.
  - Items sin PDF quedan en el manifiesto con estado "sin_pdf" (para revisarlos).

Uso (desde la carpeta 07_prototipo_dify):
  python armar_manifiesto.py
Salida: datos/manifiesto_descarga.csv
"""
import os
import re

import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(AQUI, "datos", "DB_prototipo_INCLUIR_2011-2021.xlsx")
PESOS = os.path.join(AQUI, "..", "03_medicion_pesos", "datos", "pesos_archivos.csv")
SALIDA = os.path.join(AQUI, "datos", "manifiesto_descarga.csv")
MAX_TITULO = 120


def limpio(texto):
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", str(texto))
    s = re.sub(r"\s+", " ", s).strip(" .")
    return s[:MAX_TITULO].rstrip(" .") or "sin titulo"


def anio(valor):
    m = re.match(r"\s*(\d{4})", str(valor))
    return m.group(1) if m else "s.f."


def main():
    db = pd.read_excel(DB, dtype=str)
    db["handle"] = "unal/" + db["ID"].str.strip()
    arch = pd.read_csv(PESOS, dtype=str, encoding="utf-8-sig")
    # PDF y archivos con extension rara (ej. nombre que termina en ".2014" o sin
    # extension): se intentan, y el descargador confirma por la cabecera %PDF.
    NO_PDF = {"epub", "jpg", "jpeg", "png", "xlsx", "xls", "pps", "ppt", "pptx", "doc",
              "docx", "zip", "mp3", "mp4", "csv", "txt"}
    arch = arch[(arch["bundle"] == "ORIGINAL") & ~arch["ext"].isin(NO_PDF)
                & arch["handle"].isin(set(db["handle"]))]
    arch = arch.drop_duplicates(["handle", "bitstream_uuid"])

    filas = []
    for _, d in db.iterrows():
        base = f"{limpio(d['Título'])} ({anio(d['Año'])})"
        pdfs = arch[arch["handle"] == d["handle"]].reset_index(drop=True)
        if pdfs.empty:
            filas.append({"id": d["ID"], "handle": d["handle"], "titulo": d["Título"],
                          "estado": "sin_pdf", "nombre_destino": ""})
            continue
        for i, a in pdfs.iterrows():
            nombre = base + ("" if i == 0 else f" - parte {i + 1}")
            filas.append({"id": d["ID"], "handle": d["handle"], "titulo": d["Título"],
                          "estado": "pendiente", "nombre_original": a["nombre"],
                          "bytes": a["bytes"], "md5": a["md5"], "url": a["url_descarga"],
                          "bitstream_uuid": a["bitstream_uuid"], "nombre_destino": nombre + ".pdf"})

    m = pd.DataFrame(filas)
    # choques de nombre entre items distintos
    con_nombre = m["nombre_destino"] != ""
    choque = con_nombre & m.duplicated("nombre_destino", keep=False)
    m.loc[choque, "nombre_destino"] = m.loc[choque].apply(
        lambda r: r["nombre_destino"][:-4] + f" [unal-{r['id']}].pdf", axis=1)
    assert m.loc[con_nombre, "nombre_destino"].is_unique

    m.to_csv(SALIDA, index=False, encoding="utf-8-sig")
    ok = m[m["estado"] == "pendiente"]
    print(f"Items en la DB: {len(db)}")
    print(f"PDFs a descargar: {len(ok)} de {ok['id'].nunique()} items "
          f"({ok['bytes'].astype(float).sum() / 1e9:.2f} GB)")
    print(f"Items sin PDF: {(m['estado'] == 'sin_pdf').sum()}  -> {m.loc[m['estado'] == 'sin_pdf', 'id'].tolist()}")
    print(f"Nombres con choque resuelto: {int(choque.sum())}")
    print(f"Guardado en {SALIDA}")


if __name__ == "__main__":
    main()
