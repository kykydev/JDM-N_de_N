#!/usr/bin/env python3
"""Contrôle et préparation hors-ligne du corpus « A de B ».

Lit data/corpus/raw/*.csv (jamais modifiés), produit :
  - data/corpus/clean/<nom>.csv   (une ligne par syntagme, ordre d'origine conservé)
  - data/corpus/clean/termes.csv  (termes dédupliqués, entrée de l'étape 2)
  - reports/rapport_corpus.md     (synthèse des contrôles)

Aucune suppression, aucune lemmatisation, aucun appel réseau.
Déterministe : même entrée -> mêmes fichiers octet pour octet.

Usage : python3 src/corpus_check.py [--raw DIR] [--clean DIR] [--report FICHIER]
        (défauts : data/corpus/raw, data/corpus/clean, reports/rapport_corpus.md)
"""

import argparse
import csv
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "corpus" / "raw"
CLEAN_DIR = ROOT / "data" / "corpus" / "clean"
REPORT_PATH = ROOT / "reports" / "rapport_corpus.md"

EXPECTED_LINES = 80
TRAIN_SIZE = 50
# Seuil à partir duquel un même terme A ou B est signalé comme répété dans un type.
REPETITION_THRESHOLD = 3

APOS = "['’]"
# Ordre des alternatives = priorité au motif le plus long (« de la » avant « de »).
# Chaque motif doit être précédé d'un espace : la préposition n'est jamais en tête.
PREP_RE = re.compile(
    rf"(?<=\s)(?P<prep>de\s+la\s+|de\s+l{APOS}\s*|des\s+|du\s+|de\s+|d{APOS}\s*)",
    re.IGNORECASE,
)
# Déterminant indéfini après « de »/« d' » : « d'un mariage », « d'une reine ».
INDEF_RE = re.compile(r"^(?P<det>une?)\s+(?=\S)", re.IGNORECASE)
# Autres déterminants non prévus par les règles du papier : signalés, pas traités.
OTHER_DET_RE = re.compile(
    r"^(ce|cet|cette|ces|mon|ma|mes|ton|ta|tes|son|sa|ses|notre|nos|votre|vos|leur|leurs)\s",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Normalisation (comparaison uniquement, jamais écrite dans les sorties)
# ---------------------------------------------------------------------------

def norm(text):
    text = unicodedata.normalize("NFC", text)
    text = text.replace("’", "'")
    text = re.sub(r"\s+", " ", text).strip()
    return text.lower()


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_file(path):
    """Renvoie (entrées, anomalies). Chaque entrée garde son numéro de ligne physique."""
    entries, issues = [], []
    raw_lines = path.read_bytes().split(b"\n")
    if raw_lines and raw_lines[-1] == b"":
        raw_lines.pop()  # saut de ligne final
    for lineno, raw in enumerate(raw_lines, start=1):
        try:
            line = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            issues.append((lineno, f"UTF-8 invalide ({exc.reason}, octet {exc.start})", raw.decode("utf-8", "replace")))
            continue
        if lineno == 1:
            line = line.lstrip("﻿")
        line = line.rstrip("\r")
        if not line.strip():
            issues.append((lineno, "ligne vide", line))
            continue
        parts = re.split(r"\s*;\s*", line.strip())
        if len(parts) != 2:
            issues.append((lineno, f"{len(parts)} champ(s) au lieu de 2", line))
            continue
        syntagme, relation = (re.sub(r"\s+", " ", p) for p in parts)
        if not syntagme or not relation:
            issues.append((lineno, "champ vide", line))
            continue
        entries.append({"lineno": lineno, "syntagme": syntagme, "relation": relation})
    return entries, issues


# ---------------------------------------------------------------------------
# Découpage A / B et définitude
# ---------------------------------------------------------------------------

def definiteness(prep, b_raw):
    """Applique les règles de la section 4.4.2. Renvoie (B, det, definitude, remarque)."""
    p = norm(prep)
    remark = ""
    if p in ("de la", "de l'", "du", "des"):
        det, definite = "Det", True
        b = b_raw
    else:  # « de » ou « d' »
        m = INDEF_RE.match(b_raw)
        if m:
            # d'un / d'une : déterminant présent mais indéfini.
            det, definite = "Det", False
            b = b_raw[m.end():]
        else:
            det, definite = "NoDet", False
            b = b_raw
            if OTHER_DET_RE.match(b_raw):
                remark = f"déterminant non couvert par les règles : « {b_raw.split()[0]} »"
    b = b.strip()
    # Entité nommée : Def forcé même en NoDet.
    if b[:1].isupper():
        definite = True
    return b, det, "Def" if definite else "NoDef", remark


def split_candidates(syntagme):
    """Tous les découpages possibles, un par préposition trouvée."""
    candidates = []
    for m in PREP_RE.finditer(syntagme):
        a = syntagme[:m.start()].strip()
        b_raw = syntagme[m.end():].strip()
        if not a or not b_raw:
            continue
        b, det, definite, remark = definiteness(m.group("prep"), b_raw)
        if not b:
            continue
        candidates.append({
            "A": a, "B": b, "prep": re.sub(r"\s+", " ", m.group("prep")).strip(),
            "det": det, "definitude": definite, "remarque": remark,
        })
    return candidates


# ---------------------------------------------------------------------------
# Traitement principal
# ---------------------------------------------------------------------------

def process_file(path):
    entries, issues = parse_file(path)
    rows = []
    for e in entries:
        # Le split suit la position physique de la ligne, pas l'indice après filtrage.
        split = "train" if e["lineno"] <= TRAIN_SIZE else "test"
        cands = split_candidates(e["syntagme"])
        row = {
            "syntagme": e["syntagme"], "relation": e["relation"], "split": split,
            "lineno": e["lineno"], "candidats": cands,
            "A": "", "B": "", "det": "", "definitude": "", "ambigu": "non",
        }
        if not cands:
            issues.append((e["lineno"], "aucune préposition de séparation trouvée", e["syntagme"]))
        elif len(cands) == 1:
            c = cands[0]
            row.update(A=c["A"], B=c["B"], det=c["det"], definitude=c["definitude"])
            if c["remarque"]:
                issues.append((e["lineno"], c["remarque"], e["syntagme"]))
        else:
            row["ambigu"] = "oui"
        rows.append(row)
    return rows, issues


def fmt_candidates(cands):
    return " | ".join(f"{c['A']} / {c['B']}" for c in cands)


def write_clean(clean_dir, name, rows):
    with open(clean_dir / f"{name}.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["syntagme", "A", "B", "relation", "split", "det", "definitude", "ambigu", "candidats"])
        for r in rows:
            w.writerow([r["syntagme"], r["A"], r["B"], r["relation"], r["split"],
                        r["det"], r["definitude"], r["ambigu"],
                        fmt_candidates(r["candidats"]) if r["ambigu"] == "oui" else ""])


def write_terms(clean_dir, all_rows):
    # Clé = (forme originale, rôle) : aucune fusion morphologique ni de casse.
    firm = Counter()
    ambiguous = Counter()
    relations = defaultdict(set)
    for r in all_rows:
        if r["ambigu"] == "non" and r["A"]:
            for term, role in ((r["A"], "A"), (r["B"], "B")):
                firm[(term, role)] += 1
                relations[(term, role)].add(r["relation"])
        elif r["ambigu"] == "oui":
            for c in r["candidats"]:
                for term, role in ((c["A"], "A"), (c["B"], "B")):
                    ambiguous[(term, role)] += 1
                    relations[(term, role)].add(r["relation"])
    keys = sorted(set(firm) | set(ambiguous), key=lambda k: (norm(k[0]), k[0], k[1]))
    with open(clean_dir / "termes.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["terme", "role", "relations_associees", "nb_occurrences", "nb_candidats_ambigus"])
        for k in keys:
            w.writerow([k[0], k[1], "|".join(sorted(relations[k])), firm[k], ambiguous[k]])
    return len(keys), sum(1 for k in keys if firm[k] == 0)


# ---------------------------------------------------------------------------
# Rapport
# ---------------------------------------------------------------------------

def md_escape(text):
    return str(text).replace("|", "\\|")


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(md_escape(c) for c in row) + " |" for row in rows]
    return out


def build_report(files, n_terms, n_terms_only_ambiguous, source):
    L = ["# Rapport de contrôle du corpus", "",
         f"Généré par `src/corpus_check.py` sur `{source}/`. Rien n'a été supprimé ni modifié dans "
         f"`{source}/` : ce rapport signale, les décisions restent manuelles.", ""]
    all_rows = [r for f in files for r in f["rows"]]

    # --- Comptes -----------------------------------------------------------
    L += ["## 1. Comptes par fichier", ""]
    body = []
    for f in files:
        rows = f["rows"]
        labels = sorted({r["relation"] for r in rows})
        n_train = sum(r["split"] == "train" for r in rows)
        n_amb = sum(r["ambigu"] == "oui" for r in rows)
        status = "OK" if f["n_lines"] == EXPECTED_LINES and not f["issues"] and len(labels) == 1 else "À VÉRIFIER"
        body.append([f["name"], ", ".join(labels), f["n_lines"], len(rows), n_train,
                     len(rows) - n_train, n_amb, len(f["issues"]), status])
    L += table(["fichier", "relation", "lignes", "parsées", "train", "test", "ambiguës", "anomalies", "statut"], body)
    L += ["", f"Total : {len(all_rows)} syntagmes parsés sur {sum(f['n_lines'] for f in files)} lignes.", ""]

    # --- Anomalies ---------------------------------------------------------
    L += ["## 2. Lignes malformées et anomalies", ""]
    anomalies = [[f["name"], ln, msg, f"`{txt}`"] for f in files for ln, msg, txt in f["issues"]]
    for f in files:
        labels = Counter(r["relation"] for r in f["rows"])
        if len(labels) > 1:
            anomalies.append([f["name"], "-", "plusieurs étiquettes de relation", ", ".join(f"{k} ({v})" for k, v in sorted(labels.items()))])
    L += table(["fichier", "ligne", "problème", "contenu"], anomalies) if anomalies else ["Aucune."]
    L += [""]

    # --- Ambiguïtés --------------------------------------------------------
    amb = [(f["name"], r) for f in files for r in f["rows"] if r["ambigu"] == "oui"]
    L += ["## 3. Cas ambigus (plusieurs prépositions)", "",
          "Non tranchés ici : résolution via la base de connaissances à l'étape 2 (papier, §4.1). "
          "Ces lignes ont A, B, det et definitude vides dans les CSV nettoyés ; les candidats sont "
          "dans la colonne `candidats`.", ""]
    if amb:
        body = []
        for name, r in amb:
            cands = "<br>".join(f"A=`{c['A']}` · B=`{c['B']}` ({c['prep']}; {c['det']}+{c['definitude']})" for c in r["candidats"])
            body.append([name, r["lineno"], r["split"], f"**{r['syntagme']}**", cands])
        L += table(["fichier", "ligne", "split", "syntagme", "découpages candidats"], body)
    else:
        L += ["Aucun."]
    L += [""]

    # --- Doublons intra-fichier -------------------------------------------
    L += ["## 4. Doublons exacts intra-fichier", ""]
    body = []
    for f in files:
        pos = defaultdict(list)
        for r in f["rows"]:
            pos[r["syntagme"]].append(r)
        for s, rs in pos.items():
            if len(rs) > 1:
                body.append([f["name"], f"`{s}`", ", ".join(f"{r['lineno']} ({r['split']})" for r in rs)])
    L += table(["fichier", "syntagme", "lignes"], body) if body else ["Aucun."]
    L += [""]

    # --- Doublons inter-fichiers ------------------------------------------
    L += ["## 5. Doublons inter-fichiers (classification multiple)", "",
          "Même syntagme (après normalisation casse/espaces/NFC) présent dans plusieurs types. "
          "À arbitrer manuellement ; rien n'est supprimé.", ""]
    by_norm = defaultdict(list)
    for f in files:
        for r in f["rows"]:
            by_norm[norm(r["syntagme"])].append((f["name"], r))
    body = []
    for key in sorted(by_norm):
        occ = by_norm[key]
        if len({name for name, _ in occ}) > 1:
            body.append([f"`{occ[0][1]['syntagme']}`",
                         "<br>".join(f"{name} l.{r['lineno']} ({r['split']})" for name, r in occ)])
    L += table(["syntagme", "occurrences"], body) if body else ["Aucun."]
    L += [""]

    # --- Doublons de paires (A, B) ----------------------------------------
    L += ["## 6. Doublons de la paire (A, B) normalisée", "",
          "Paires identiques après normalisation (minuscules, NFC, espaces, apostrophes), "
          "que le syntagme de surface soit identique ou non. Les lignes ambiguës sont exclues. "
          "Une même paire avec des déterminants différents dans deux types (ex. « photo de famille » "
          "vs « photo d'une famille ») est précisément le cas que le trait de définitude doit séparer.", ""]
    by_pair = defaultdict(list)
    for f in files:
        for r in f["rows"]:
            if r["ambigu"] == "non" and r["A"]:
                by_pair[(norm(r["A"]), norm(r["B"]))].append((f["name"], r))
    body = []
    for key in sorted(by_pair):
        occ = by_pair[key]
        if len(occ) > 1:
            same_surface = len({norm(r["syntagme"]) for _, r in occ}) == 1
            same_type = len({name for name, _ in occ}) == 1
            kind = ("même syntagme" if same_surface else "surfaces différentes") + (", même type" if same_type else ", types différents")
            body.append([f"{key[0]} / {key[1]}", kind,
                         "<br>".join(f"`{r['syntagme']}` — {name} l.{r['lineno']} ({r['split']}, {r['det']}+{r['definitude']})" for name, r in occ)])
    L += table(["paire A / B", "nature", "occurrences"], body) if body else ["Aucun."]
    L += [""]

    # --- Répétitions / diversité ------------------------------------------
    L += ["## 7. Diversité lexicale par type", "",
          f"Nombre de termes A et B distincts (formes normalisées, lignes non ambiguës) et termes "
          f"apparaissant au moins {REPETITION_THRESHOLD} fois dans un même type.", ""]
    body = []
    for f in files:
        rows = [r for r in f["rows"] if r["ambigu"] == "non" and r["A"]]
        ca = Counter(norm(r["A"]) for r in rows)
        cb = Counter(norm(r["B"]) for r in rows)
        rep_a = ", ".join(f"{t} ({n})" for t, n in sorted(ca.items(), key=lambda x: (-x[1], x[0])) if n >= REPETITION_THRESHOLD)
        rep_b = ", ".join(f"{t} ({n})" for t, n in sorted(cb.items(), key=lambda x: (-x[1], x[0])) if n >= REPETITION_THRESHOLD)
        dup_a = sum(1 for n in ca.values() if n >= 2)
        dup_b = sum(1 for n in cb.values() if n >= 2)
        body.append([f["name"], len(rows), len(ca), len(cb), dup_a, dup_b, rep_a or "—", rep_b or "—"])
    L += table(["fichier", "n", "A distincts", "B distincts", "A vus ≥2 fois", "B vus ≥2 fois", f"A répétés (≥{REPETITION_THRESHOLD})", f"B répétés (≥{REPETITION_THRESHOLD})"], body)
    L += [""]

    # --- Définitude --------------------------------------------------------
    L += ["## 8. Répartition des traits de définitude par type", "",
          "Règles (§4.4.2) : Det = du, de la, de l', des, d'un, d'une ; NoDet = de, d' ; "
          "Def = déterminant défini ; NoDef = absence de déterminant ou indéfini ; "
          "B à majuscule initiale (entité nommée) ⇒ Def forcé. Lignes ambiguës exclues.", ""]
    combos = ["Det+Def", "Det+NoDef", "NoDet+Def", "NoDet+NoDef"]
    body = []
    totals = Counter()
    for f in files:
        c = Counter(f"{r['det']}+{r['definitude']}" for r in f["rows"] if r["ambigu"] == "non" and r["A"])
        totals.update(c)
        body.append([f["name"]] + [c[k] for k in combos])
    body.append(["**total**"] + [f"**{totals[k]}**" for k in combos])
    L += table(["fichier"] + combos, body)
    L += ["", "Contrôle des exemples du papier :", ""]
    for s, expected in (("chat du rabbin", "Det+Def"), ("écran de cinéma", "NoDet+NoDef"), ("tableau de Chagall", "NoDet+Def")):
        c = split_candidates(s)[0]
        got = f"{c['det']}+{c['definitude']}"
        L.append(f"- {s} → {got} ({'OK' if got == expected else 'ÉCHEC, attendu ' + expected})")
    L += [""]

    # --- Termes ------------------------------------------------------------
    L += ["## 9. Fichier des termes", "",
          f"`data/corpus/clean/termes.csv` : {n_terms} couples (terme, rôle) distincts, formes originales "
          f"conservées. `nb_occurrences` compte les lignes non ambiguës ; `nb_candidats_ambigus` compte "
          f"les apparitions comme candidat d'une ligne ambiguë. {n_terms_only_ambiguous} terme(s) "
          f"n'existent que comme candidats.", ""]
    return "\n".join(L)


def rel(path):
    try:
        return path.relative_to(ROOT)
    except ValueError:
        return path


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--raw", type=Path, default=RAW_DIR, help="dossier des CSV source")
    parser.add_argument("--clean", type=Path, default=CLEAN_DIR, help="dossier des CSV nettoyés")
    parser.add_argument("--report", type=Path, default=REPORT_PATH, help="chemin du rapport Markdown")
    args = parser.parse_args()
    raw_dir, clean_dir, report_path = (p.resolve() for p in (args.raw, args.clean, args.report))
    if clean_dir == raw_dir:
        parser.error("--clean doit différer de --raw (les sources ne sont jamais réécrites)")
    clean_dir.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    files = []
    for path in sorted(raw_dir.glob("*.csv")):
        rows, issues = process_file(path)
        n_lines = len(path.read_bytes().splitlines())
        if n_lines != EXPECTED_LINES:
            issues.insert(0, ("-", f"{n_lines} lignes au lieu de {EXPECTED_LINES}", ""))
        files.append({"name": path.stem, "rows": rows, "issues": issues, "n_lines": n_lines})
        write_clean(clean_dir, path.stem, rows)
    all_rows = [r for f in files for r in f["rows"]]
    n_terms, n_only_amb = write_terms(clean_dir, all_rows)
    report_path.write_text(build_report(files, n_terms, n_only_amb, rel(raw_dir)) + "\n", encoding="utf-8")
    n_amb = sum(r["ambigu"] == "oui" for r in all_rows)
    n_issues = sum(len(f["issues"]) for f in files)
    print(f"{len(files)} fichiers, {len(all_rows)} syntagmes, {n_amb} ambigus, {n_issues} anomalies.")
    print(f"Rapport : {rel(report_path)}")


if __name__ == "__main__":
    main()
