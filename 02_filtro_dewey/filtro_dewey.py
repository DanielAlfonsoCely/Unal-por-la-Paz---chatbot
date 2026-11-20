"""
Filtro 1: año (2011-2021) + Dewey sobre el Reporte de Objetos DSpace.
No modifica el original. Genera:
  - candidatos.csv        -> registros que pasan (todas las columnas + anio, dewey_codigos, motivo_dewey)
  - resumen_filtro.txt    -> conteos para revisar / mostrar
  - codigos_dewey.xlsx    -> cada código con su nombre, registros y regla

Uso:
  pip install pandas openpyxl
  python filtro_dewey.py "Reporte de Objetos Dspace 10 jun 2026.xlsx"
  python filtro_dewey.py "Reporte de Objetos Dspace 10 jun 2026.xlsx" --sin-anios

Con --sin-anios no se filtra por año (entran todos, incluso los que no traen año)
y las salidas llevan el sufijo _todos_anios para no pisar las de 2011-2021:
  candidatos_todos_anios.csv, resumen_filtro_todos_anios.txt, codigos_dewey_todos_anios.xlsx
La columna en_2011_2021 marca cuáles caían en el rango original.
"""
import re
import sys
import unicodedata
from collections import Counter

import pandas as pd

# ---------------- CONFIGURACIÓN (lo que definimos) ----------------
ANIO_MIN, ANIO_MAX = 2011, 2021
COL_FECHA = "fecha del documento"      # la misma que usamos antes (dio 21486 en rango)

DESCARTA_PRIMER_DIGITO = {"0", "1", "2", "4", "8"}
PASAN_COMPLETOS = {"7", "9"}                       # artes, historia
NO_3XX = {"332", "395"}                            # 3xx: todo menos estos
SI_5XX = {"510", "519", "522", "526", "530", "542", "549",
          "552", "553", "558", "560", "577"}       # 5xx: solo estos
SI_6XX = {"621", "622", "630", "633", "634", "635", "636", "637", "638",
          "639", "640", "643", "645", "649", "657", "668", "670", "677", "696"}
TALVEZ_6XX = {"610"}                               # pasa, marcado para el LLM
# 6xx/5xx que no estén en SI se descartan (incluye 650, 606, 611)

# CONDICIONALES: solo pasan si el registro trae OTRO código que pase por sí mismo
# (ej. 510 solo -> descarte; 510 + 330 -> pasa por el 330)
CONDICIONALES = {
    "510", "519", "530", "610",                    # confirmados
    # técnicos
    "522", "542", "549", "552", "560", "621", "640", "643", "645",
    "649", "657", "668", "670", "677", "696",
    # otras regiones (historia no colombiana)
    "930", "940", "945", "950", "970", "972", "973", "990",
    # 3xx que solos casi nunca tratan tierra/territorio
    "302", "310", "327", "337", "339", "341", "345", "347",
    "355", "364", "365", "368",
    "370", "371", "372", "373", "374", "375", "378",   # educación (379 pasa)
    "380",                                              # 381, 382, 384-388 pasan
    "392", "393", "394",                                # 399 pasa
}

# RESCATE: si un registro se descarta por Dewey (cualquier regla) pero alguna de
# estas columnas contiene un término fuerte, vuelve a entrar (va al LLM).
COLS_RESCATE = ["título", "abstract", "subject", "línea de investigación", "collection"]
TERMINOS_RESCATE = [            # texto normalizado: minúsculas y sin tildes
    r"reforma (agraria|rural)", r"tenencia de (la )?tierra", r"acceso a (la )?tierra",
    r"concentracion de (la )?tierra", r"restitucion de tierras", r"baldio",
    r"campesin", r"(?<!ciencias )agrari", r"despojo", r"desplazamiento forzado",
    r"zonas? de reserva campesina", r"\bpdet\b", r"ley 1448", r"ley 160\b",
    r"desarrollo rural",
    r"\bland (tenure|reform|restitution|grabbing|access)", r"peasant",
    r"(?<!sciences )agrarian", r"rural (reform|development)", r"forced displacement",
]
# 7xx: solo pasan solos los de planificación del territorio (71x);
# el resto de 7xx (arquitectura, música, pintura, deportes...) es condicional
SIETE_PASAN_SOLOS = ("71",)

# Tipos que no son texto: se descartan directo
TIPOS_EXCLUIDOS = {"audio", "partitura", "simulacion", "imagenes",
                   "grabacion sonora", "presentacion", "objeto de aprendizaje"}

# "5" o "6" sueltos (sin división): se tratan como condicionales
# False = solo pasan si otro código del registro pasa
PASAR_INDETERMINADOS = False
# -------------------------------------------------------------------


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return s.strip().lower()


def buscar_col(df, nombre):
    for c in df.columns:
        if norm(c) == norm(nombre):
            return c
    sys.exit(f"No encontré la columna '{nombre}'. Columnas: {list(df.columns)}")


SEP = r"::|\s/\s|\|\||;|\n"
NOMBRE_A_CODIGO = {}     # se llena con aprender_nombres() desde el mismo reporte
SIN_RESOLVER = Counter()  # nombres sin número que no se pudieron traducir


def clave(nombre):
    return re.sub(r"[^a-z0-9 ]", "", norm(nombre)).strip()


def aprender_nombres(serie):
    """De los segmentos '540 - Química y ciencias afines' aprende nombre -> código."""
    votos = {}
    for texto in serie.dropna():
        for p in re.split(SEP, str(texto)):
            m = re.match(r"\s*(\d{3})\s*-\s*(.+)", p)
            if m:
                votos.setdefault(clave(m.group(2)), Counter())[m.group(1)] += 1
    for k, c in votos.items():
        NOMBRE_A_CODIGO[k] = c.most_common(1)[0][0]


def extraer_codigos(texto, contar=False):
    """Códigos de cada segmento; si el segmento no trae número, lo traduce por nombre."""
    if pd.isna(texto) or not str(texto).strip():
        return []
    cods, pendientes = [], []
    for p in re.split(SEP, str(texto)):
        if not p.strip():
            continue
        m = re.match(r"\s*(\d{1,3})(?!\d)", p)
        if m:
            c = m.group(1)
            # formato de divisiones: "62 Ingeniería..." equivale a 620
            cods.append(c + "0" if len(c) == 2 else c)
        elif clave(p) in NOMBRE_A_CODIGO:
            cods.append(NOMBRE_A_CODIGO[clave(p)])
        else:
            pendientes.append(p.strip())
    # solo reportar nombres de registros que quedaron SIN ningún código
    if contar and not cods:
        for p in pendientes:
            SIN_RESOLVER[p] += 1
    return cods


def decidir(cods):
    """Devuelve (pasa: bool, motivo: str)."""
    if not cods:
        return True, "dewey_vacio"
    # por cada clase (primer dígito) usar el código más específico disponible
    por_clase = {}
    for c in cods:
        por_clase.setdefault(c[0], []).append(c)
    resultados = []
    for d, lista in por_clase.items():
        tres = [c for c in lista if len(c) == 3]
        usar = tres if tres else lista
        for c in usar:
            if c in CONDICIONALES or (d == "7" and not c.startswith(SIETE_PASAN_SOLOS)):
                resultados.append(("cond", f"condicional_solo_{c}"))
            elif d in DESCARTA_PRIMER_DIGITO:
                resultados.append(("no", f"descarta_{d}xx"))
            elif d in PASAN_COMPLETOS:
                resultados.append(("si", f"pasa_{d}xx"))
            elif d == "3":
                if c in NO_3XX:
                    resultados.append(("no", f"no_{c}"))
                else:
                    resultados.append(("si", "pasa_3xx"))
            elif d in ("5", "6"):
                lista_si = SI_5XX if d == "5" else SI_6XX
                if len(c) < 3:
                    resultados.append(("indet", f"indeterminado_{d}xx"))
                elif c in lista_si:
                    resultados.append(("si", f"si_{c}"))
                elif c in TALVEZ_6XX:
                    resultados.append(("si", f"talvez_{c}"))
                else:
                    resultados.append(("no", f"no_{c}"))
    for estado, motivo in resultados:          # basta que uno cumpla
        if estado == "si":
            return True, motivo
    for estado, motivo in resultados:
        if estado == "indet":
            return PASAR_INDETERMINADOS, motivo
    for estado, motivo in resultados:          # condicional sin acompañante que pase
        if estado == "cond":
            return False, motivo
    return False, resultados[0][1] if resultados else "sin_codigo"


def periodo(anio):
    """Agrupa el año para el resumen."""
    if pd.isna(anio):
        return "sin año"
    a = int(anio)
    if a < 1990:
        return "antes de 1990"
    if a < 2000:
        return "1990-1999"
    if a < 2011:
        return "2000-2010"
    if a <= 2021:
        return "2011-2021 (rango original)"
    return "2022 en adelante"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    sin_anios = "--sin-anios" in sys.argv[1:]
    if not args:
        sys.exit("Uso: python filtro_dewey.py <ruta_reporte.xlsx> [--sin-anios]")
    ruta = args[0]
    suf = "_todos_anios" if sin_anios else ""
    print(f"Modo: {'SIN filtro de años' if sin_anios else f'años {ANIO_MIN}-{ANIO_MAX}'}")
    print("Leyendo (puede tardar 1-2 min)...")
    df = pd.read_excel(ruta, dtype=str)
    total = len(df)

    col_fecha = buscar_col(df, COL_FECHA)
    col_dewey = buscar_col(df, "Dewey")
    col_tipo = buscar_col(df, "Tipo")

    aprender_nombres(df[col_dewey])
    print(f"Diccionario nombre->código aprendido: {len(NOMBRE_A_CODIGO)} nombres")

    # --- diagnóstico del formato Dewey (para verificar el parseo) ---
    print("\nEjemplos del campo Dewey y códigos extraídos:")
    ejemplos = df[col_dewey].dropna().drop_duplicates().sample(
        n=min(12, df[col_dewey].nunique()), random_state=1)
    for e in ejemplos:
        print(f"  {str(e)[:90]!r:95} -> {extraer_codigos(e)}")

    # --- año ---
    df["anio"] = pd.to_numeric(
        df[col_fecha].astype(str).str.extract(r"((?:19|20)\d{2})")[0], errors="coerce")
    df["en_2011_2021"] = df["anio"].between(ANIO_MIN, ANIO_MAX)
    sin_anio = int(df["anio"].isna().sum())
    if sin_anios:
        en_rango = df.copy()
    else:
        en_rango = df[df["en_2011_2021"]].copy()
    n_rango = len(en_rango)
    es_no_texto = en_rango[col_tipo].fillna("").map(norm).isin(TIPOS_EXCLUIDOS)
    n_no_texto = int(es_no_texto.sum())
    en_rango = en_rango[~es_no_texto].copy()

    # --- Dewey ---
    en_rango["dewey_codigos"] = en_rango[col_dewey].apply(
        lambda x: "|".join(extraer_codigos(x, contar=True)))
    sin_num = en_rango[col_dewey].fillna("").str.match(r"^\s*[^\d\s]")
    traducidos = int((sin_num & (en_rango["dewey_codigos"] != "")).sum())
    dec = en_rango[col_dewey].apply(lambda x: decidir(extraer_codigos(x)))
    en_rango["pasa_dewey"] = [p for p, _ in dec]
    en_rango["motivo_dewey"] = [m for _, m in dec]

    # --- rescate por palabras en registros descartados ---
    cols_r = [c for c in en_rango.columns if norm(c) in {norm(x) for x in COLS_RESCATE}]
    print(f"Columnas usadas para rescate: {cols_r}")
    patrones = [re.compile(p) for p in TERMINOS_RESCATE]

    def termino_rescate(fila):
        texto = norm(" ".join(str(fila[c]) for c in cols_r if pd.notna(fila[c])))
        for p in patrones:
            m = p.search(texto)
            if m:
                return m.group(0)
        return ""

    en_rango["rescate"] = ""
    descartados = ~en_rango["pasa_dewey"]
    en_rango.loc[descartados, "rescate"] = en_rango[descartados].apply(termino_rescate, axis=1)
    rescatados = descartados & (en_rango["rescate"] != "")
    resc_por_motivo = en_rango.loc[rescatados, "motivo_dewey"].value_counts()
    resc_por_termino = en_rango.loc[rescatados, "rescate"].value_counts()
    en_rango.loc[rescatados, "motivo_dewey"] = "rescatado(" + en_rango.loc[rescatados, "motivo_dewey"] + ")"
    en_rango.loc[rescatados, "pasa_dewey"] = True

    cand = en_rango[en_rango["pasa_dewey"]].drop(columns=["pasa_dewey"])
    desc = en_rango[~en_rango["pasa_dewey"]]

    cand.to_csv(f"candidatos{suf}.csv", index=False, encoding="utf-8-sig")

    # --- lista de códigos: código, nombre, registros, decisión ---
    codigo_a_nombre = {}
    for texto in df[col_dewey].dropna():
        for p in re.split(SEP, str(texto)):
            m = re.match(r"\s*(\d{2,3})\s*-?\s*([^/]+)", p)
            if m:
                c = m.group(1) + ("0" if len(m.group(1)) == 2 else "")
                codigo_a_nombre.setdefault(c, Counter())[m.group(2).strip()] += 1
    conteo = Counter()
    for s in en_rango["dewey_codigos"]:
        for c in set(filter(None, s.split("|"))):
            conteo[c] += 1
    col_reg = "registros_todos_anios" if sin_anios else f"registros_{ANIO_MIN}_{ANIO_MAX}"
    filas = []
    for c, n in sorted(conteo.items()):
        nombres = codigo_a_nombre.get(c)
        pasa, motivo = decidir([c])
        filas.append({"codigo": c,
                      "nombre": nombres.most_common(1)[0][0] if nombres else "",
                      col_reg: n,
                      "decision": "PASA" if pasa else "DESCARTA",
                      "regla": motivo})
    pd.DataFrame(filas).to_excel(f"codigos_dewey{suf}.xlsx", index=False)

    # --- resumen ---
    def bloque(titulo, serie, n=30):
        lineas = [f"\n== {titulo} =="]
        vc = serie.value_counts(dropna=False).head(n)
        for k, v in vc.items():
            lineas.append(f"  {str(k)[:60]:62} {v:6}  ({v / len(serie) * 100:5.1f}%)")
        return lineas

    out = [
        f"Modo: {'SIN filtro de años' if sin_anios else f'años {ANIO_MIN}-{ANIO_MAX}'}",
        f"Total registros en el reporte: {total}",
        f"Sin año en '{col_fecha}': {sin_anio}",
        f"Registros que entran al filtro Dewey (antes de quitar no-texto): {n_rango}",
        f"Descartados por Tipo no-texto: {n_no_texto}",
        f"Dewey sin número (solo texto): {int(sin_num.sum())}, "
        f"traducidos a código: {traducidos}",
        f"PASAN Dewey (candidatos): {len(cand)}  (incluye {int(rescatados.sum())} rescatados por palabras)",
        f"Descartados por Dewey: {len(desc)}",
    ]
    if sin_anios:
        en_orig = int(cand["en_2011_2021"].sum())
        out += [
            f"\nDe los candidatos, en {ANIO_MIN}-{ANIO_MAX} (base actual, debería dar 8837): {en_orig}",
            f"Candidatos NUEVOS al quitar el filtro de años: {len(cand) - en_orig}",
        ]
        orden = ["antes de 1990", "1990-1999", "2000-2010", "2011-2021 (rango original)",
                 "2022 en adelante", "sin año"]
        per = cand["anio"].map(periodo).value_counts().reindex(orden, fill_value=0)
        out += ["\n== Candidatos por período =="]
        out += [f"  {k:30} {v:6}  ({v / len(cand) * 100:5.1f}%)" for k, v in per.items()]
        out += bloque("Candidatos NUEVOS (fuera de 2011-2021) por Tipo",
                      cand.loc[~cand["en_2011_2021"], col_tipo])
    out += ["\n== Rescatados: por qué regla se habían descartado =="]
    out += [f"  {str(k)[:60]:62} {v:6}" for k, v in resc_por_motivo.head(20).items()]
    out += ["\n== Rescatados: término que los rescató =="]
    out += [f"  {str(k)[:60]:62} {v:6}" for k, v in resc_por_termino.items()]
    out += bloque("Candidatos por motivo", cand["motivo_dewey"])
    out += bloque("Descartados por motivo", desc["motivo_dewey"])
    out += bloque("Candidatos por Tipo", cand[col_tipo])
    out += ["\n== Nombres de registros que quedaron SIN código (top 25) =="]
    out += [f"  {k[:60]:62} {v:6}" for k, v in SIN_RESOLVER.most_common(25)]
    out += ["\n(Indeterminados = 5xx/6xx con solo código general; "
            f"PASAR_INDETERMINADOS={PASAR_INDETERMINADOS})"]

    texto = "\n".join(out)
    print("\n" + texto)
    with open(f"resumen_filtro{suf}.txt", "w", encoding="utf-8") as f:
        f.write(texto)
    print(f"\nListo: candidatos{suf}.csv, resumen_filtro{suf}.txt y codigos_dewey{suf}.xlsx")


if __name__ == "__main__":
    main()