"""
Análisis de co-ocurrencia Dewey sobre candidatos.csv (salida de filtro_dewey.py).
Sirve para decidir reglas tipo "510 solo se descarta; 510 + 3xx pasa".

Genera coocurrencia_dewey.xlsx con 3 hojas:
  - resumen  : por código -> nombre, registros, cuántos van SOLOS (sin otra
               clase Dewey), cuántos acompañados de 3xx, 9xx, 630 o 7xx
  - parejas  : código, acompañante, nombre del acompañante, registros
               (filtra por la columna 'codigo' para ver un código a la vez)
  - solos    : registros donde el código va solo, con título (para mirar ejemplos)

Uso:  python coocurrencia_dewey.py
"""
import re
from collections import Counter, defaultdict

import pandas as pd

d = pd.read_csv("candidatos.csv", dtype=str).fillna("")
col_dewey = next(c for c in d.columns if c.strip().lower() == "dewey")
col_titulo = next((c for c in d.columns if c.strip().lower() in ("título", "titulo")), None)

# nombres de cada código, tal como vienen en el repositorio
nombres = defaultdict(Counter)
for texto in d[col_dewey]:
    for p in re.split(r"::|\s/\s|\|\||;|\n", texto):
        m = re.match(r"\s*(\d{2,3})\s*-?\s*([^/]+)", p)
        if m:
            c = m.group(1) + ("0" if len(m.group(1)) == 2 else "")
            nombres[c][m.group(2).strip()] += 1
nombre = lambda c: nombres[c].most_common(1)[0][0] if nombres.get(c) else ""

total, solos, parejas = Counter(), Counter(), Counter()
con = defaultdict(Counter)
filas_solos = []
for _, fila in d.iterrows():
    cods = sorted(set(filter(None, fila["dewey_codigos"].split("|"))))
    for c in cods:
        total[c] += 1
        # "solo" = no hay ningún código de OTRA centena (510::519 sigue siendo solo)
        otros = [o for o in cods if o[0] != c[0]]
        if not otros:
            solos[c] += 1
            if len(filas_solos) < 20000:
                filas_solos.append({"codigo": c, "nombre": nombre(c),
                                    "titulo": fila[col_titulo] if col_titulo else "",
                                    "dewey": fila[col_dewey][:150]})
        for o in otros:
            parejas[(c, o)] += 1
        for etiqueta, regla in {"con_3xx": lambda o: o[0] == "3",
                                "con_9xx": lambda o: o[0] == "9",
                                "con_7xx": lambda o: o[0] == "7",
                                "con_630": lambda o: o.startswith("63")}.items():
            if any(regla(o) for o in otros):
                con[c][etiqueta] += 1

resumen = pd.DataFrame([{
    "codigo": c, "nombre": nombre(c), "registros": n,
    "solos": solos[c], "%_solos": round(solos[c] / n * 100, 1),
    "con_3xx": con[c]["con_3xx"], "con_9xx": con[c]["con_9xx"],
    "con_7xx": con[c]["con_7xx"], "con_630": con[c]["con_630"],
} for c, n in total.items()]).sort_values("registros", ascending=False)

pares = pd.DataFrame([{
    "codigo": a, "nombre": nombre(a), "acompanante": b,
    "nombre_acompanante": nombre(b), "registros": n,
} for (a, b), n in parejas.items()]).sort_values(["codigo", "registros"],
                                                  ascending=[True, False])

with pd.ExcelWriter("coocurrencia_dewey.xlsx") as w:
    resumen.to_excel(w, sheet_name="resumen", index=False)
    pares.to_excel(w, sheet_name="parejas", index=False)
    pd.DataFrame(filas_solos).sort_values("codigo").to_excel(
        w, sheet_name="solos", index=False)

print(resumen.head(30).to_string(index=False))
print("\nListo: coocurrencia_dewey.xlsx")