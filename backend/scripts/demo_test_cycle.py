"""Ensaio local de falha/correção. Não representa revisão humana nem defeito real."""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    backend = Path(__file__).resolve().parents[1]
    source = backend / "tests/test_scrum_ementa_bdd.py"
    original = source.read_text(encoding="utf-8")
    implementation = (backend / "app/ementa.py").read_text(encoding="utf-8")
    correct = "(self.case, self.question, self.reasoning, self.ruling)"
    broken = "(self.question, self.case, self.reasoning, self.ruling)"
    if implementation.count(correct) != 1:
        raise RuntimeError("A classe mudou; revisar o ensaio.")

    with tempfile.TemporaryDirectory(prefix="case-law-demo-") as directory:
        sandbox = Path(directory)
        shutil.copytree(backend / "app", sandbox / "app")
        target = sandbox / "app/ementa.py"
        target.write_text(implementation.replace(correct, broken), encoding="utf-8")
        rehearsal = sandbox / "test_rehearsal.py"
        rehearsal.write_text(original, encoding="utf-8")
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-c",
            str(backend / "pyproject.toml"),
            str(rehearsal),
            "-o",
            f"pythonpath={sandbox}",
            "-m",
            "unit",
            "-q",
        ]
        print(
            "ENSAIO: ordem das seções trocada na CLASSE temporária; esperamos quatro falhas.",
            flush=True,
        )
        failed = subprocess.run(command, cwd=backend, check=False).returncode
        if failed != 1:
            print(f"Ensaio inconclusivo: código {failed}; esperado 1.")
            return 1

        target.write_text(implementation, encoding="utf-8")
        shutil.rmtree(sandbox / "app/__pycache__", ignore_errors=True)
        print("CORREÇÃO: ordem original restaurada na CLASSE temporária.", flush=True)
        corrected = subprocess.run(command, cwd=backend, check=False).returncode
        if corrected != 0:
            return corrected

    print(
        "Ensaio concluído: falhou, foi corrigido e passou; arquivos do projeto intactos."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
