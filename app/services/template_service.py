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
        "description_en": "Fast-start teaching case with two species (BC + sulfate) and seven size sections: internal/external mixing structure comparison only. The two-species base has a degenerate inorganic system, so the core's 'Mass Cond' counter is not usable here - use 'Teaching: BC-sulfate aging' for the aging demo.",
        "description_zh": "两种组分（黑碳 + 硫酸盐）、七个粒径档的内/外混结构对比教学案例——只演示结构与表示差异（两物种基座的无机体系退化，内核「质量冷凝」计数不可用；要演示老化请用「教学案例：黑碳–硫酸盐老化」）。",
        "base": "teaching",
        "updates": {
            # 2026-09-30（用户要求）：案例预设已从界面与数据模型里删除 —— 过程开关与时长由模板
            # 直接给出，界面上就是三个勾选框 + 时长输入框，所见即所跑（不再有"预设覆盖用户改动"）。
            "mixing_assumption": "EXTERNAL_MIXING",
            "mapping_scheme": "DETERMINISTIC_NEAREST",
            "scalars": {
                "tag_external": 0,
                "tagrho": 0,
                "with_coag": 1,
                "with_cond": 0,
                "with_nucl": 0,
                "final_time_hours": 0.5,
            },
        },
    },
    {
        "id": "tutorial_aging",
        "category": "teaching",
        "name_en": "Teaching: BC-sulfate aging (3 species)",
        "name_zh": "教学案例：黑碳–硫酸盐老化（三组分）",
        "description_en": "BC + sulfate + ammonium: coagulation and condensation over 12 h, starting from pure (externally mixed) particles - watch sulfate coat the soot, a mixed composition bin appear, and the mixing degree rise.",
        "description_zh": "黑碳 + 硫酸盐 + 铵（三组分）：凝并 + 冷凝、12 小时，初始为纯粒子（外混放置）——观察硫酸盐包裹黑碳、混合档出现、混合度上升。",
        "base": "teaching",
        "updates": {
            "mixing_assumption": "EXTERNAL_MIXING",
            "mapping_scheme": "DETERMINISTIC_NEAREST",
            "scalars": {
                "tag_external": 1,
                "tagrho": 0,
                "with_coag": 1,
                "with_cond": 1,
                "with_nucl": 0,
                "final_time_hours": 12.0,
            },
            # 2026-09-30：三组分逐档质量必须与基座的 init_bin_number 自洽，否则 SCRAM1.2 的
            # moving-center 重分布会按「档内质量/档内个数」反推的中心粒径把整档搬走
            # （写在第 5–6 档的质量在末态跑到第 2–3 档）。下面三个数组是「基座两物质值按
            # 原 BC:SO4:NH4 份额拆三份」的重建结果：每档三者之和 = N_k*(pi/6)*d_k^3*rho，
            # d_k 取档边界几何平均、rho = 1800 kg/m3。改基座的 init_bin_number 或这里任一
            # 数组都必须同步重算（config_model._domain_guards 会在运行前拦下不自洽的组合）。
            "species": {
                "2": {"bin_values": [1.69955e-10, 5.44026e-07, 0.00140863, 0.279036, 4.81543, 4.41814, 1.93717]},
                "4": {"bin_values": [3.3991e-09, 4.0802e-06, 0.00316942, 0.613879, 11.4653, 2.14937, 0.290576]},
                "5": {
                    "bin_values": [1.69955e-09, 2.0401e-06, 0.00140863, 0.334843, 4.58612, 0.955274, 0.145288],
                    "init_gas": 4.32472,
                },
            },
        },
    },
    {
        "id": "gmd_hazy_condensation",
        "category": "gmd_validation",
        "name_en": "GMD hazy condensation validation",
        "name_zh": "GMD hazy 冷凝验证",
        "description_en": "Reference-style validation case from Zhu et al. (2015): hazy 12 h condensation at 298 K and 1 atm.",
        "description_zh": "对应 Zhu et al. (2015) 第 3 节的 hazy 12 小时冷凝验证场景，298 K、1 atm。",
        "base": "baseline",
        "updates": {
            "mixing_assumption": "EXTERNAL_MIXING",
            "mapping_scheme": "DETERMINISTIC_NEAREST",
            "scalars": {
                "with_coag": 0,
                "with_cond": 1,
                "with_nucl": 0,
                # 2026-09-12 人工复核（按论文补恒定硫酸盐气相源）：本体把论文 hazy 验证案例的
                # "恒定硫酸盐源 2.29e-4 µg/m³/s（= 5.5 µm³/cm³/12h @ ρ=1.77）"硬编码在
                # `nucl_model=5` 分支里（ModuleDiscretization.f90:713-714，注释 "specified for the
                # validation test"），且只挂在 ESO4（=30 物种布局里的索引 4）上。
                # 因此教学基座（2 物种）接不到该源 → 冷凝空转（Q-18）；改用 baseline 布局 + nucl_model=5，
                # 实测源值 2.29e-4 生效、Mass Cond 非零。
                "nucl_model": 5,
                "temperature": 298.0,
                "pressure": 101325.0,
                "humidity": 0.7,
                "final_time_hours": 12.0,
                "dtmin_seconds": 1.0,
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
        "base": "baseline",
        "updates": {
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
                # 2026-09-12 人工复核：原为 6（euler_coupled）。该方案在本体里是最脆弱的一支
                # （重复交付 hand-out → 数量不守恒 → STOP，见 BUG_TRACKING #7），
                # 而本体/论文口径用的都是 2（Moving Diameter，baseline12h.cfg 第 7 行）。
                # 教学模板不应默认踩在本体的已知缺陷上，故改回 2；要用 6 请显式选择。
                "redistribution_method": 2,
                # 同 gmd_hazy_condensation：用 baseline 布局 + nucl_model=5 才能拿到论文的恒定硫酸盐源
                "nucl_model": 5,
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
        self.examples_path = root / "examples" / "configs" / "default_config.cfg"

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
        elif template["base"] == "teaching":
            data = self.config_model.parse(self.examples_path)
        else:
            data = self.config_model.new_default()
        updates = template.get("updates", {})
        data["template_name"] = template_id
        data["mixing_assumption"] = updates.get("mixing_assumption", data.get("mixing_assumption", "EXTERNAL_MIXING"))
        data["mapping_scheme"] = updates.get("mapping_scheme", data.get("mapping_scheme", "DETERMINISTIC_NEAREST"))
        for key, value in updates.get("scalars", {}).items():
            data["scalars"][key] = value
        # 2026-09-30：模板可覆写单个物种的初值（给占位槽补质量/气相，如老化教学案例补 NH4）。
        for species_id, patch in (updates.get("species") or {}).items():
            for record in data.get("species_records", []):
                if int(record.get("species_id", -1)) == int(species_id):
                    record.update(patch)
                    break
        return self.config_model.normalize(data)
