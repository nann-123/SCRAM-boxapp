from __future__ import annotations

import json
from copy import deepcopy
from math import sqrt
from pathlib import Path
from typing import Any


def _split_comment(line: str) -> tuple[str, str]:
    if "##" in line:
        head, tail = line.split("##", 1)
        return head.rstrip(), "##" + tail.strip()
    return line.rstrip(), ""


def _tokens(line: str) -> list[str]:
    return _split_comment(line)[0].split()


def _format_line(tokens: list[Any], comment: str = "") -> str:
    text = " ".join(str(token) for token in tokens).rstrip()
    return f"{text} {comment}".rstrip() if comment else text


def _parse_species_comment(comment: str) -> tuple[str, str]:
    body = comment.replace("##", "", 1).strip()
    if not body:
        return "", ""
    if ";" in body:
        name, notes = body.split(";", 1)
        return name.strip(), notes.strip()
    return body, ""


SUPPORTED_REDISTRIBUTION_OPTIONS = {"legacy", "core_conserv", "core_nogrow", "core_smallgrow"}
SUPPORTED_MIXING_ASSUMPTIONS = {"INTERNAL_MIXING", "EXTERNAL_MIXING"}


class ConfigModel:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.schema = json.loads((root / "core" / "schema" / "config_schema.json").read_text(encoding="utf-8"))
        self.default_path = root / "core" / "defaults" / "default_config.cfg"

    def default_lines(self) -> list[str]:
        return self.default_path.read_text(encoding="utf-8").splitlines()

    def parse(self, path: Path) -> dict[str, Any]:
        lines = path.read_text(encoding="utf-8").splitlines()
        data: dict[str, Any] = {
            "path": str(path),
            "raw_lines": lines,
            "scalars": {},
            "species_records": [],
            "init_bin_number": [],
            "init_bin_emission_species_1": [],
            "init_bin_emission_species_2": [],
            "emission_matrix": [],
            "diameter_bounds": [],
            "fraction_bounds": [],
            "mapping_scheme": "DETERMINISTIC_NEAREST",
            "mixing_assumption": "EXTERNAL_MIXING",
            "case_preset": "coag_only",
            "template_name": "tutorial_minimal",
        }
        for field in self.schema["scalar_fields"]:
            if isinstance(field["line_index"], int):
                token_list = _tokens(lines[field["line_index"]])
                value = token_list[field.get("subindex", 0)]
                data["scalars"][field["key"]] = self._coerce(value, field["type"])

        n_species = int(data["scalars"]["n_species"])
        n_sizebin = int(data["scalars"]["n_sizebin"])
        tag_init = int(data["scalars"]["tag_init"])
        species_start = 19
        for row in range(n_species):
            line = lines[species_start + row]
            tokens = _tokens(line)
            _, comment = _split_comment(line)
            species_name, notes = _parse_species_comment(comment)
            record = {
                "species_id": int(tokens[0]),
                "species_name": species_name or f"species_{row + 1}",
                "group_id": int(tokens[1]),
                "init_gas": float(tokens[2]),
                "emission": float(tokens[3]),
                "bin_values": [float(value) for value in tokens[4:4 + n_sizebin]] if tag_init == 1 else [float(tokens[4])],
                "notes": notes,
            }
            data["species_records"].append(record)

        after_species = species_start + n_species
        data["init_bin_number"] = [float(value) for value in _tokens(lines[after_species])]
        data["init_bin_emission_species_1"] = [float(value) for value in _tokens(lines[after_species + 1])]
        data["init_bin_emission_species_2"] = [float(value) for value in _tokens(lines[after_species + 2])]
        emission_matrix: list[list[float]] = []
        for idx in range(n_species):
            if idx == 0:
                emission_matrix.append(list(data["init_bin_emission_species_1"]))
            elif idx == 1:
                emission_matrix.append(list(data["init_bin_emission_species_2"]))
            else:
                emission_matrix.append([0.0] * n_sizebin)
        data["emission_matrix"] = emission_matrix
        diameter_line = after_species + 3
        data["diameter_bounds"] = [float(value) for value in _tokens(lines[diameter_line])]
        data["scalars"]["kind_composition"] = int(_tokens(lines[diameter_line + 1])[0])
        data["scalars"]["n_frac"] = int(_tokens(lines[diameter_line + 2])[0])
        data["scalars"].setdefault("redistribution_option", "core_conserv")
        data["fraction_bounds"] = [float(value) for value in _tokens(lines[diameter_line + 3])]
        return data

    def new_default(self) -> dict[str, Any]:
        return self.parse(self.default_path)

    def serialize(self, data: dict[str, Any], target: Path) -> Path:
        normalized = self.normalize(data)
        scalars = normalized["scalars"]
        lines = [
            _format_line([scalars["coefficient_file"]], "## repartition coefficient file"),
            _format_line([scalars["with_coag"]], "## coagulation switch"),
            _format_line([scalars["with_cond"]], "## condensation switch"),
            _format_line([scalars["with_nucl"], scalars["nucl_model"]], "## nucleation switch and model"),
            _format_line([scalars["sulfate_computation"]], "## sulfate condensation mode"),
            _format_line([scalars["dynamic_solver"], scalars["tag_thrm"]], "## dynamic solver and thermodynamic tag"),
            _format_line([scalars["redistribution_method"]], "## redistribution method"),
            _format_line([scalars["init_scenario"]], "## initial scenario"),
            _format_line([scalars["tag_external"]], "## external mixing tag"),
            _format_line([self._format_scalar(scalars["temperature"], "float")], "## temperature K"),
            _format_line([self._format_scalar(scalars["pressure"], "float")], "## pressure Pa"),
            _format_line([self._format_scalar(scalars["humidity"], "float")], "## relative humidity"),
            _format_line([scalars["tagrho"], self._format_scalar(scalars["fixed_density"], "float")], "## density mode and fixed density"),
            _format_line([self._format_scalar(scalars["final_time_hours"], "float")], "## simulation time hours"),
            _format_line([self._format_scalar(scalars["dtmin_seconds"], "float")], "## minimum time step seconds"),
            _format_line([self._format_scalar(scalars["cut_dim"], "float")], "## cut diameter flag"),
            _format_line([scalars["n_sizebin"], scalars["kind_grid"]], "## size sections and grid mode"),
            _format_line([scalars["n_groups"]], "## number of groups"),
            _format_line([scalars["n_species"], scalars["tag_init"]], "## number of species and initialization mode"),
        ]

        for idx, record in enumerate(normalized["species_records"]):
            comment = self._species_comment(record, idx)
            lines.append(
                _format_line(
                    [
                        record["species_id"],
                        record["group_id"],
                        self._format_scalar(record["init_gas"], "float"),
                        self._format_scalar(record["emission"], "float"),
                        *[self._format_scalar(value, "float") for value in record["bin_values"]],
                    ],
                    comment,
                )
            )

        lines.append(_format_line([self._format_scalar(value, "float") for value in normalized["init_bin_number"]], "## initial bin number"))
        lines.append(
            _format_line(
                [self._format_scalar(value, "float") for value in normalized["init_bin_emission_species_1"]],
                "## emission row 1",
            )
        )
        lines.append(
            _format_line(
                [self._format_scalar(value, "float") for value in normalized["init_bin_emission_species_2"]],
                "## emission row 2",
            )
        )
        lines.append(_format_line([self._format_scalar(value, "float") for value in normalized["diameter_bounds"]], "## diameter bounds"))
        lines.append(_format_line([scalars["kind_composition"]], "## composition discretization mode"))
        lines.append(_format_line([scalars["n_frac"]], "## fraction sections"))
        lines.append(_format_line([self._format_scalar(value, "float") for value in normalized["fraction_bounds"]], "## fraction bounds"))

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return target

    def normalize(self, data: dict[str, Any]) -> dict[str, Any]:
        normalized = {
            "path": data.get("path", ""),
            "raw_lines": list(data.get("raw_lines", [])),
            "scalars": deepcopy(data["scalars"]),
            "species_records": [deepcopy(record) for record in data["species_records"]],
            "init_bin_number": [float(value) for value in data["init_bin_number"]],
            "init_bin_emission_species_1": [float(value) for value in data["init_bin_emission_species_1"]],
            "init_bin_emission_species_2": [float(value) for value in data["init_bin_emission_species_2"]],
            "emission_matrix": [list(row) for row in data.get("emission_matrix", [])],
            "diameter_bounds": [float(value) for value in data["diameter_bounds"]],
            "fraction_bounds": [float(value) for value in data["fraction_bounds"]],
            "mapping_scheme": data.get("mapping_scheme", "DETERMINISTIC_NEAREST"),
            "mixing_assumption": data.get("mixing_assumption", "EXTERNAL_MIXING"),
            "case_preset": data.get("case_preset", "coag_only"),
            "template_name": data.get("template_name", "tutorial_minimal"),
        }
        normalized["scalars"]["n_species"] = int(normalized["scalars"]["n_species"])
        normalized["scalars"]["n_sizebin"] = int(normalized["scalars"]["n_sizebin"])
        normalized["scalars"]["n_frac"] = int(normalized["scalars"]["n_frac"])
        normalized["scalars"]["n_groups"] = int(normalized["scalars"]["n_groups"])
        redistribution_option = str(normalized["scalars"].get("redistribution_option", "core_conserv")).strip().lower()
        if redistribution_option not in SUPPORTED_REDISTRIBUTION_OPTIONS:
            redistribution_option = "core_conserv"
        normalized["scalars"]["redistribution_option"] = redistribution_option
        normalized["raw_lines"] = self.default_lines()

        n_species = int(normalized["scalars"]["n_species"])
        n_sizebin = int(normalized["scalars"]["n_sizebin"])
        n_frac = int(normalized["scalars"]["n_frac"])

        species_records = normalized["species_records"][:n_species]
        while len(species_records) < n_species:
            idx = len(species_records) + 1
            species_records.append(
                {
                    "species_id": idx,
                    "species_name": f"species_{idx}",
                    "group_id": min(idx, max(int(normalized["scalars"]["n_groups"]), 1)),
                    "init_gas": 0.0,
                    "emission": 0.0,
                    "bin_values": [0.0] * n_sizebin,
                    "notes": "",
                }
            )
        for idx, record in enumerate(species_records, start=1):
            record["species_id"] = int(record.get("species_id", idx))
            record["species_name"] = str(record.get("species_name", f"species_{idx}"))
            record["group_id"] = int(record.get("group_id", 1))
            record["init_gas"] = float(record.get("init_gas", 0.0))
            record["emission"] = float(record.get("emission", 0.0))
            values = [float(value) for value in record.get("bin_values", [])][:n_sizebin]
            if len(values) < n_sizebin:
                values.extend([0.0] * (n_sizebin - len(values)))
            record["bin_values"] = values
            record["notes"] = str(record.get("notes", ""))
        normalized["species_records"] = species_records

        normalized["init_bin_number"] = self._normalize_vector(normalized["init_bin_number"], n_sizebin, 1.0e3)
        normalized["init_bin_emission_species_1"] = self._normalize_vector(normalized["init_bin_emission_species_1"], n_sizebin, 0.0)
        normalized["init_bin_emission_species_2"] = self._normalize_vector(normalized["init_bin_emission_species_2"], n_sizebin, 0.0)

        emission_matrix = [list(row) for row in normalized.get("emission_matrix", [])][:n_species]
        while len(emission_matrix) < n_species:
            emission_matrix.append([0.0] * n_sizebin)
        emission_matrix = [self._normalize_vector(row, n_sizebin, 0.0) for row in emission_matrix]
        normalized["emission_matrix"] = emission_matrix
        normalized["init_bin_emission_species_1"] = emission_matrix[0] if emission_matrix else [0.0] * n_sizebin
        normalized["init_bin_emission_species_2"] = emission_matrix[1] if len(emission_matrix) > 1 else [0.0] * n_sizebin

        bounds = [float(value) for value in normalized["diameter_bounds"]]
        if len(bounds) != n_sizebin + 1:
            bounds = self._logspace_bounds(n_sizebin)
        normalized["diameter_bounds"] = bounds

        fractions = [float(value) for value in normalized["fraction_bounds"]]
        if len(fractions) != n_frac + 1:
            step = 1.0 / max(n_frac, 1)
            fractions = [round(idx * step, 6) for idx in range(n_frac + 1)]
            fractions[-1] = 1.0
        normalized["fraction_bounds"] = fractions
        return normalized

    def validate(self, data: dict[str, Any]) -> list[str]:
        normalized = self.normalize(data)
        errors: list[str] = []
        n_species = int(normalized["scalars"]["n_species"])
        n_sizebin = int(normalized["scalars"]["n_sizebin"])
        n_frac = int(normalized["scalars"]["n_frac"])
        if n_species != len(normalized["species_records"]):
            errors.append("n_species does not match species table row count")
        if n_sizebin != len(normalized["init_bin_number"]):
            errors.append("n_sizebin does not match initial number row length")
        if len(normalized["diameter_bounds"]) != n_sizebin + 1:
            errors.append("diameter bounds length must equal n_sizebin + 1")
        if len(normalized["fraction_bounds"]) != n_frac + 1:
            errors.append("fraction bounds length must equal n_frac + 1")
        if not self._is_strictly_increasing(normalized["diameter_bounds"]):
            errors.append("diameter bounds must be strictly increasing")
        if not self._is_strictly_increasing(normalized["fraction_bounds"]):
            errors.append("fraction bounds must be strictly increasing")
        if abs(normalized["fraction_bounds"][0]) > 1.0e-9 or abs(normalized["fraction_bounds"][-1] - 1.0) > 1.0e-9:
            errors.append("fraction bounds must start at 0 and end at 1")
        for record in normalized["species_records"]:
            if len(record["bin_values"]) != n_sizebin:
                errors.append(f"species {record['species_id']} does not have {n_sizebin} initial mass entries")
        if normalized.get("mapping_scheme") not in {"LEGACY", "DETERMINISTIC_NEAREST"}:
            errors.append("mapping scheme must be LEGACY or DETERMINISTIC_NEAREST")
        if normalized.get("mixing_assumption") not in SUPPORTED_MIXING_ASSUMPTIONS:
            errors.append("mixing assumption must be INTERNAL_MIXING or EXTERNAL_MIXING")
        if normalized.get("mapping_scheme") == "LEGACY" and not normalized["scalars"]["coefficient_file"]:
            errors.append("legacy mapping requires a coefficient file")
        if normalized["scalars"].get("redistribution_option") not in SUPPORTED_REDISTRIBUTION_OPTIONS:
            errors.append("redistribution option must be legacy, core_conserv, core_nogrow, or core_smallgrow")
        return errors

    def size_rows(self, data: dict[str, Any]) -> list[dict[str, float | int | str]]:
        normalized = self.normalize(data)
        rows: list[dict[str, float | int | str]] = []
        for idx in range(int(normalized["scalars"]["n_sizebin"])):
            lower = normalized["diameter_bounds"][idx]
            upper = normalized["diameter_bounds"][idx + 1]
            rows.append(
                {
                    "bin_id": idx + 1,
                    "lower_bound": lower,
                    "upper_bound": upper,
                    "representative_diameter": sqrt(lower * upper),
                    "initial_number": normalized["init_bin_number"][idx],
                    "notes": "",
                }
            )
        return rows

    def fraction_rows(self, data: dict[str, Any]) -> list[dict[str, float | int | str]]:
        normalized = self.normalize(data)
        rows: list[dict[str, float | int | str]] = []
        for idx in range(int(normalized["scalars"]["n_frac"])):
            rows.append(
                {
                    "fraction_id": idx + 1,
                    "lower_bound": normalized["fraction_bounds"][idx],
                    "upper_bound": normalized["fraction_bounds"][idx + 1],
                    "notes": "",
                }
            )
        return rows

    def _coerce(self, value: str, value_type: str) -> Any:
        if value_type in {"int", "bool_int"}:
            return int(float(value))
        if value_type == "float":
            return float(value)
        return value

    def _format_scalar(self, value: Any, value_type: str) -> str:
        if value_type in {"int", "bool_int"}:
            return str(int(value))
        if value_type == "float":
            return f"{float(value):.12g}"
        return str(value)

    def _normalize_vector(self, values: list[float], target_len: int, fill: float) -> list[float]:
        vector = [float(value) for value in values][:target_len]
        if len(vector) < target_len:
            vector.extend([fill] * (target_len - len(vector)))
        return vector

    def _logspace_bounds(self, n_sizebin: int) -> list[float]:
        if n_sizebin <= 0:
            return [0.001, 1.0]
        start = 0.001
        end = 10.0
        ratio = (end / start) ** (1.0 / n_sizebin)
        values = [start]
        for _ in range(n_sizebin):
            values.append(values[-1] * ratio)
        return values

    def _is_strictly_increasing(self, values: list[float]) -> bool:
        return all(right > left for left, right in zip(values, values[1:]))

    def _species_comment(self, record: dict[str, Any], idx: int) -> str:
        name = str(record.get("species_name", f"species_{idx + 1}")).strip()
        notes = str(record.get("notes", "")).strip()
        if name and notes:
            return f"## {name}; {notes}"
        if name:
            return f"## {name}"
        if notes:
            return f"## species_{idx + 1}; {notes}"
        return f"## species_{idx + 1}"
