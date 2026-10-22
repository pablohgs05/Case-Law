"""Ensaio local de falha/correção. Não representa revisão humana nem defeito real."""

import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    backend = Path(__file__).resolve().parents[1]
    source = backend / "tests/test_scrum_ementa_bdd.py"
    original = source.read_text(encoding="utf-8")
    assertion = 'assert rebuilt == text + "I." + text + "II." + text + "III." + text + "IV." + text'
    if original.count(assertion) != 1:
        raise RuntimeError("O teste mudou; atualize o ensaio antes de executar.")

    with tempfile.TemporaryDirectory(prefix="case-law-demo-") as directory:
        rehearsal = Path(directory) / "test_rehearsal.py"
        # Falha didática deliberada apenas na cópia temporária.
        rehearsal.write_text(
            original.replace(
                assertion, 'assert rebuilt == "EXPECTATIVA INCORRETA DO ENSAIO"'
            ),
            encoding="utf-8",
        )
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-c",
            str(backend / "pyproject.toml"),
            str(rehearsal),
            "-m",
            "unit",
            "-q",
        ]
        print("ENSAIO: expectativa incorreta; esperamos três falhas.", flush=True)
        failed = subprocess.run(command, cwd=backend, check=False).returncode
        if failed != 1:
            print(f"Ensaio inconclusivo: código {failed}; esperado 1.")
            return 1

        rehearsal.write_text(original, encoding="utf-8")
        print("CORREÇÃO: expectativa original restaurada na cópia.", flush=True)
        corrected = subprocess.run(command, cwd=backend, check=False).returncode
        if corrected != 0:
            return corrected

    print(
        "Ensaio concluído: falhou, foi corrigido e passou; arquivos do projeto intactos."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
