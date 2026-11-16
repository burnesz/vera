#!/usr/bin/env python3
"""
Congela o gabarito de recuperação e os diálogos de Query Rewriting (RN-AVAL02).

Marca `congelado: true`, registra a data e imprime o SHA-256 de cada arquivo. Os scripts de
avaliação gravam esse hash no manifest de cada rodada; depois de congelar, faça commit dos
arquivos e não os edite mais durante a rodada oficial.

    ./.venv/bin/python scripts/freeze_gold.py
"""

import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from evaluation import retrieval_experiment as rx  # noqa: E402


def main():
    for path in (rx.GOLD_PATH, rx.DIALOGS_PATH):
        data = rx.load_json(path)
        if data.get("congelado"):
            print(f"Já congelado: {os.path.relpath(path, rx.ROOT)} (sha256 {rx.file_sha256(path)})")
            continue
        data["congelado"] = True
        data["data_congelamento"] = date.today().isoformat()
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        print(f"Congelado: {os.path.relpath(path, rx.ROOT)} (sha256 {rx.file_sha256(path)})")


if __name__ == "__main__":
    main()
