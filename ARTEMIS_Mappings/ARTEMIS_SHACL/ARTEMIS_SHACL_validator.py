"""
ARTEMIS SHACL Validator
=======================
Valida file Turtle usando i moduli SHACL ARTEMIS.

Modalità disponibili:
  - Separata (default): valida ogni file singolarmente
  - Unificata (--merge): fonde tutti i file in un unico grafo e valida una volta sola

Uso:
    python validate_artemis.py file1.ttl file2.ttl
    python validate_artemis.py BronzeTripod/*.ttl JapaneseTower/*.ttl
    python validate_artemis.py BronzeTripod/*.ttl JapaneseTower/*.ttl --merge
    python validate_artemis.py --all
    python validate_artemis.py --all --merge
    python validate_artemis.py file1.ttl --shacl analysis
    python validate_artemis.py file1.ttl --report report.txt
"""

import sys
import argparse
from pathlib import Path

try:
    from pyshacl import validate
    from rdflib import Graph
except ImportError:
    print("ERRORE: pySHACL non è installato. Esegui: pip install pyshacl")
    sys.exit(1)


# ╔══════════════════════════════════════════════════════════╗
# ║              CONFIGURAZIONE — MODIFICA QUI               ║
# ╚══════════════════════════════════════════════════════════╝

# Cartella in cui si trovano i file SHACL .ttl
SHACL_DIR = Path(".")

# Mappa nome-modulo → nome file SHACL
SHACL_MODULES = {
    "cultural_objects":   "ARTEMIS_SHACL_Heritage_Cultural_Objects.ttl",
    "analysis":           "ARTEMIS_SHACL_Heritage_Sciencee_Analyses.ttl",
    "services":           "ARTEMIS_SHACL_Digital_Services.ttl",
    "digital_operations": "ARTEMIS_SHACL_Digital_Operations.ttl",
}

# Cartella dei file Turtle da validare (usata solo con --all)
DATA_DIR = Path(".")

# ╚══════════════════════════════════════════════════════════╝


def load_shacl_graph(module_names):
    combined = Graph()
    for name in module_names:
        path = SHACL_DIR / SHACL_MODULES[name]
        if not path.exists():
            print(f"  [ATTENZIONE] File SHACL non trovato: {path}")
            continue
        combined.parse(str(path), format="turtle")
        print(f"  Caricato: {path.name}  ({len(combined)} triple totali)")
    return combined


def validate_single(data_path, shacl_graph, use_inference, violations_only):
    """Valida un singolo file Turtle."""
    conforms, _, results_text = validate(
        data_graph=str(data_path),
        shacl_graph=shacl_graph,
        data_graph_format="turtle",
        inference="rdfs" if use_inference else "none",
        abort_on_first=False,
        allow_warnings=True,
        meta_shacl=False,
        debug=False,
    )
    if violations_only:
        results_text = filter_violations(results_text)
    return conforms, results_text


def validate_merged(data_paths, shacl_graph, use_inference, violations_only):
    """Fonde tutti i file in un unico grafo e valida una volta sola."""
    merged = Graph()
    for path in data_paths:
        try:
            merged.parse(str(path), format="turtle")
        except Exception as e:
            print(f"  [ERRORE parsing] {path.name}: {e}")
    print(f"  Grafo unificato: {len(merged)} triple totali da {len(data_paths)} file")

    conforms, _, results_text = validate(
        data_graph=merged,
        shacl_graph=shacl_graph,
        inference="rdfs" if use_inference else "none",
        abort_on_first=False,
        allow_warnings=True,
        meta_shacl=False,
        debug=False,
    )
    if violations_only:
        results_text = filter_violations(results_text)
    return conforms, results_text


def filter_violations(results_text):
    lines = results_text.splitlines()
    filtered, in_block = [], False
    for line in lines:
        if "Constraint Violation" in line:
            in_block = True
        elif line.strip() == "" and in_block:
            in_block = False
            filtered.append("")
        if in_block or not filtered:
            filtered.append(line)
    return "\n".join(filtered)


def format_summary(label, conforms, results_text):
    violations = results_text.count("Constraint Violation")
    warnings   = results_text.count("sh:Warning")
    status     = "✅ CONFORME" if conforms else "❌ NON CONFORME"
    return f"{status}  |  {label}  |  Violazioni: {violations}  |  Warning: {warnings}"


def main():
    parser = argparse.ArgumentParser(
        description="Valida file Turtle con i moduli SHACL ARTEMIS."
    )
    parser.add_argument(
        "data_files", nargs="*",
        help="Uno o più file Turtle da validare"
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Valida tutti i file .ttl presenti in DATA_DIR"
    )
    parser.add_argument(
        "--merge", action="store_true",
        help=(
            "Modalità unificata: fonde tutti i file in un unico grafo "
            "prima di validare. Risolve i falsi positivi causati da URI "
            "condivisi tra file diversi (es. he_007 citato in analysis)."
        )
    )
    parser.add_argument(
        "--shacl", choices=list(SHACL_MODULES.keys()),
        help="Usa solo un modulo SHACL specifico (default: tutti)"
    )
    parser.add_argument(
        "--report", metavar="FILE",
        help="Salva il report completo su file di testo"
    )
    parser.add_argument(
        "--violations", action="store_true",
        help="Mostra solo le violazioni (severity Violation), ignora i Warning"
    )
    parser.add_argument(
        "--no-inference", action="store_true",
        help="Disabilita l'inferenza RDFS (più veloce)"
    )
    args = parser.parse_args()

    # Raccolta file
    if args.all:
        data_files = sorted(DATA_DIR.glob("*.ttl"))
    else:
        data_files = [Path(f) for f in args.data_files]

    data_files = [f for f in data_files if f.exists()]

    if not data_files:
        print("Nessun file da validare. Passa almeno un .ttl oppure usa --all.")
        sys.exit(1)

    module_names = [args.shacl] if args.shacl else list(SHACL_MODULES.keys())
    use_inference = not args.no_inference

    print("=" * 60)
    print("ARTEMIS SHACL Validator")
    print("=" * 60)
    print(f"Modalità    : {'UNIFICATA (--merge)' if args.merge else 'SEPARATA (default)'}")
    print(f"Moduli SHACL: {', '.join(module_names)}")
    print(f"Inferenza   : {'RDFS' if use_inference else 'nessuna'}")
    print(f"Filtro      : {'solo Violation' if args.violations else 'Violation + Warning'}")
    print(f"File        : {len(data_files)}")
    print()

    print("Caricamento moduli SHACL...")
    shacl_graph = load_shacl_graph(module_names)
    print()

    all_reports = []
    overall_conforms = True

    if args.merge:
        # ── Modalità unificata ────────────────────────────────
        print("Fusione dei file in un unico grafo...")
        conforms, report_text = validate_merged(
            data_files, shacl_graph, use_inference, args.violations
        )
        if not conforms:
            overall_conforms = False

        label = f"{len(data_files)} file unificati"
        summary = format_summary(label, conforms, report_text)
        print(f"\n  → {summary}")
        print()

        file_list = "\n".join(f"    - {f}" for f in data_files)
        all_reports.append(
            f"\n{'=' * 60}\n"
            f"Modalità: UNIFICATA\n"
            f"File inclusi:\n{file_list}\n"
            f"{summary}\n"
            f"{'=' * 60}\n"
            f"{report_text}\n"
        )

    else:
        # ── Modalità separata ─────────────────────────────────
        for data_path in data_files:
            print(f"Validazione: {data_path.name} ...")
            conforms, report_text = validate_single(
                data_path, shacl_graph, use_inference, args.violations
            )
            if not conforms:
                overall_conforms = False

            summary = format_summary(data_path.name, conforms, report_text)
            print(f"  → {summary}")
            all_reports.append(
                f"\n{'=' * 60}\n"
                f"File: {data_path}\n"
                f"{summary}\n"
                f"{'=' * 60}\n"
                f"{report_text}\n"
            )

    # Risultato finale
    print()
    print("=" * 60)
    esito = "✅ Tutti i file sono conformi" if overall_conforms else "❌ Trovate violazioni"
    print(f"RISULTATO FINALE: {esito}")
    print("=" * 60)

    if args.report:
        Path(args.report).write_text("\n".join(all_reports), encoding="utf-8")
        print(f"\nReport salvato in: {args.report}")

    for section in all_reports:
        print(section)

    sys.exit(0 if overall_conforms else 1)


if __name__ == "__main__":
    main()
