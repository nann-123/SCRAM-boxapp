from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

from app.config_binding.config_model import ConfigModel
from app.services import deployment_paths


CASE_PRESETS = {
    "tutorial_minimal": {"with_coag": 1, "with_cond": 0, "with_nucl": 0, "duration_hours": 0.25},
    "coag_only": {"with_coag": 1, "with_cond": 0, "with_nucl": 0, "duration_hours": 0.5},
    "coag_cond": {"with_coag": 1, "with_cond": 1, "with_nucl": 0, "duration_hours": 0.5},
    "coag_cond_nucl": {"with_coag": 1, "with_cond": 1, "with_nucl": 1, "duration_hours": 0.5},
    "baseline12h": {"with_coag": 1, "with_cond": 1, "with_nucl": 1, "duration_hours": 12.0},
    "gmd_hazy_condensation": {"with_coag": 0, "with_cond": 1, "with_nucl": 0, "duration_hours": 12.0},
    "gmd_hazy_coag_cond": {"with_coag": 1, "with_cond": 1, "with_nucl": 0, "duration_hours": 12.0},
    "gmd_paris_emission_only": {"with_coag": 0, "with_cond": 0, "with_nucl": 0, "duration_hours": 12.0},
    "gmd_paris_coagulation": {"with_coag": 1, "with_cond": 0, "with_nucl": 0, "duration_hours": 12.0},
    "gmd_paris_condensation": {"with_coag": 0, "with_cond": 1, "with_nucl": 0, "duration_hours": 12.0},
    "gmd_paris_full": {"with_coag": 1, "with_cond": 1, "with_nucl": 1, "duration_hours": 12.0},
}


MIXING_ASSUMPTIONS = ("INTERNAL_MIXING", "EXTERNAL_MIXING")
RUNTIME_VERSION_FILE = ".scram_runtime_version.json"
RUNTIME_HASH_SUFFIXES = {".f", ".f90", ".F90", ".c", ".h", ".inc", ".INC"}
RUNTIME_HASH_FILENAMES = {"SConstruct", "README", "README.md"}
RDB_CORE_MODE_MAP = {
    "legacy": 0,
    "core_conserv": 1,
    "core_nogrow": 2,
    "core_smallgrow": 3,
}


class RunService:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.config_model = ConfigModel(root)
        self.shared_runtime_root = deployment_paths.shared_runtime_root(root)
        self.shared_runtime_dir = deployment_paths.shared_runtime_platform_dir(root)
        self.runtime_dir = deployment_paths.runtime_platform_dir()
        self.runtime_config_dir = self.runtime_dir / "boxapp_cfg"
        self.results_root = deployment_paths.user_results_root()
        self.generated_root = deployment_paths.user_generated_configs_root()
        self._last_runtime_error = ""
        self._runtime_manifest: dict[str, Any] = {}
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self._stage_runtime_tree()
        self._runtime_manifest = self._runtime_signature(self.runtime_dir)
        self.results_root.mkdir(parents=True, exist_ok=True)
        self.generated_root.mkdir(parents=True, exist_ok=True)
        self.runtime_config_dir.mkdir(parents=True, exist_ok=True)
        (self.runtime_dir / "RESULT").mkdir(parents=True, exist_ok=True)
        self.current_process: subprocess.Popen[str] | None = None

    def set_results_root(self, results_root: Path) -> None:
        self.results_root = results_root
        self.results_root.mkdir(parents=True, exist_ok=True)

    def default_executable(self) -> Path:
        candidates = self._candidate_executables()
        for source, candidate in candidates:
            if self._is_compatible_executable(candidate):
                self._last_runtime_error = ""
                return candidate
            if source == "SCRAM_PROGRAMSCRAM":
                self._last_runtime_error = f"SCRAM_PROGRAMSCRAM points to an incompatible executable: {candidate}"
                raise RuntimeError(self._last_runtime_error)
        detail = "; ".join(f"{source}={path}" for source, path in candidates)
        self._last_runtime_error = f"No compatible ProgramSCRAM for platform {deployment_paths.platform_name()}; checked {detail}"
        raise RuntimeError(self._last_runtime_error)

    def executable_available(self) -> bool:
        try:
            executable = self.default_executable()
        except RuntimeError:
            return False
        return executable.exists() and self._is_compatible_executable(executable)

    def prepare_run(self, config_data: dict[str, Any], case_name: str, scheme: str, output_root: Path | None = None) -> dict[str, Any]:
        # Case preset provides suggested values to the GUI (via apply_case_preset),
        # but the user may override them.  Normalize without forcing preset values.
        data = self.config_model.normalize(config_data)
        data = self._with_mixing_assumption(data, scheme)
        # Apply case preset process switches and duration to the generated config.
        preset_name = data.get("case_preset", "")
        preset = CASE_PRESETS.get(preset_name) if preset_name else None
        if preset is not None:
            data = self._with_case_preset(data, preset)
        config_path = self.generated_root / f"{case_name}_{scheme.lower()}.cfg"
        runtime_config_relpath = self._runtime_config_relpath(case_name, scheme)
        runtime_config_path = self.runtime_dir / runtime_config_relpath
        self.config_model.serialize(data, config_path)
        self.config_model.serialize(data, runtime_config_path)
        run_root = (output_root or self.results_root) / "runs" / case_name / scheme.lower()
        (run_root / "csv").mkdir(parents=True, exist_ok=True)
        (run_root / "logs").mkdir(parents=True, exist_ok=True)
        log_path = run_root / "logs" / "run.log"
        env = os.environ.copy()
        env.update(
            {
                "SCRAM_RESULTS_DIR": str(run_root),
                "SCRAM_TESTCASE": case_name,
                "SCRAM_PROCESS_COMBO": case_name,
                "SCRAM_SCHEME_NAME": scheme.lower(),
                "SCRAM_COEFF_REPARTITION_MODE": self._coag_mapping_mode(scheme),
                "SCRAM_COEFF_CACHE_MODE": "ALWAYS_REBUILD",
                "SCRAM_RDB_CORE_CONSERV": str(self._rdb_core_mode(data)),
                "SCRAM_RDB_CORE_CONSERV_NAME": str(data["scalars"].get("redistribution_option", "core_conserv")),
            }
        )
        self._prepare_runtime_environment(env)
        executable = self.default_executable()
        runtime_manifest = self._runtime_signature(executable.parent, executable)
        return {
            "case_name": case_name,
            "scheme": scheme,
            "config_data": data,
            "config_path": config_path,
            "runtime_config_path": runtime_config_path,
            "runtime_config_relpath": runtime_config_relpath,
            "run_root": run_root,
            "log_path": log_path,
            "env": env,
            "command": [str(executable), runtime_config_relpath.as_posix()],
            "runtime_manifest": runtime_manifest,
            "total_sim_seconds": float(data["scalars"]["final_time_hours"]) * 3600.0,
        }

    def run_prepared(self, prepared: dict[str, Any], log_callback: Callable[[str], None] | None = None) -> dict[str, Any]:
        start = time.perf_counter()
        log_path = Path(prepared["log_path"])
        self._reset_runtime_outputs()
        with log_path.open("w") as handle:
            self._write_runtime_log_header(handle, prepared)
            self.current_process = subprocess.Popen(
                prepared["command"],
                cwd=self.runtime_dir,
                env=prepared["env"],
                stdout=handle,
                stderr=subprocess.STDOUT,
                text=True,
            )
            returncode = self.current_process.wait()
        self.current_process = None
        wallclock = time.perf_counter() - start
        self._collect_runtime_outputs(prepared, wallclock)
        result = self.summarize_run(Path(prepared["run_root"]))
        returncode = self._effective_returncode(returncode, prepared)
        result.update(
            {
                "case_name": prepared["case_name"],
                "scheme": prepared["scheme"],
                "status": "ok" if returncode == 0 else "failed",
                "wallclock": wallclock,
                "results_dir": str(prepared["run_root"]),
                "log_path": str(prepared["log_path"]),
                "config_path": str(prepared["config_path"]),
            }
        )
        if log_callback:
            log_callback(f"{prepared['case_name']} / {prepared['scheme']} finished with code {returncode}")
        return result

    def run_single(
        self,
        config_data: dict[str, Any],
        case_name: str,
        scheme: str,
        output_root: Path | None = None,
        log_callback: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        prepared = self.prepare_run(config_data, case_name, scheme, output_root=output_root)
        return self.run_prepared(prepared, log_callback=log_callback)

    def run_comparison(self, config_data: dict[str, Any], case_name: str, log_callback: Callable[[str], None] | None = None) -> list[dict[str, Any]]:
        rows = []
        for scheme in MIXING_ASSUMPTIONS:
            if log_callback:
                log_callback(f"Running {case_name} / {scheme}")
            rows.append(self.run_single(config_data, case_name, scheme, log_callback=log_callback))
        self.write_summaries(rows, output_root=self.results_root)
        return rows

    def run_batch_comparison(self, config_data: dict[str, Any], log_callback: Callable[[str], None] | None = None) -> list[dict[str, Any]]:
        rows = []
        for case_name in ("coag_only", "coag_cond", "coag_cond_nucl", "baseline12h"):
            for scheme in MIXING_ASSUMPTIONS:
                if log_callback:
                    log_callback(f"Running {case_name} / {scheme}")
                rows.append(self.run_single(config_data, case_name, scheme, log_callback=log_callback))
        self.write_summaries(rows, output_root=self.results_root)
        return rows

    def stop_current(self) -> bool:
        if self.current_process is None:
            return False
        self.current_process.terminate()
        return True

    def summarize_run(self, run_root: Path) -> dict[str, Any]:
        timestep_path = run_root / "csv" / "timestep_summary.csv"
        final_mass = float("nan")
        final_number = float("nan")
        total_steps = 0
        if timestep_path.exists():
            rows = list(csv.DictReader(timestep_path.open()))
            total_steps = len(rows)
            if rows:
                final_mass = float(rows[-1]["total_mass"])
                final_number = float(rows[-1]["total_number"])
        return {
            "final_mass": final_mass,
            "final_number": final_number,
            "total_steps": total_steps,
        }

    def read_live_metrics(self, run_root: Path, total_sim_seconds: float) -> dict[str, Any]:
        metrics = {
            "simulated_seconds": 0.0,
            "progress": 0,
            "eta_seconds": None,
            "current_total_mass": math.nan,
            "current_total_number": math.nan,
            "active_bins": 0,
            "active_pairs": 0,
            "average_diameter": math.nan,
            "last_output_time": "",
            "current_module": "",
            "latest_warning": "",
            "latest_file": "",
            "timestep": 0,
        }
        timestep_path = run_root / "csv" / "timestep_summary.csv"
        if timestep_path.exists():
            rows = list(csv.DictReader(timestep_path.open()))
            if rows:
                row = rows[-1]
                sim_seconds = float(row["time_seconds"])
                metrics["simulated_seconds"] = sim_seconds
                metrics["progress"] = max(0, min(100, int(100.0 * sim_seconds / max(total_sim_seconds, 1.0))))
                metrics["current_total_mass"] = float(row["total_mass"])
                metrics["current_total_number"] = float(row["total_number"])
                metrics["active_bins"] = int(float(row["active_bins"]))
                metrics["active_pairs"] = int(float(row["active_pairs"]))
                metrics["last_output_time"] = row["time_seconds"].strip()
                metrics["timestep"] = int(float(row["timestep"]))
        metrics["average_diameter"] = self._read_average_diameter(run_root, metrics["timestep"])
        metrics["current_module"], metrics["latest_warning"], metrics["latest_file"] = self._read_log_status(run_root)
        return metrics

    def write_summaries(self, rows: list[dict[str, Any]], output_root: Path | None = None) -> None:
        if not rows:
            return
        csv_root = output_root or self.results_root
        csv_root.mkdir(parents=True, exist_ok=True)
        perf_path = csv_root / "performance_summary.csv"
        with perf_path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        by_case: dict[str, dict[str, dict[str, Any]]] = {}
        for row in rows:
            by_case.setdefault(str(row["case_name"]), {})[str(row["scheme"])] = row
        final_rows = []
        for case_name, items in by_case.items():
            external = items.get("EXTERNAL_MIXING") or items.get("DETERMINISTIC_NEAREST")
            internal = items.get("INTERNAL_MIXING") or items.get("LEGACY")
            if not external or not internal:
                continue
            for scheme_name, row in items.items():
                final_rows.append(
                    {
                        "case_name": case_name,
                        "scheme": scheme_name,
                        "status": row["status"],
                        "final_total_mass": row["final_mass"],
                        "final_total_number": row["final_number"],
                        "relative_difference_vs_external_mass": (float(row["final_mass"]) - float(external["final_mass"]))
                        / max(abs(float(external["final_mass"])), 1.0e-20),
                        "relative_difference_vs_external_number": (float(row["final_number"]) - float(external["final_number"]))
                        / max(abs(float(external["final_number"])), 1.0e-20),
                        "relative_difference_vs_internal_mass": (float(row["final_mass"]) - float(internal["final_mass"]))
                        / max(abs(float(internal["final_mass"])), 1.0e-20),
                        "relative_difference_vs_internal_number": (float(row["final_number"]) - float(internal["final_number"]))
                        / max(abs(float(internal["final_number"])), 1.0e-20),
                    }
                )
        final_path = csv_root / "final_state_summary.csv"
        if final_rows:
            with final_path.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(final_rows[0].keys()))
                writer.writeheader()
                writer.writerows(final_rows)

    def _with_case_preset(self, config_data: dict[str, Any], preset: dict[str, float | int] | None) -> dict[str, Any]:
        data = self.config_model.normalize(config_data)
        if preset:
            data["scalars"]["with_coag"] = int(preset["with_coag"])
            data["scalars"]["with_cond"] = int(preset["with_cond"])
            data["scalars"]["with_nucl"] = int(preset["with_nucl"])
            data["scalars"]["final_time_hours"] = float(preset["duration_hours"])
        return data

    def _with_mixing_assumption(self, config_data: dict[str, Any], scheme: str) -> dict[str, Any]:
        data = self.config_model.normalize(config_data)
        normalized_scheme = scheme.upper()
        data["mixing_assumption"] = normalized_scheme
        data["mapping_scheme"] = "DETERMINISTIC_NEAREST"
        if normalized_scheme == "INTERNAL_MIXING":
            data["scalars"]["tag_external"] = 0
            data["scalars"]["n_frac"] = 1
            data["scalars"]["kind_composition"] = 0
            data["fraction_bounds"] = [0.0, 1.0]
        elif normalized_scheme == "EXTERNAL_MIXING":
            data["scalars"]["n_frac"] = max(int(data["scalars"].get("n_frac", 3)), 3)
            if len(data.get("fraction_bounds", [])) != int(data["scalars"]["n_frac"]) + 1:
                data["fraction_bounds"] = [0.0, 0.2, 0.8, 1.0]
                data["scalars"]["n_frac"] = 3
            data["scalars"]["kind_composition"] = 0
            # The Greater Paris paper scenarios initialise the background aerosol
            # as internally mixed, then allow emitted particles and dynamics to
            # create externally resolved mixing states.
            data["scalars"]["tag_external"] = int(data["scalars"].get("tag_external", 0))
        return self.config_model.normalize(data)

    def _coag_mapping_mode(self, scheme: str) -> str:
        if scheme.upper() == "LEGACY":
            return "LEGACY"
        return "COAG_TARGET_NEAREST"

    def _rdb_core_mode(self, data: dict[str, Any]) -> int:
        option = str(data.get("scalars", {}).get("redistribution_option", "core_conserv")).strip().lower()
        return RDB_CORE_MODE_MAP.get(option, 1)

    def _read_average_diameter(self, run_root: Path, timestep: int) -> float:
        path = run_root / "csv" / "size_distribution_number.csv"
        if not path.exists():
            return math.nan
        numer = 0.0
        denom = 0.0
        with path.open() as handle:
            for row in csv.DictReader(handle):
                if int(float(row["timestep"])) != timestep:
                    continue
                diameter = float(row["representative_diameter"])
                number = float(row["number"])
                numer += diameter * number
                denom += number
        return numer / denom if denom > 0.0 else math.nan

    def _read_log_status(self, run_root: Path) -> tuple[str, str, str]:
        log_path = run_root / "logs" / "run.log"
        if not log_path.exists():
            return "", "", ""
        lines = [line.strip() for line in log_path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()]
        if not lines:
            return "", "", ""
        current_module = lines[-1]
        warning = ""
        latest_file = ""
        for line in reversed(lines):
            if not warning and ("warning" in line.lower() or "error" in line.lower()):
                warning = line
            if not latest_file and (".csv" in line.lower() or ".txt" in line.lower()):
                latest_file = line
            if warning and latest_file:
                break
        return current_module, warning, latest_file

    def _candidate_executables(self) -> list[tuple[str, Path]]:
        exe_name = "ProgramSCRAM.exe" if os.name == "nt" else "ProgramSCRAM"
        candidates: list[tuple[str, Path]] = []
        env_path = os.environ.get("SCRAM_PROGRAMSCRAM")
        if env_path:
            candidates.append(("SCRAM_PROGRAMSCRAM", Path(env_path).expanduser()))
        candidates.append(("staged_runtime", self.runtime_dir / exe_name))
        if self.shared_runtime_dir.exists():
            candidates.append(("shared_platform_runtime", self.shared_runtime_dir / exe_name))
        unique: list[tuple[str, Path]] = []
        seen: set[str] = set()
        for source, candidate in candidates:
            key = str(candidate)
            if key in seen:
                continue
            seen.add(key)
            unique.append((source, candidate))
        return unique

    def _stage_runtime_tree(self) -> None:
        if not self.shared_runtime_dir.exists():
            self._last_runtime_error = f"Shared platform runtime is missing: {self.shared_runtime_dir}"
            return
        shared_manifest = self._runtime_signature(self.shared_runtime_dir)
        installed_manifest = self._read_runtime_manifest(self.runtime_dir / RUNTIME_VERSION_FILE)
        installed_exe = self.runtime_dir / ("ProgramSCRAM.exe" if os.name == "nt" else "ProgramSCRAM")
        if installed_manifest == shared_manifest and self._is_compatible_executable(installed_exe):
            return
        if self.runtime_dir.exists():
            shutil.rmtree(self.runtime_dir)
        ignore = shutil.ignore_patterns(
            ".venv",
            "RESULT",
            "results",
            "__pycache__",
            "*.pyc",
            "*.o",
            "*.mod",
            "*.smod",
            ".sconsign.dblite",
            "manual_compile*.log",
        )
        shutil.copytree(self.shared_runtime_dir, self.runtime_dir, ignore=ignore)
        self._write_runtime_manifest(self.runtime_dir / RUNTIME_VERSION_FILE, shared_manifest)

    def _is_compatible_executable(self, path: Path) -> bool:
        if not path.exists() or not os.access(path, os.X_OK):
            return False
        if os.name == "nt":
            return path.suffix.lower() == ".exe"
        try:
            with path.open("rb") as handle:
                header = handle.read(20)
        except OSError:
            return False
        magic = header[:4]
        if sys.platform == "darwin":
            return magic in {b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca"}
        if magic != b"\x7fELF" or len(header) < 20:
            return False
        machine = int.from_bytes(header[18:20], "little")
        host = platform.machine().lower()
        if host in {"x86_64", "amd64"}:
            return machine == 62
        if host in {"aarch64", "arm64"}:
            return machine == 183
        return True

    def _runtime_signature(self, runtime_dir: Path, executable: Path | None = None) -> dict[str, Any]:
        exe_name = "ProgramSCRAM.exe" if os.name == "nt" else "ProgramSCRAM"
        exe_path = executable or runtime_dir / exe_name
        manifest = {
            "schema": 1,
            "platform": deployment_paths.platform_name(),
            "host_machine": platform.machine(),
            "runtime_dir": str(runtime_dir),
            "executable_name": exe_name,
            "executable_sha256": self._sha256_file(exe_path),
            "executable_size": exe_path.stat().st_size if exe_path.exists() else 0,
            "source_sha256": self._source_tree_hash(runtime_dir / "source" / "SCRAM1.1"),
        }
        manifest_path = runtime_dir / "runtime_manifest.json"
        if manifest_path.exists():
            manifest["declared_manifest_sha256"] = self._sha256_file(manifest_path)
        return manifest

    def _source_tree_hash(self, source_root: Path) -> str:
        if not source_root.exists():
            return ""
        digest = hashlib.sha256()
        for path in sorted(source_root.rglob("*")):
            if not path.is_file():
                continue
            if any(part in {".git", "__pycache__"} for part in path.parts):
                continue
            if path.suffix not in RUNTIME_HASH_SUFFIXES and path.name not in RUNTIME_HASH_FILENAMES:
                continue
            rel = path.relative_to(source_root).as_posix()
            digest.update(rel.encode("utf-8"))
            digest.update(b"\0")
            digest.update(self._sha256_file(path).encode("ascii"))
            digest.update(b"\0")
        return digest.hexdigest()

    def _sha256_file(self, path: Path) -> str:
        if not path.exists() or not path.is_file():
            return ""
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _read_runtime_manifest(self, path: Path) -> dict[str, Any] | None:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _write_runtime_manifest(self, path: Path, manifest: dict[str, Any]) -> None:
        path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _write_runtime_log_header(self, handle: Any, prepared: dict[str, Any]) -> None:
        header = {
            "command": prepared["command"],
            "cwd": str(self.runtime_dir),
            "runtime_manifest": prepared.get("runtime_manifest", {}),
            "mapping_mode": prepared["env"].get("SCRAM_COEFF_REPARTITION_MODE", ""),
            "cache_mode": prepared["env"].get("SCRAM_COEFF_CACHE_MODE", ""),
            "rdb_core_mode": prepared["env"].get("SCRAM_RDB_CORE_CONSERV", ""),
            "rdb_core_mode_name": prepared["env"].get("SCRAM_RDB_CORE_CONSERV_NAME", ""),
            "results_dir": prepared["env"].get("SCRAM_RESULTS_DIR", ""),
        }
        handle.write("# SCRAM BoxApp runtime metadata\n")
        handle.write(json.dumps(header, indent=2, sort_keys=True))
        handle.write("\n# ProgramSCRAM output\n")
        handle.flush()

    def _runtime_config_relpath(self, case_name: str, scheme: str) -> Path:
        safe_case = "".join(ch.lower() if ch.isalnum() else "_" for ch in case_name)[:16].strip("_") or "case"
        upper_scheme = scheme.upper()
        if upper_scheme == "INTERNAL_MIXING":
            safe_scheme = "internal"
        elif upper_scheme == "EXTERNAL_MIXING":
            safe_scheme = "external"
        else:
            safe_scheme = "n" if "NEAREST" in upper_scheme else "l"
        return Path("boxapp_cfg") / f"{safe_case}_{safe_scheme}.cfg"

    def _prepare_runtime_environment(self, env: dict[str, str]) -> None:
        if not sys.platform.startswith("linux"):
            return
        candidates = [Path("/lib/x86_64-linux-gnu"), Path("/usr/lib/x86_64-linux-gnu"), Path("/lib64")]
        entries = [str(path) for path in candidates if path.exists()]
        if not entries:
            return
        existing = env.get("LD_LIBRARY_PATH", "")
        if existing:
            entries.append(existing)
        env["LD_LIBRARY_PATH"] = ":".join(entries)

    _FATAL_LOG_PATTERNS: list[str] = [
        "non conservation",
        "negatif",
        "IEEE_INVALID_FLAG",
        "IEEE_DIVIDE_BY_ZERO",
        "STOP",
    ]

    def _effective_returncode(self, raw_returncode: int, prepared: dict[str, Any]) -> int:
        if raw_returncode != 0:
            return raw_returncode
        log_path = Path(prepared.get("log_path", ""))
        if not log_path.exists():
            return raw_returncode
        try:
            text = log_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return raw_returncode
        lower = text.lower()
        for pattern in self._FATAL_LOG_PATTERNS:
            if pattern.lower() in lower:
                return -1
        return raw_returncode

    def _reset_runtime_outputs(self) -> None:
        result_dir = self.runtime_dir / "RESULT"
        for path in result_dir.iterdir():
            if path.is_file():
                path.unlink()

    def _collect_runtime_outputs(self, prepared: dict[str, Any], wallclock: float) -> None:
        run_root = Path(prepared["run_root"])
        csv_root = run_root / "csv"
        csv_root.mkdir(parents=True, exist_ok=True)
        result_dir = self.runtime_dir / "RESULT"
        report_path = result_dir / "report.txt"
        if report_path.exists():
            shutil.copy2(report_path, run_root / "logs" / "report.txt")
        timestep_path = csv_root / "timestep_summary.csv"
        if timestep_path.exists():
            return
        mass_pairs = self._read_scalar_pairs(result_dir / "mass_result_sbin.txt")
        number_pairs = self._read_scalar_pairs(result_dir / "number_result_sbin.txt")
        if not mass_pairs or not number_pairs:
            return
        total_mass = sum(value for _, value in mass_pairs)
        total_number = sum(value for _, value in number_pairs)
        active_bins = sum(1 for _, value in number_pairs if value > 0.0)
        total_sim_seconds = float(prepared["total_sim_seconds"])
        scheme = str(prepared["scheme"])
        case_name = str(prepared["case_name"])
        config_data = prepared["config_data"]
        self._write_csv(
            timestep_path,
            [
                {
                    "timestep": 1,
                    "time_seconds": total_sim_seconds,
                    "total_mass": total_mass,
                    "total_number": total_number,
                    "active_bins": active_bins,
                    "active_pairs": 0,
                    "skipped_pairs": 0,
                    "mapping_mode": scheme,
                    "cache_status": "legacy_result_import",
                    "runtime_step": wallclock,
                    "testcase": case_name,
                    "process_combo": case_name,
                    "scheme": scheme,
                }
            ],
        )
        self._write_distribution_csv(
            csv_root / "size_distribution_number.csv",
            number_pairs,
            total_sim_seconds,
            case_name,
            scheme,
            "number",
            config_data,
        )
        self._write_distribution_csv(
            csv_root / "size_distribution_mass.csv",
            mass_pairs,
            total_sim_seconds,
            case_name,
            scheme,
            "mass",
            config_data,
        )
        species_rows = self._build_species_mass_rows(result_dir, config_data, total_sim_seconds, case_name, scheme)
        if species_rows:
            self._write_csv(csv_root / "species_mass_timeseries.csv", species_rows)

    def _read_scalar_pairs(self, path: Path) -> list[tuple[float, float]]:
        if not path.exists():
            return []
        pairs: list[tuple[float, float]] = []
        for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            parts = raw_line.split()
            if len(parts) < 2:
                continue
            try:
                pairs.append((float(parts[0]), float(parts[1])))
            except ValueError:
                continue
        return pairs

    def _write_distribution_csv(
        self,
        target: Path,
        pairs: list[tuple[float, float]],
        total_sim_seconds: float,
        case_name: str,
        scheme: str,
        kind: str,
        config_data: dict[str, Any],
    ) -> None:
        bounds = list(config_data.get("diameter_bounds", []))
        rows: list[dict[str, Any]] = []
        for index, (diameter, value) in enumerate(pairs, start=1):
            log_width = 1.0
            if len(bounds) > index:
                lower = float(bounds[index - 1])
                upper = float(bounds[index])
                if lower > 0.0 and upper > lower:
                    log_width = math.log10(upper / lower)
            row = {
                "timestep": 1,
                "time_seconds": total_sim_seconds,
                "size_bin": index,
                "representative_diameter": diameter,
                kind: value,
                f"d{'N' if kind == 'number' else 'M'}_dlogD": value / max(log_width, 1.0e-12),
                "testcase": case_name,
                "process_combo": case_name,
                "scheme": scheme,
            }
            rows.append(row)
        self._write_csv(target, rows)

    def _build_species_mass_rows(
        self,
        result_dir: Path,
        config_data: dict[str, Any],
        total_sim_seconds: float,
        case_name: str,
        scheme: str,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for index, record in enumerate(config_data.get("species_records", []), start=1):
            species_path = result_dir / f"mass_result_s{index}.txt"
            pairs = self._read_scalar_pairs(species_path)
            if not pairs:
                continue
            rows.append(
                {
                    "timestep": 1,
                    "time_seconds": total_sim_seconds,
                    "species_index": index,
                    "species_name": record.get("species_name", f"species_{index}"),
                    "total_mass": sum(value for _, value in pairs),
                    "testcase": case_name,
                    "process_combo": case_name,
                    "scheme": scheme,
                }
            )
        return rows

    def _write_csv(self, path: Path, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
