from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from app.config_binding.config_model import ConfigModel


TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "tutorial_minimal",
        "category": "teaching",
        "name_en": "Minimal tutorial (BC + sulfate)",
        "name_zh": "最简单教学案例（BC + 硫酸盐）",
        "description_en": "Fast-start teaching case with two species, four size bins, and internal/external mixing comparison.",
        "description_zh": "两种组分、四个粒径 bin 的快速教学案例，适合首次体验 internal / external mixing 对比。",
        "base": "default",
        "updates": {
            "case_preset": "coag_only",
            "mixing_assumption": "EXTERNAL_MIXING",
            "mapping_scheme": "DETERMINISTIC_NEAREST",
            "scalars": {"tag_external": 0, "tagrho": 0},
        },
    },
    {
        "id": "gmd_hazy_condensation",
        "category": "gmd_validation",
        "name_en": "GMD hazy condensation validation",
        "name_zh": "GMD hazy 冷凝验证",
        "description_en": "Reference-style validation case from Zhu et al. (2015): hazy 12 h condensation at 298 K and 1 atm.",
        "description_zh": "对应 Zhu et al. (2015) 第 3 节的 hazy 12 小时冷凝验证场景，298 K、1 atm。",
        "base": "default",
        "updates": {
            "case_preset": "gmd_hazy_condensation",
            "mixing_assumption": "EXTERNAL_MIXING",
            "mapping_scheme": "DETERMINISTIC_NEAREST",
            "scalars": {
                "with_coag": 0,
                "with_cond": 1,
                "with_nucl": 0,
                "temperature": 298.0,
                "pressure": 101325.0,
                "humidity": 0.7,
                "final_time_hours": 12.0,
                "dtmin_seconds": 1.0,
                "n_sizebin": 4,
                "n_frac": 2,
                "tag_external": 0,
            },
        },
    },
    {
        "id": "gmd_hazy_coag_cond",
        "category": "gmd_validation",
        "name_en": "GMD hazy coagulation + condensation validation",
        "name_zh": "GMD hazy 凝并+冷凝验证",
        "description_en": "Reference-style validation case from Zhu et al. (2015): hazy 12 h condensation with coagulation.",
        "description_zh": "对应 Zhu et al. (2015) 第 3 节的 hazy 12 小时凝并+冷凝联合验证场景。",
        "base": "default",
        "updates": {
            "case_preset": "gmd_hazy_coag_cond",
            "mixing_assumption": "EXTERNAL_MIXING",
            "mapping_scheme": "DETERMINISTIC_NEAREST",
            "scalars": {
                "with_coag": 1,
                "with_cond": 1,
                "with_nucl": 0,
                "temperature": 298.0,
                "pressure": 101325.0,
                "humidity": 0.7,
                "final_time_hours": 12.0,
                "dtmin_seconds": 1.0,
                "redistribution_method": 6,
                "n_sizebin": 4,
                "n_frac": 2,
                "tag_external": 0,
            },
        },
    },
    {
        "id": "gmd_paris_emission_only",
        "category": "gmd_reference",
        "name_en": "GMD Greater Paris scenario A (emission only)",
        "name_zh": "GMD 巴黎场景 A（仅排放）",
        "description_en": "Greater Paris reference scenario from Zhu et al. (2015), scenario A: emission only.",
        "description_zh": "对应 Zhu et al. (2015) 第 4 节的 Greater Paris 参考场景 A，仅排放。",
        "base": "baseline",
        "updates": {
            "case_preset": "gmd_paris_emission_only",
            "mixing_assumption": "EXTERNAL_MIXING",
            "mapping_scheme": "DETERMINISTIC_NEAREST",
            "scalars": {"with_coag": 0, "with_cond": 0, "with_nucl": 0, "final_time_hours": 12.0, "tag_external": 0},
        },
    },
    {
        "id": "gmd_paris_coagulation",
        "category": "gmd_reference",
        "name_en": "GMD Greater Paris scenario B (emission + coagulation)",
        "name_zh": "GMD 巴黎场景 B（排放 + 凝并）",
        "description_en": "Greater Paris reference scenario from Zhu et al. (2015), scenario B: emission with coagulation.",
        "description_zh": "对应 Zhu et al. (2015) 第 4 节的 Greater Paris 参考场景 B，排放 + 凝并。",
        "base": "baseline",
        "updates": {
            "case_preset": "gmd_paris_coagulation",
            "mixing_assumption": "EXTERNAL_MIXING",
            "mapping_scheme": "DETERMINISTIC_NEAREST",
            "scalars": {"with_coag": 1, "with_cond": 0, "with_nucl": 0, "final_time_hours": 12.0, "tag_external": 0},
        },
    },
    {
        "id": "gmd_paris_condensation",
        "category": "gmd_reference",
        "name_en": "GMD Greater Paris scenario C (emission + condensation)",
        "name_zh": "GMD 巴黎场景 C（排放 + 冷凝）",
        "description_en": "Greater Paris reference scenario from Zhu et al. (2015), scenario C: emission with condensation.",
        "description_zh": "对应 Zhu et al. (2015) 第 4 节的 Greater Paris 参考场景 C，排放 + 冷凝。",
        "base": "baseline",
        "updates": {
            "case_preset": "gmd_paris_condensation",
            "mixing_assumption": "EXTERNAL_MIXING",
            "mapping_scheme": "DETERMINISTIC_NEAREST",
            "scalars": {"with_coag": 0, "with_cond": 1, "with_nucl": 0, "final_time_hours": 12.0, "tag_external": 0},
        },
    },
    {
        "id": "gmd_paris_full",
        "category": "gmd_reference",
        "name_en": "GMD Greater Paris scenario D (full dynamics)",
        "name_zh": "GMD 巴黎场景 D（全过程）",
        "description_en": "Greater Paris reference scenario from Zhu et al. (2015), scenario D: emission + C/E + coagulation + nucleation.",
        "description_zh": "对应 Zhu et al. (2015) 第 4 节的 Greater Paris 参考场景 D，排放 + 冷凝/蒸发 + 凝并 + 成核。",
        "base": "baseline",
        "updates": {
            "case_preset": "gmd_paris_full",
            "mixing_assumption": "EXTERNAL_MIXING",
            "mapping_scheme": "DETERMINISTIC_NEAREST",
            "scalars": {"with_coag": 1, "with_cond": 1, "with_nucl": 1, "final_time_hours": 12.0, "tag_external": 0},
        },
    },
]


class TemplateService:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.config_model = ConfigModel(root)
        self.baseline_path = root / "core" / "templates" / "baseline12h.cfg"

    def list_templates(self) -> list[dict[str, Any]]:
        return deepcopy(TEMPLATES)

    def template_by_id(self, template_id: str) -> dict[str, Any]:
        for item in TEMPLATES:
            if item["id"] == template_id:
                return deepcopy(item)
        raise KeyError(template_id)

    def load_template(self, template_id: str) -> dict[str, Any]:
        template = self.template_by_id(template_id)
        if template["base"] == "baseline":
            data = self.config_model.parse(self.baseline_path)
        else:
            data = self.config_model.new_default()
        updates = template.get("updates", {})
        data["template_name"] = template_id
        data["case_preset"] = updates.get("case_preset", data.get("case_preset", "coag_only"))
        data["mixing_assumption"] = updates.get("mixing_assumption", data.get("mixing_assumption", "EXTERNAL_MIXING"))
        data["mapping_scheme"] = updates.get("mapping_scheme", data.get("mapping_scheme", "DETERMINISTIC_NEAREST"))
        for key, value in updates.get("scalars", {}).items():
            data["scalars"][key] = value
        return self.config_model.normalize(data)
