from __future__ import annotations

from academic_pe.evaluation import run_core15_benchmark


if __name__ == "__main__":
    print(run_core15_benchmark().model_dump_json(indent=2))
