import contextlib
import io
import logging
import os
import sys
import tempfile

import pytest
import yaml


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))


from translator import main as translator_main
from simulator_cli import main as machine_main


def run_translator(source_file: str, target_file: str, data_file: str) -> str:
    argv_backup = sys.argv
    sys.argv = [
        "translator.py",
        source_file,
        target_file,
        "--data", data_file,
    ]
    try:
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            translator_main()
    finally:
        sys.argv = argv_backup
    return stdout.getvalue()


def run_machine(
    target_file: str,
    data_file: str,
    input_file: str | None,
    head: int | None = None,
    trace: bool = False,
    verbose: bool = False,
) -> tuple[str, str]:
    argv_backup = sys.argv
    sys.argv = [
        "simulator_cli.py",
        target_file,
        "--data", data_file,
        "--data-mem-size", "65536",
        "--tick-limit", "10000000",
    ]
    if input_file:
        sys.argv += ["--input", input_file]
    if head is not None:
        sys.argv += ["--head", str(head)]
    if trace:
        sys.argv += ["--trace"]
    if verbose:
        sys.argv += ["--verbose"]

    try:
        with (
            contextlib.redirect_stdout(io.StringIO()) as stdout,
            contextlib.redirect_stderr(io.StringIO()) as stderr,
        ):
            machine_main()
    finally:
        sys.argv = argv_backup

    return stdout.getvalue(), stderr.getvalue()


@pytest.mark.golden_test("*.yml")
def test_golden(golden, caplog):
    caplog.set_level(logging.DEBUG)

    with tempfile.TemporaryDirectory() as tmpdir:
        source_file = os.path.join(tmpdir, "source.fth")
        target_file = os.path.join(tmpdir, "target.bin")
        data_file = os.path.join(tmpdir, "target.data")
        input_file = os.path.join(tmpdir, "input.yaml")

        with open(source_file, "w", encoding="utf-8") as f:
            f.write(golden["source"])
        
        has_input = bool(golden.get("input"))
        if has_input:
            with open(input_file, "w", encoding="utf-8") as f:
                yaml.dump(golden["input"], f, allow_unicode=True)
        
        translator_output = run_translator(source_file, target_file, data_file)

        head = golden.get("head", None)
        trace = golden.get("trace", False)
        verbose = golden.get("verbose", False)

        machine_output, machine_err = run_machine(
            target_file, data_file,
            input_file if has_input else None,
            head=head,
            trace=trace,
            verbose=verbose,
        )

        log_lines = caplog.text.splitlines()
        if len(log_lines) > 400:
            log_text = "\n".join([*log_lines[:200], "...", *log_lines[-200:]])
        else:
            log_text = "\n".join(log_lines)
        
        assert golden.out["translator_output"] == translator_output
        assert golden.out["machine_output"] == machine_output
        assert golden.out["machine_err"] == machine_err
        assert golden.out["log"] == log_text
