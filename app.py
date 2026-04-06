import streamlit as st
import pandas as pd
import re
import io
from rapidfuzz import fuzz

st.set_page_config(
    page_title="Catégorisation de mots-clés",
    page_icon="🔍",
    layout="wide"
)

st.title("🔍 Catégorisation de mots-clés")
st.caption("Sans API, sans coût — correspondance exacte et approximative.")

# ── Helpers ──────────────────────────────────────────────────────────────────

def normalize(text):
    text = text.lower().strip()
    text = re.sub(r'[^a-zà-ÿ0-9\s]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()

def find_value(keyword, values, mode, threshold):
    kw_norm = normalize(keyword)
    if mode == "Exact":
        for val in values:
            if normalize(val) in kw_norm:
                return val
        return ""
    else:
        best_val, best_score = "", 0
        for val in values:
            val_norm = normalize(val)
            if val_norm in kw_norm:
                return val
            score = fuzz.partial_ratio(val_norm, kw_norm)
            if score > best_score and score >= threshold:
                best_score = score
                best_val = val
        return best_val

def to_excel(df):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Résultats")
        ws = writer.sheets["Résultats"]
        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 50)
    return buf.getvalue()

# ── Session state ─────────────────────────────────────────────────────────────

if "matrix" not in st.session_state:
    st.session_state.matrix = {}
if "keywords" not in st.session_state:
    st.session_state.keywords = []
if "results" not in st.session_state:
    st.session_state.results = None

# ── Layout ────────────────────────────────────────────────────────────────────

col1, col2 = st.columns([1, 1], gap="large")

# ── COLONNE GAUCHE : Inputs ───────────────────────────────────────────────────

with col1:

    # STEP 1
    st.subheader("1 · Matrice de catégories")
    st.caption("Colonnes = catégories, lignes = valeurs possibles")

    matrix_file = st.file_uploader(
        "Fichier Excel (.xlsx)",
        type=["xlsx"],
        key="matrix_upload",
        label_visibility="collapsed"
    )

    if matrix_file:
        df_matrix = pd.read_excel(matrix_file).dropna(how="all").dropna(how="all", axis=1)
        df_matrix.columns = [str(c).strip() for c in df_matrix.columns]
        matrix = {
            col: df_matrix[col].dropna().astype(str).str.strip().tolist()
            for col in df_matrix.columns
        }
        matrix = {k: [v for v in vals if v] for k, vals in matrix.items()}
        st.session_state.matrix = matrix

    if st.session_state.matrix:
        for cat, vals in st.session_state.matrix.items():
            st.markdown(f"**{cat}** — {', '.join(vals)}")
        st.success(f"{len(st.session_state.matrix)} catégories chargées")

    st.divider()

    # STEP 2
    st.subheader("2 · Mots-clés")
    st.caption("Un mot-clé par ligne — Excel ou CSV")

    kw_file = st.file_uploader(
        "Fichier mots-clés",
        type=["xlsx", "csv", "txt"],
        key="kw_upload",
        label_visibility="collapsed"
    )

    kw_text = st.text_area(
        "Ou collez vos mots-clés ici",
        placeholder="lunettes de vue homme noir\nlunettes de soleil femme gucci\nlentilles enfant bleu",
        height=120
    )

    if st.button("Charger les mots-clés", use_container_width=True):
        kws = []
        if kw_file:
            if kw_file.name.endswith(".csv") or kw_file.name.endswith(".txt"):
                df_kw = pd.read_csv(kw_file, header=None)
            else:
                df_kw = pd.read_excel(kw_file, header=None)
            kws += df_kw.iloc[:, 0].dropna().astype(str).str.strip().tolist()
        if kw_text.strip():
            kws += [k.strip() for k in kw_text.strip().split("\n") if k.strip()]
        kws = list(dict.fromkeys(kws))
        st.session_state.keywords = kws

    if st.session_state.keywords:
        st.success(f"{len(st.session_state.keywords)} mots-clés chargés")
        with st.expander("Aperçu"):
            st.write(st.session_state.keywords[:20])
            if len(st.session_state.keywords) > 20:
                st.caption(f"... et {len(st.session_state.keywords) - 20} autres")

    st.divider()

    # STEP 3 — Paramètres
    st.subheader("3 · Paramètres")

    mode = st.radio(
        "Mode de correspondance",
        ["Exact", "Approximatif (fuzzy)"],
        horizontal=True,
        help="Exact = le mot doit être présent tel quel. Fuzzy = gère les variantes orthographiques."
    )

    threshold = 85
    if mode == "Approximatif (fuzzy)":
        threshold = st.slider(
            "Seuil de similarité",
            min_value=60, max_value=100, value=85, step=5,
            help="Plus le seuil est élevé, plus la correspondance est stricte."
        )

    # Bouton principal
    st.divider()
    run = st.button(
        "🚀 Catégoriser les mots-clés",
        type="primary",
        use_container_width=True,
        disabled=not (st.session_state.matrix and st.session_state.keywords)
    )

# ── COLONNE DROITE : Résultats ────────────────────────────────────────────────

with col2:
    st.subheader("4 · Résultats")

    if run:
        matrix = st.session_state.matrix
        keywords = st.session_state.keywords
        results = []

        progress = st.progress(0, text="Catégorisation en cours...")
        total = len(keywords)

        for i, kw in enumerate(keywords):
            row = {"Mot-clé": kw}
            for cat, vals in matrix.items():
                row[cat] = find_value(kw, vals, mode.split()[0], threshold)
            results.append(row)
            if i % 50 == 0:
                progress.progress((i + 1) / total, text=f"{i + 1} / {total} mots-clés traités...")

        progress.progress(1.0, text="Terminé !")
        st.session_state.results = pd.DataFrame(results)

    if st.session_state.results is not None:
        df = st.session_state.results
        cats = [c for c in df.columns if c != "Mot-clé"]

        # Métriques
        metric_cols = st.columns(len(cats))
        for i, cat in enumerate(cats):
            filled = (df[cat] != "").sum()
            pct = round(filled / len(df) * 100)
            metric_cols[i].metric(cat, f"{pct}%", f"{filled}/{len(df)}")

        # Tableau
        st.dataframe(df, use_container_width=True, height=420)

        # Export
        excel_data = to_excel(df)
        st.download_button(
            label="⬇️ Télécharger en Excel",
            data=excel_data,
            file_name="resultats_categorisation.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            type="primary"
        )

    else:
        st.info("Les résultats apparaîtront ici après la catégorisation.")
