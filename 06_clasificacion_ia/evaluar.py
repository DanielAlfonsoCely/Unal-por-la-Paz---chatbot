"""
Compara la clasificación de la IA contra la de Natalia (muestra de 300).
Uso:
  python evaluar.py ajuste_gemma12b.jsonl Muestra_clasificaci_nresultados.xlsx clave_muestra_NO_COMPARTIR.xlsx --grupo AJUSTE
"""
import argparse, json
from pathlib import Path
import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument("resultados"); ap.add_argument("muestra"); ap.add_argument("clave")
ap.add_argument("--grupo", default="AJUSTE")
a = ap.parse_args()

res = pd.DataFrame([json.loads(l) for l in Path(a.resultados).read_text(encoding="utf-8").splitlines() if l.strip()])
res["N°"] = res["id"].astype(str)
nat = pd.read_excel(a.muestra, sheet_name="Clasificar"); nat["N°"] = nat["N°"].astype(str)
cla = pd.read_excel(a.clave); cla["N°"] = cla["N°"].astype(str)
d = nat.merge(cla[["N°", "Grupo", "Tipo"]], on="N°").merge(res, on="N°", how="inner")
d = d[d["Grupo"].astype(str).str.upper().str.startswith(a.grupo.upper()[:4])]
if d.empty: raise SystemExit("No hay documentos en común entre los resultados y ese grupo.")

d["Natalia"] = d["Decisión"].astype(str).str.strip().str.upper()
d.loc[d["N°"] == "29", "Natalia"] = "INCLUIR"          # decidido: se toma como error de ella
d["abrio"] = d["¿Abrí el documento?"].astype(str).str.strip().str.lower().str.startswith("s")
d["IA"] = d["decision_final"]

pos_n = d["Natalia"].isin(["INCLUIR", "POSIBLE"])
pos_ia = d["IA"].isin(["INCLUIR", "POSIBLE", "REVISAR"])    # todo esto llega a revisión humana
def ok3(r):
    if r.IA == r.Natalia: return True
    if r.abrio and r.IA == "POSIBLE": return True             # ella tuvo que abrirlo: POSIBLE es válido
    if r.Natalia == "INCLUIR" and r.IA == "POSIBLE": return None  # no es error grave: llega a revisión
    return False
d["ok3"] = d.apply(ok3, axis=1)

print(f"\n=== {a.grupo}: {len(d)} documentos | modelo {d['modelo'].iloc[0]} | think={d['think'].iloc[0]} | prompt {d['prompt'].iloc[0]}")
print("\nTabla (filas = Natalia, columnas = IA):")
print(pd.crosstab(d["Natalia"], d["IA"], margins=True, margins_name="Total").to_string())
tp = (pos_n & pos_ia).sum(); fn = (pos_n & ~pos_ia).sum(); fp = (~pos_n & pos_ia).sum(); tn = (~pos_n & ~pos_ia).sum()
print(f"\n¿Llega a revisión? (lo importante)")
print(f"  Positivos de Natalia detectados: {tp} de {tp+fn}" + (f" ({100*tp/(tp+fn):.0f} %)" if tp+fn else ""))
print(f"  Positivos perdidos (Natalia sí, IA EXCLUIR): {fn}   <- lo grave")
print(f"  De más a revisar (Natalia EXCLUIR, IA no): {fp} de {fp+tn}")
print(f"  Acierto binario: {100*(tp+tn)/len(d):.1f} %")
print(f"\n3 clases: exactos o válidos {int((d.ok3 == True).sum())}, INCLUIR->POSIBLE {int(d.ok3.isna().sum())}, errores {int((d.ok3 == False).sum())}")
seg = d.loc[d["segundos"] > 0, "segundos"]
if len(seg): print(f"\nTiempo por documento: mediana {seg.median():.1f} s, promedio {seg.mean():.1f} s")
if "banderas" in d: 
    b = d["banderas"].explode().dropna().value_counts()
    if len(b): print("Banderas:", b.to_dict())

cols = ["N°", "Natalia", "IA", "decision_modelo", "abrio", "Título", "motivo", "tema_central", "evidencia", "Comentarios"]
err = d[(pos_n & ~pos_ia) | (~pos_n & pos_ia) | (d.ok3 == False)].copy()
err["tipo_error"] = ["PERDIDO" if (n in ("INCLUIR", "POSIBLE") and i == "EXCLUIR") else ("DE MÁS" if n == "EXCLUIR" else "OTRO")
                     for n, i in zip(err["Natalia"], err["IA"])]
err = err.sort_values("tipo_error", key=lambda s: s.map({"PERDIDO": 0, "DE MÁS": 1, "OTRO": 2}))
destino = Path(a.resultados).with_name(Path(a.resultados).stem + f"_eval_{a.grupo}.xlsx")
with pd.ExcelWriter(destino) as w:
    err[["tipo_error"] + [c for c in cols if c in err]].to_excel(w, sheet_name="Diferencias", index=False)
    d[[c for c in cols if c in d]].to_excel(w, sheet_name="Todos", index=False)
print(f"\nDiferencias para revisar: {len(err)} -> {destino}")
for _, r in err.head(15).iterrows():
    print(f"  [{r.tipo_error}] N°{r['N°']} Natalia={r.Natalia} IA={r.IA} | {str(r['Título'])[:70]}")
