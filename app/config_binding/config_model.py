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


# 2026-09-23 改造（原 Bug #12「RDB core-aware 死控件」）：
# `redistribution_option` 现在接的是**核心真的会读**的环境变量 `SCRAM_REDISTRIBUTION_MODE`
# （SCRAM1.2 新增，见 `SCRAM1.2/SRC/ModuleDiscretization.f90` 开头的 read_discretization）。
# 核心接受且仅接受这两个值（其它值会 `error stop 'SCRAM1.2: unknown SCRAM_REDISTRIBUTION_MODE'`；
# 变量未设置时默认就是 moving_center_dualpivot）：
#   moving_center_dualpivot —— 1.2 新内核（默认；method≥2 一律走它，2/3/4/5/6 等价）
#   legacy                 —— 旧内核，恢复 method 2/3/4/5/6 的旧语义（注意：legacy 下
#                             method=6 会复现本体自带的「数量不守恒」Bug #7）
REMAP_MODE_DUALPIVOT = "moving_center_dualpivot"
REMAP_MODE_LEGACY = "legacy"
SUPPORTED_REDISTRIBUTION_OPTIONS = {REMAP_MODE_DUALPIVOT, REMAP_MODE_LEGACY}
SUPPORTED_MIXING_ASSUMPTIONS = {"INTERNAL_MIXING", "EXTERNAL_MIXING"}

# Bug #24 安全闸门（2026-09-23）：核心 ModuleAdaptstep.f90 的求解器分发只判 0（euler）/1（ETR）/
# 2（ROS2），**没有 else 分支**；而唯一推进子步时钟的语句只存在于这三个求解器内部
# ⇒ 越界值会让外层 `do while (current_sub_time .lt. final_sub_time)` 永不退出（死循环挂住，
# 只能强杀，实测 core 60 s 无任何 Progress 输出）。这里在运行前拦下，比让核心挂死好。
# 注意：本表只用于**校验**，不改界面控件（控件范围收窄属界面变更，另议）。
SUPPORTED_DYNAMIC_SOLVERS = {0, 1, 2}

# 内核（SCRAM1.2/SRC/ModuleDiscretization.f90:129-136）在 nucl_model=5 时**按设计跳过**
# `init_bin_number` + 两行 `init_bin_emission` 共三行：nucl_model=5 是自成一体的硬编码
# 验证模式，初始化走 `if(nucl_model.eq.5)` 分支、排放硬编码 `gas_emision_rate(ESO4)`，
# 这三个数组内核读了也不用。
# 因此本写入器必须同步省略，否则文件指针错位 ⇒ 后续 diameter 读取读到这三行 ⇒
# `Bad integer/real in list input` 崩溃（Bug #9）。
# 注意：物种行内核是**无条件读入**的（同文件 :117-127），所以只有这三行是条件性的。
NUCL_MODEL_HARDCODED = 5


def _has_emission_block(scalars: dict[str, Any]) -> bool:
    """cfg 是否应包含 init_bin_number + 两行 init_bin_emission（内核契约）。

    返回 True 表示按标准格式写出/读入；False 表示 nucl_model=5 的 53 行精简格式。
    取值无法解析时按标准格式处理（保守：宁可多写，由内核报错暴露）。
    """
    try:
        return int(scalars.get("nucl_model", 0)) != NUCL_MODEL_HARDCODED
    except (TypeError, ValueError):
        return True


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
        if _has_emission_block(data["scalars"]):
            data["init_bin_number"] = [float(value) for value in _tokens(lines[after_species])]
            data["init_bin_emission_species_1"] = [float(value) for value in _tokens(lines[after_species + 1])]
            data["init_bin_emission_species_2"] = [float(value) for value in _tokens(lines[after_species + 2])]
            diameter_line = after_species + 3
        else:
            # nucl_model=5：内核不消费这三个数组，填良构占位值，让内存模型与标准格式保持同形
            # （GUI 的表格列数、validate() 的长度校验都依赖它）。
            data["init_bin_number"] = [0.0] * n_sizebin
            data["init_bin_emission_species_1"] = [0.0] * n_sizebin
            data["init_bin_emission_species_2"] = [0.0] * n_sizebin
            diameter_line = after_species
            # 失败要显式：把 56 行格式喂给 nucl_model=5，必须报错而不是错位读出一堆垃圾。
            leftover = [line for line in lines[diameter_line + 4:] if line.strip()]
            if leftover:
                raise ValueError(
                    f"nucl_model={NUCL_MODEL_HARDCODED} 的配置不应包含 "
                    f"init_bin_number/init_bin_emission 三行，但 {path} 尾部多出 "
                    f"{len(leftover)} 行 ⇒ 写入器与内核契约不一致（Bug #9）。"
                    f"若这是标准格式配置，请把 nucl_model 改为非 5 的值。"
                )
        emission_matrix: list[list[float]] = []
        for idx in range(n_species):
            if idx == 0:
                emission_matrix.append(list(data["init_bin_emission_species_1"]))
            elif idx == 1:
                emission_matrix.append(list(data["init_bin_emission_species_2"]))
            else:
                emission_matrix.append([0.0] * n_sizebin)
        data["emission_matrix"] = emission_matrix
        data["diameter_bounds"] = [float(value) for value in _tokens(lines[diameter_line])]
        data["scalars"]["kind_composition"] = int(_tokens(lines[diameter_line + 1])[0])
        data["scalars"]["n_frac"] = int(_tokens(lines[diameter_line + 2])[0])
        data["scalars"].setdefault("redistribution_option", REMAP_MODE_DUALPIVOT)
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

        # 这三行是条件性的：nucl_model=5 时内核按设计跳过，写入器必须同步省略（见 _has_emission_block）
        if _has_emission_block(scalars):
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
            # Bug #19 修复（2026-09-23）：必须保留 explicit_keys。
            # 原先这里构造成"只含固定键的新字典"，会把调用方刚算好的 explicit_keys 静默丢掉
            # ⇒ GUI 路径上传给 prepare_run 的永远是空集 ⇒ 案例预设无条件覆盖用户设置
            # （#11 的修复在 GUI 上失效）。normalize 是唯一稳妥的位置：
            # _with_mixing_assumption 与 _with_case_preset 内部都会再调一次 normalize。
            "explicit_keys": [str(key) for key in (data.get("explicit_keys") or [])],
        }
        normalized["scalars"]["n_species"] = int(normalized["scalars"]["n_species"])
        normalized["scalars"]["n_sizebin"] = int(normalized["scalars"]["n_sizebin"])
        normalized["scalars"]["n_frac"] = int(normalized["scalars"]["n_frac"])
        normalized["scalars"]["n_groups"] = int(normalized["scalars"]["n_groups"])
        redistribution_option = str(normalized["scalars"].get("redistribution_option", REMAP_MODE_DUALPIVOT)).strip().lower()
        if redistribution_option not in SUPPORTED_REDISTRIBUTION_OPTIONS:
            redistribution_option = REMAP_MODE_DUALPIVOT
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

        # nl=5 时这三个数组内核不读、也不写出，默认值必须是 0（原来固定填 1.0e3 会让预览表显示假的初始数浓度）
        number_default = 1.0e3 if _has_emission_block(normalized["scalars"]) else 0.0
        normalized["init_bin_number"] = self._normalize_vector(normalized["init_bin_number"], n_sizebin, number_default)
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
            errors.append(
                "redistribution option must be moving_center_dualpivot or legacy "
                "(it is passed to the core as SCRAM_REDISTRIBUTION_MODE)"
            )
        # Bug #24 安全闸门：越界的求解器号会让核心死循环挂住（见模块顶部注释）
        try:
            solver = int(normalized["scalars"].get("dynamic_solver", 2))
        except (TypeError, ValueError):
            errors.append("dynamic solver must be an integer (0, 1, or 2)")
        else:
            if solver not in SUPPORTED_DYNAMIC_SOLVERS:
                errors.append(
                    f"dynamic solver must be 0 (euler), 1 (ETR) or 2 (ROS2), got {solver}: "
                    "any other value makes the core loop forever without advancing the "
                    "sub-step clock (Bug #24)"
                )
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
