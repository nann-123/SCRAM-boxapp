from __future__ import annotations

import csv
import math
import os
import subprocess
import sys
import time
from functools import partial
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, QTimer, Qt, Signal
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
    QDoubleSpinBox,
)

from app.config_binding.config_model import ConfigModel
from app.services.i18n_service import I18nService
from app.services.plot_service import PlotService
from app.services.report_service import ReportService
from app.services.run_service import CASE_PRESETS, RunService
from app.services.settings_service import SettingsService
from app.services.template_service import TemplateService


class RunWorker(QThread):
    stage_changed = Signal(object)
    message = Signal(str)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, run_service: RunService, prepared_runs: list[dict[str, Any]]) -> None:
        super().__init__()
        self.run_service = run_service
        self.prepared_runs = prepared_runs

    def run(self) -> None:
        rows: list[dict[str, Any]] = []
        try:
            for prepared in self.prepared_runs:
                self.stage_changed.emit(prepared)
                rows.append(self.run_service.run_prepared(prepared, log_callback=self.message.emit))
            if rows:
                self.run_service.write_summaries(rows, output_root=Path(self.prepared_runs[0]["run_root"]).parents[2])
            self.completed.emit(rows)
        except Exception as exc:  # pragma: no cover - UI path
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self, root: Path) -> None:
        super().__init__()
        self.root = root
        self.app_version = "0.3.0"
        self.config_model = ConfigModel(root)
        self.template_service = TemplateService(root)
        self.run_service = RunService(root)
        self.plot_service = PlotService(root)
        self.report_service = ReportService(root)
        self.settings_service = SettingsService(root)
        self.settings = self.settings_service.load()
        self.i18n = I18nService(root, str(self.settings["language"]))
        default_template = str(self.settings.get("last_template", "gmd_paris_full"))
        self.data = self.template_service.load_template(default_template)
        self.data["experiment_name"] = self.data.get("experiment_name", default_template)
        self.current_config_path = self.config_model.default_path
        self.current_results_root = Path(str(self.settings["default_output_directory"]))
        self.field_widgets: dict[str, QWidget] = {}
        self.run_worker: RunWorker | None = None
        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self._refresh_run_monitor)
        self.current_prepared: dict[str, Any] | None = None
        self.current_run_started_at = 0.0
        self._build_ui()
        self.refresh_all()

    def _build_ui(self) -> None:
        self._build_toolbar()
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self.experiment_tab = QWidget()
        self.structure_tab = QWidget()
        self.run_tab = QWidget()
        self.results_tab = QWidget()
        self.report_tab = QWidget()
        self.settings_tab = QWidget()
        self.help_tab = QWidget()
        self.tabs.addTab(self.experiment_tab, "")
        self.tabs.addTab(self.structure_tab, "")
        self.tabs.addTab(self.run_tab, "")
        self.tabs.addTab(self.results_tab, "")
        if self.report_service.available():
            self.tabs.addTab(self.report_tab, "")
        self.tabs.addTab(self.settings_tab, "")
        self.tabs.addTab(self.help_tab, "")
        self._build_experiment_tab()
        self._build_structure_tab()
        self._build_run_tab()
        self._build_results_tab()
        if self.report_service.available():
            self._build_report_tab()
        self._build_settings_tab()
        self._build_help_tab()
        self.statusBar().showMessage(self.i18n.t("status_ready"))

    def _rebuild_ui(self) -> None:
        self.data = self._collect_data()
        old = self.centralWidget()
        if old is not None:
            old.deleteLater()
        for child in self.findChildren(QToolBar):
            self.removeToolBar(child)
            child.deleteLater()
        self.field_widgets = {}
        self._build_ui()

    def _build_toolbar(self) -> None:
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setStyleSheet("QToolButton { font-size: 14px; padding: 8px 14px; min-width: 96px; min-height: 34px; }")
        self.addToolBar(toolbar)
        actions = [
            ("new_experiment", self.new_from_defaults),
            ("run", self.run_single_case),
            ("stop", self.stop_run),
            ("view_results", lambda: self.tabs.setCurrentWidget(self.results_tab)),
            ("export_report", self._open_report_tab),
        ]
        for key, handler in actions:
            action = QAction(self.i18n.t(key), self)
            action.triggered.connect(handler)
            toolbar.addAction(action)
        toolbar.addSeparator()
        self.toolbar_language_combo = QComboBox()
        self.toolbar_language_combo.addItems(["zh_CN", "en_US"])
        self.toolbar_language_combo.setCurrentText(str(self.settings["language"]))
        self.toolbar_language_combo.currentTextChanged.connect(self.change_language)
        toolbar.addWidget(QLabel(self.i18n.t("language")))
        toolbar.addWidget(self.toolbar_language_combo)

    def _build_experiment_tab(self) -> None:
        outer = QVBoxLayout(self.experiment_tab)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        actions_row = QHBoxLayout()
        for key, handler in [
            ("load_config", self.load_config),
            ("save_config", self.save_config),
            ("save_as", self.save_config_as),
            ("validate_config", self.validate_config),
        ]:
            button = QPushButton(self.i18n.t(key))
            button.clicked.connect(handler)
            actions_row.addWidget(button)
        actions_row.addStretch(1)
        layout.addLayout(actions_row)

        cards = QGridLayout()
        cards.setColumnStretch(0, 1)
        cards.setColumnStretch(1, 1)
        cards.setColumnStretch(2, 1)

        experiment_card = QGroupBox(self.i18n.t("experiment_card"))
        experiment_form = QFormLayout(experiment_card)
        self.experiment_name_edit = QLineEdit()
        self.template_combo = QComboBox()
        for template in self.template_service.list_templates():
            label = template["name_zh"] if self.i18n.language.startswith("zh") else template["name_en"]
            self.template_combo.addItem(label, template["id"])
        self.template_combo.addItem(self.i18n.t("custom_config"), "__custom__")
        self.template_combo.currentTextChanged.connect(lambda _text: self._update_template_description())
        self.load_template_button = QPushButton(self.i18n.t("load_template"))
        self.load_template_button.clicked.connect(self.load_template)
        template_row = QWidget()
        template_layout = QHBoxLayout(template_row)
        template_layout.setContentsMargins(0, 0, 0, 0)
        template_layout.addWidget(self.template_combo)
        template_layout.addWidget(self.load_template_button)
        self.template_description = QLabel()
        self.template_description.setWordWrap(True)
        self.case_preset_combo = QComboBox()
        self.case_preset_combo.addItems(list(CASE_PRESETS))
        self.case_preset_combo.currentTextChanged.connect(self.apply_case_preset)
        self.mapping_scheme_combo = QComboBox()
        self.mapping_scheme_combo.addItems(["INTERNAL_MIXING", "EXTERNAL_MIXING"])
        self._mixing_scheme_locked = ""
        self.mapping_scheme_combo.currentIndexChanged.connect(self._on_mixing_scheme_changed)
        self.mapping_scheme_combo.setToolTip(self.i18n.t("mixing_scheme_readonly_tip"))
        self.coefficient_file_edit = QLineEdit()
        coeff_browse = QPushButton(self.i18n.t("browse"))
        coeff_browse.clicked.connect(self.choose_coefficient_file)
        coeff_row = QWidget()
        coeff_layout = QHBoxLayout(coeff_row)
        coeff_layout.setContentsMargins(0, 0, 0, 0)
        coeff_layout.addWidget(self.coefficient_file_edit)
        coeff_layout.addWidget(coeff_browse)
        self.scheme_detail_widget = QWidget()
        scheme_detail_layout = QFormLayout(self.scheme_detail_widget)
        scheme_detail_layout.setContentsMargins(0, 0, 0, 0)
        scheme_detail_layout.addRow(self.i18n.t("coefficient_file"), coeff_row)
        experiment_form.addRow(self.i18n.t("experiment_name"), self.experiment_name_edit)
        exp_hint = QLabel(self.i18n.t("experiment_name_hint"))
        exp_hint.setStyleSheet("color: #999; font-size: 10px; padding-left: 2px;")
        experiment_form.addRow("", exp_hint)
        experiment_form.addRow(self.i18n.t("template_preset"), template_row)
        experiment_form.addRow(self.i18n.t("template_note"), self.template_description)
        experiment_form.addRow(self.i18n.t("case_preset"), self.case_preset_combo)
        experiment_form.addRow(self.i18n.t("mapping_scheme"), self.mapping_scheme_combo)
        experiment_form.addRow("", self.scheme_detail_widget)
        cards.addWidget(experiment_card, 0, 0)

        process_card = QGroupBox(self.i18n.t("process_card"))
        process_layout = QVBoxLayout(process_card)
        self.with_coag_box = QCheckBox(self.i18n.t("with_coag"))
        self.with_cond_box = QCheckBox(self.i18n.t("with_cond"))
        self.with_nucl_box = QCheckBox(self.i18n.t("with_nucl"))
        self.with_cond_box.toggled.connect(self._sync_visibility)
        self.with_nucl_box.toggled.connect(self._sync_visibility)
        process_layout.addWidget(self.with_coag_box)
        process_layout.addWidget(self.with_cond_box)
        process_layout.addWidget(self.with_nucl_box)
        self.nearest_note = QLabel(self.i18n.t("nearest_note"))
        self.nearest_note.setWordWrap(True)
        self.legacy_note = QLabel(self.i18n.t("legacy_note"))
        self.legacy_note.setWordWrap(True)
        process_layout.addWidget(self.nearest_note)
        process_layout.addWidget(self.legacy_note)
        cards.addWidget(process_card, 0, 1)

        runtime_card = QGroupBox(self.i18n.t("runtime_card"))
        runtime_form = QFormLayout(runtime_card)
        self.field_widgets["final_time_hours"] = self._double_spin(0.01, 240.0, 0.25, single_step=1.0)
        self.field_widgets["dtmin_seconds"] = self._double_spin(0.001, 3600.0, 1.0, decimals=3, single_step=1.0)
        self.output_dir_edit = QLineEdit(str(self.current_results_root))
        browse_button = QPushButton(self.i18n.t("browse"))
        browse_button.clicked.connect(self.choose_output_directory)
        out_row = QWidget()
        out_layout = QHBoxLayout(out_row)
        out_layout.setContentsMargins(0, 0, 0, 0)
        out_layout.addWidget(self.output_dir_edit)
        out_layout.addWidget(browse_button)
        runtime_form.addRow(self.i18n.t("simulation_time"), self.field_widgets["final_time_hours"])
        runtime_form.addRow(self.i18n.t("dtmin_seconds"), self.field_widgets["dtmin_seconds"])
        runtime_form.addRow(self.i18n.t("output_directory"), out_row)
        cards.addWidget(runtime_card, 0, 2)

        environment_card = QGroupBox(self.i18n.t("environment_card"))
        environment_form = QFormLayout(environment_card)
        self.field_widgets["temperature"] = self._double_spin(200.0, 400.0, 298.0, single_step=1.0)
        self.field_widgets["pressure"] = self._double_spin(10000.0, 200000.0, 101325.0, decimals=1, single_step=1000.0)
        self.field_widgets["humidity"] = self._double_spin(0.0, 1.0, 0.65, decimals=3, single_step=0.01)
        self.scenario_combo = QComboBox()
        self.scenario_combo.addItem(self.i18n.t("scenario_hazy"), 1)
        self.scenario_combo.addItem(self.i18n.t("scenario_urban"), 2)
        self.scenario_combo.addItem(self.i18n.t("scenario_clear"), 3)
        self.scenario_combo.currentIndexChanged.connect(self._sync_visibility)
        self.tag_external_box = QCheckBox(self.i18n.t("tag_external"))
        self.tag_external_box.toggled.connect(self._sync_visibility)
        self.tagrho_combo = QComboBox()
        self.tagrho_combo.addItem(self.i18n.t("use_real_density"), 1)
        self.tagrho_combo.addItem(self.i18n.t("use_fixed_density"), 0)
        self.tagrho_combo.currentTextChanged.connect(self._sync_visibility)
        self.field_widgets["fixed_density"] = self._double_spin(100.0, 5000.0, 1800.0, decimals=1, single_step=100.0)
        environment_form.addRow(self.i18n.t("temperature"), self.field_widgets["temperature"])
        environment_form.addRow(self.i18n.t("pressure"), self.field_widgets["pressure"])
        environment_form.addRow(self.i18n.t("humidity"), self.field_widgets["humidity"])
        environment_form.addRow(self.i18n.t("init_scenario"), self.scenario_combo)
        environment_form.addRow(self.i18n.t("mixing_state"), self.tag_external_box)
        environment_form.addRow(self.i18n.t("density_mode"), self.tagrho_combo)
        environment_form.addRow(self.i18n.t("fixed_density"), self.field_widgets["fixed_density"])
        cards.addWidget(environment_card, 1, 0)

        advanced_card = QGroupBox(self.i18n.t("advanced_card"))
        advanced_layout = QVBoxLayout(advanced_card)
        self.basic_mode_combo = QComboBox()
        self.basic_mode_combo.addItem(self.i18n.t("basic_mode"), "basic")
        self.basic_mode_combo.addItem(self.i18n.t("advanced_mode"), "advanced")
        self.basic_mode_combo.currentTextChanged.connect(lambda _text: self._sync_visibility())
        advanced_layout.addWidget(QLabel(self.i18n.t("view_mode")))
        advanced_layout.addWidget(self.basic_mode_combo)
        advanced_grid = QGridLayout()
        advanced_grid.setColumnStretch(0, 1)
        advanced_grid.setColumnStretch(1, 1)
        advanced_grid.setColumnStretch(2, 1)
        advanced_grid.setColumnStretch(3, 1)
        self.cond_only_widget = QWidget()
        cond_form = QFormLayout(self.cond_only_widget)
        self.field_widgets["sulfate_computation"] = self._int_spin(0, 9)
        self.field_widgets["redistribution_method"] = self._int_spin(0, 9)
        self.redistribution_option_combo = QComboBox()
        self.redistribution_option_combo.addItem(self.i18n.t("rdb_legacy"), "legacy")
        self.redistribution_option_combo.addItem(self.i18n.t("rdb_core_conserv"), "core_conserv")
        self.redistribution_option_combo.addItem(self.i18n.t("rdb_core_nogrow"), "core_nogrow")
        self.redistribution_option_combo.addItem(self.i18n.t("rdb_core_smallgrow"), "core_smallgrow")
        cond_form.addRow(self.i18n.t("sulfate_computation"), self.field_widgets["sulfate_computation"])
        cond_form.addRow(self.i18n.t("redistribution_method"), self.field_widgets["redistribution_method"])
        cond_form.addRow(self.i18n.t("redistribution_option"), self.redistribution_option_combo)
        cond_box = QGroupBox(self.i18n.t("cond_card"))
        cond_box_layout = QVBoxLayout(cond_box)
        cond_box_layout.addWidget(self.cond_only_widget)
        self.nucl_only_widget = QWidget()
        nucl_form = QFormLayout(self.nucl_only_widget)
        self.field_widgets["nucl_model"] = self._int_spin(0, 9)
        nucl_form.addRow(self.i18n.t("nucl_model"), self.field_widgets["nucl_model"])
        nucl_box = QGroupBox(self.i18n.t("nucl_card"))
        nucl_box_layout = QVBoxLayout(nucl_box)
        nucl_box_layout.addWidget(self.nucl_only_widget)
        self.external_only_widget = QWidget()
        external_form = QFormLayout(self.external_only_widget)
        self.field_widgets["n_groups"] = self._int_spin(1, 20)
        external_form.addRow(self.i18n.t("n_groups"), self.field_widgets["n_groups"])
        external_box = QGroupBox(self.i18n.t("external_card"))
        external_box_layout = QVBoxLayout(external_box)
        external_box_layout.addWidget(self.external_only_widget)

        self.grid_only_widget = QWidget()
        grid_form = QFormLayout(self.grid_only_widget)
        self.field_widgets["dynamic_solver"] = self._int_spin(0, 9)
        self.field_widgets["tag_thrm"] = self._int_spin(0, 9)
        self.field_widgets["kind_grid"] = self._int_spin(0, 9)
        self.field_widgets["kind_composition"] = self._int_spin(0, 9)
        self.field_widgets["cut_dim"] = self._double_spin(0.0, 100.0, 0.0, decimals=4, single_step=0.1)
        grid_form.addRow(self.i18n.t("dynamic_solver"), self.field_widgets["dynamic_solver"])
        grid_form.addRow(self.i18n.t("tag_thrm"), self.field_widgets["tag_thrm"])
        grid_form.addRow(self.i18n.t("kind_grid"), self.field_widgets["kind_grid"])
        grid_form.addRow(self.i18n.t("kind_composition"), self.field_widgets["kind_composition"])
        grid_form.addRow(self.i18n.t("cut_dim"), self.field_widgets["cut_dim"])
        grid_box = QGroupBox(self.i18n.t("grid_card"))
        grid_box_layout = QVBoxLayout(grid_box)
        grid_box_layout.addWidget(self.grid_only_widget)
        advanced_grid.addWidget(cond_box, 0, 0)
        advanced_grid.addWidget(nucl_box, 0, 1)
        advanced_grid.addWidget(external_box, 0, 2)
        advanced_grid.addWidget(grid_box, 0, 3)
        advanced_layout.addLayout(advanced_grid)
        cards.addWidget(advanced_card, 1, 1, 1, 2)

        layout.addLayout(cards)
        preview_card = QGroupBox(self.i18n.t("config_preview"))
        preview_layout = QVBoxLayout(preview_card)
        self.raw_preview = QPlainTextEdit()
        self.raw_preview.setReadOnly(True)
        preview_layout.addWidget(self.raw_preview)
        layout.addWidget(preview_card)
        scroll.setWidget(container)
        outer.addWidget(scroll)

    def _build_structure_tab(self) -> None:
        outer = QVBoxLayout(self.structure_tab)
        controls = QGroupBox(self.i18n.t("structure_card"))
        controls_layout = QGridLayout(controls)
        self.n_species_spin = self._int_spin(1, 200)
        self.n_sizebin_spin = self._int_spin(1, 200)
        self.n_frac_spin = self._int_spin(1, 50)
        self.generate_structure_button = QPushButton(self.i18n.t("generate_structure"))
        self.generate_structure_button.clicked.connect(self.generate_structure)
        self.rebuild_structure_button = QPushButton(self.i18n.t("rebuild_tables"))
        self.rebuild_structure_button.clicked.connect(lambda: self.refresh_structure_tables(from_widgets=True))
        self.logspace_button = QPushButton(self.i18n.t("auto_logspace"))
        self.logspace_button.clicked.connect(self.auto_fill_logspace_bounds)
        controls_layout.addWidget(QLabel(self.i18n.t("n_species")), 0, 0)
        controls_layout.addWidget(self.n_species_spin, 0, 1)
        controls_layout.addWidget(QLabel(self.i18n.t("n_sizebin")), 0, 2)
        controls_layout.addWidget(self.n_sizebin_spin, 0, 3)
        controls_layout.addWidget(QLabel(self.i18n.t("n_frac")), 0, 4)
        controls_layout.addWidget(self.n_frac_spin, 0, 5)
        controls_layout.addWidget(self.generate_structure_button, 0, 6)
        controls_layout.addWidget(self.rebuild_structure_button, 0, 7)
        controls_layout.addWidget(self.logspace_button, 0, 8)
        outer.addWidget(controls)

        structure_help_label = QLabel(self.i18n.t("structure_help"))
        structure_help_label.setWordWrap(True)
        structure_help_label.setStyleSheet("color: #666; font-size: 11px; padding: 2px 0;")
        outer.addWidget(structure_help_label)

        self.structure_tabs = QTabWidget()
        self.species_meta_table = QTableWidget()
        self.size_bins_table = QTableWidget()
        self.fraction_table = QTableWidget()
        self.emission_table = QTableWidget()
        self.initial_mass_table = QTableWidget()
        self.structure_tabs.addTab(self.species_meta_table, "")
        self.structure_tabs.addTab(self.size_bins_table, "")
        self.structure_tabs.addTab(self.fraction_table, "")
        self.structure_tabs.addTab(self.emission_table, "")
        self.structure_tabs.addTab(self.initial_mass_table, "")
        for _table in (self.species_meta_table, self.size_bins_table, self.fraction_table,
                        self.emission_table, self.initial_mass_table):
            _table.cellChanged.connect(lambda _r, _c, t=_table: self._on_table_cell_changed(t))
        outer.addWidget(self.structure_tabs)

    def _build_run_tab(self) -> None:
        layout = QVBoxLayout(self.run_tab)
        buttons = QHBoxLayout()
        self.run_button = QPushButton(self.i18n.t("single_run"))
        self.run_button.clicked.connect(self.run_single_case)
        self.compare_button = QPushButton(self.i18n.t("compare_schemes"))
        self.compare_button.clicked.connect(self.run_compare_case)
        self.stop_button = QPushButton(self.i18n.t("stop"))
        self.stop_button.clicked.connect(self.stop_run)
        buttons.addWidget(self.run_button)
        buttons.addWidget(self.compare_button)
        buttons.addWidget(self.stop_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.progress = QProgressBar()
        layout.addWidget(self.progress)

        status_card = QGroupBox(self.i18n.t("run_status"))
        status_grid = QGridLayout(status_card)
        self.monitor_labels: dict[str, QLabel] = {}
        labels = [
            ("status", 0, 0),
            ("current_case", 0, 2),
            ("current_scheme", 0, 4),
            ("current_process_combo", 1, 0),
            ("elapsed_wallclock", 1, 2),
            ("simulated_hours", 1, 4),
            ("current_step", 2, 0),
            ("eta", 2, 2),
            ("current_total_number", 3, 0),
            ("current_total_mass", 3, 2),
            ("average_diameter", 3, 4),
            ("active_bins", 4, 0),
            ("active_pairs", 4, 2),
            ("last_output_time", 4, 4),
            ("current_module", 5, 0),
            ("latest_warning", 5, 2),
            ("latest_file", 6, 0),
        ]
        for key, row, col in labels:
            title = QLabel(self.i18n.t(key))
            value = QLabel("-")
            value.setWordWrap(True)
            status_grid.addWidget(title, row, col)
            status_grid.addWidget(value, row, col + 1)
            self.monitor_labels[key] = value
        layout.addWidget(status_card)

        lower = QSplitter(Qt.Horizontal)
        self.run_status_list = QListWidget()
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        lower.addWidget(self.run_status_list)
        lower.addWidget(self.log_view)
        lower.setSizes([220, 760])
        layout.addWidget(lower)

    def _build_results_tab(self) -> None:
        layout = QVBoxLayout(self.results_tab)
        summary_card = QGroupBox(self.i18n.t("results_summary"))
        summary_layout = QGridLayout(summary_card)
        self.results_summary_labels: dict[str, QLabel] = {}
        for idx, key in enumerate(["summary_scheme", "summary_runtime", "summary_final_mass", "summary_final_number", "summary_relative_diff"]):
            title = QLabel(self.i18n.t(key))
            value = QLabel("-")
            self.results_summary_labels[key] = value
            summary_layout.addWidget(title, 0, idx * 2)
            summary_layout.addWidget(value, 0, idx * 2 + 1)
        layout.addWidget(summary_card)

        controls = QHBoxLayout()
        self.results_case_combo = QComboBox()
        self.results_case_combo.currentTextChanged.connect(self.refresh_results_summary)
        self.compare_results_button = QPushButton(self.i18n.t("compare_results"))
        self.compare_results_button.clicked.connect(self.refresh_results_summary)
        self.export_summary_button = QPushButton(self.i18n.t("export_summary_csv"))
        self.export_summary_button.clicked.connect(self.open_summary_csv)
        self.open_output_button = QPushButton(self.i18n.t("open_output"))
        self.open_output_button.clicked.connect(self.open_output_directory)
        self.open_figures_button = QPushButton(self.i18n.t("open_figures"))
        self.open_figures_button.clicked.connect(self.open_figure_directory)
        controls.addWidget(QLabel(self.i18n.t("current_case")))
        controls.addWidget(self.results_case_combo)
        controls.addWidget(self.compare_results_button)
        controls.addWidget(self.export_summary_button)
        controls.addWidget(self.open_output_button)
        controls.addWidget(self.open_figures_button)
        controls.addStretch(1)
        layout.addLayout(controls)

        splitter = QSplitter(Qt.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        self.figure_list = QListWidget()
        self.figure_list.currentTextChanged.connect(lambda name: self.preview_result_item("figure", name))
        self.csv_list = QListWidget()
        self.csv_list.currentTextChanged.connect(lambda name: self.preview_result_item("csv", name))
        self.log_list = QListWidget()
        self.log_list.currentTextChanged.connect(lambda name: self.preview_result_item("log", name))
        for title, widget in [
            (self.i18n.t("figure_list"), self.figure_list),
            (self.i18n.t("csv_list"), self.csv_list),
            (self.i18n.t("log_list"), self.log_list),
        ]:
            box = QGroupBox(title)
            box_layout = QVBoxLayout(box)
            box_layout.addWidget(widget)
            left_layout.addWidget(box)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.result_preview_title = QLabel(self.i18n.t("preview"))
        self.figure_preview = QLabel()
        self.figure_preview.setAlignment(Qt.AlignCenter)
        self.figure_preview.setMinimumHeight(360)
        self.result_text_preview = QPlainTextEdit()
        self.result_text_preview.setReadOnly(True)
        right_layout.addWidget(self.result_preview_title)
        right_layout.addWidget(self.figure_preview)
        right_layout.addWidget(self.result_text_preview)
        splitter.addWidget(right)
        splitter.setSizes([300, 900])
        layout.addWidget(splitter)

    def _build_report_tab(self) -> None:
        layout = QVBoxLayout(self.report_tab)
        report_card = QGroupBox(self.i18n.t("report_center"))
        report_form = QFormLayout(report_card)
        self.report_title_edit = QLineEdit(self.i18n.t("report_default_title"))
        self.report_results_dir = QLabel(str(self.current_results_root))
        report_form.addRow(self.i18n.t("report_title"), self.report_title_edit)
        report_form.addRow(self.i18n.t("report_results_dir"), self.report_results_dir)
        layout.addWidget(report_card)
        self.report_figure_list = QListWidget()
        layout.addWidget(self.report_figure_list)
        row = QHBoxLayout()
        self.generate_report_button = QPushButton(self.i18n.t("generate_report"))
        self.generate_report_button.clicked.connect(self.generate_report)
        self.open_tex_button = QPushButton(self.i18n.t("open_tex"))
        self.open_tex_button.clicked.connect(lambda: self.open_path(self.report_service.report_root / "internal_external_mixing_report.tex"))
        self.open_pdf_button = QPushButton(self.i18n.t("open_pdf"))
        self.open_pdf_button.clicked.connect(lambda: self.open_path(self.report_service.report_root / "internal_external_mixing_report.pdf"))
        row.addWidget(self.generate_report_button)
        row.addWidget(self.open_tex_button)
        row.addWidget(self.open_pdf_button)
        row.addStretch(1)
        layout.addLayout(row)
        self.report_status_label = QLabel(self.i18n.t("report_not_generated"))
        layout.addWidget(self.report_status_label)
        self.report_log = QTextEdit()
        self.report_log.setReadOnly(True)
        layout.addWidget(self.report_log)

    def _build_settings_tab(self) -> None:
        layout = QFormLayout(self.settings_tab)
        self.language_combo = QComboBox()
        self.language_combo.addItems(["zh_CN", "en_US"])
        self.language_combo.setCurrentText(str(self.settings["language"]))
        self.language_combo.currentTextChanged.connect(self.change_language)
        self.settings_output_edit = QLineEdit(str(self.settings["default_output_directory"]))
        settings_output_row = QWidget()
        settings_output_layout = QHBoxLayout(settings_output_row)
        settings_output_layout.setContentsMargins(0, 0, 0, 0)
        settings_output_layout.addWidget(self.settings_output_edit)
        self.settings_output_browse_button = QPushButton(self.i18n.t("browse"))
        self.settings_output_browse_button.clicked.connect(self.choose_settings_output_directory)
        settings_output_layout.addWidget(self.settings_output_browse_button)
        self.settings_ui_mode = QComboBox()
        self.settings_ui_mode.addItem(self.i18n.t("basic_mode"), "basic")
        self.settings_ui_mode.addItem(self.i18n.t("advanced_mode"), "advanced")
        current_mode = str(self.settings.get("ui_mode", "basic"))
        self.settings_ui_mode.setCurrentIndex(0 if current_mode == "basic" else 1)
        self.apply_settings_button = QPushButton(self.i18n.t("apply_settings"))
        self.apply_settings_button.clicked.connect(self.apply_settings)
        self.recent_configs_view = QPlainTextEdit("\n".join(str(item) for item in self.settings.get("recent_configs", [])))
        self.recent_configs_view.setReadOnly(True)
        layout.addRow(self.i18n.t("language"), self.language_combo)
        layout.addRow(self.i18n.t("output_directory"), settings_output_row)
        layout.addRow(self.i18n.t("view_mode"), self.settings_ui_mode)
        layout.addRow("", self.apply_settings_button)
        layout.addRow(self.i18n.t("recent_configs"), self.recent_configs_view)

    def _build_help_tab(self) -> None:
        layout = QVBoxLayout(self.help_tab)
        self.help_view = QTextEdit()
        self.help_view.setReadOnly(True)
        layout.addWidget(self.help_view)

    def refresh_all(self) -> None:
        self.setWindowTitle(self.i18n.t("app_title"))
        self.tabs.setTabText(0, self.i18n.t("experiment_setup"))
        self.tabs.setTabText(1, self.i18n.t("structure_editor"))
        self.tabs.setTabText(2, self.i18n.t("run_monitor"))
        self.tabs.setTabText(3, self.i18n.t("results_analysis"))
        next_index = 4
        if self.report_service.available():
            self.tabs.setTabText(4, self.i18n.t("report_export"))
            next_index = 5
        self.tabs.setTabText(next_index, self.i18n.t("settings"))
        self.tabs.setTabText(next_index + 1, self.i18n.t("help"))
        self._load_data_into_widgets()
        self.refresh_structure_tables()
        self.raw_preview.setPlainText(self._render_preview_text())
        self.refresh_results_assets()
        if self.report_service.available():
            self.refresh_report_assets()
        self.help_view.setPlainText(self._build_help_text())
        self.statusBar().showMessage(self.i18n.t("status_ready"))

    def _load_data_into_widgets(self) -> None:
        scalars = self.data["scalars"]
        self.experiment_name_edit.setText(str(self.data.get("experiment_name", self.data.get("template_name", "experiment"))))
        template_name = self.data.get("template_name", "tutorial_minimal")
        for idx in range(self.template_combo.count()):
            if self.template_combo.itemData(idx) == template_name:
                self.template_combo.setCurrentIndex(idx)
                break
        self._update_template_description()
        self.case_preset_combo.blockSignals(True)
        matched = self.data.get("case_preset") or ""
        idx = self.case_preset_combo.findText(matched)
        self.case_preset_combo.setCurrentIndex(idx if idx >= 0 else -1)
        self.case_preset_combo.blockSignals(False)
        self._mixing_scheme_locked = str(self.data.get("mixing_assumption", "EXTERNAL_MIXING"))
        self.mapping_scheme_combo.blockSignals(True)
        self.mapping_scheme_combo.setCurrentText(self._mixing_scheme_locked)
        self.mapping_scheme_combo.blockSignals(False)
        self.with_coag_box.setChecked(bool(int(scalars["with_coag"])))
        self.with_cond_box.setChecked(bool(int(scalars["with_cond"])))
        self.with_nucl_box.setChecked(bool(int(scalars["with_nucl"])))
        self.tag_external_box.setChecked(bool(int(scalars["tag_external"])))
        self.tagrho_combo.setCurrentIndex(0 if int(scalars["tagrho"]) == 1 else 1)
        init_sc = int(scalars.get("init_scenario", 3))
        for idx in range(self.scenario_combo.count()):
            if self.scenario_combo.itemData(idx) == init_sc:
                self.scenario_combo.setCurrentIndex(idx)
                break
        redistribution_option = str(scalars.get("redistribution_option", "core_conserv"))
        for idx in range(self.redistribution_option_combo.count()):
            if self.redistribution_option_combo.itemData(idx) == redistribution_option:
                self.redistribution_option_combo.setCurrentIndex(idx)
                break
        for key, widget in self.field_widgets.items():
            if key not in scalars:
                continue
            value = scalars[key]
            if isinstance(widget, QSpinBox):
                widget.setValue(int(value))
            elif isinstance(widget, QDoubleSpinBox):
                widget.setValue(float(value))
        self.coefficient_file_edit.setText(str(scalars["coefficient_file"]))
        self.n_species_spin.setValue(int(scalars["n_species"]))
        self.n_sizebin_spin.setValue(int(scalars["n_sizebin"]))
        self.n_frac_spin.setValue(int(scalars["n_frac"]))
        self.output_dir_edit.setText(str(self.current_results_root))
        ui_mode = str(self.settings.get("ui_mode", "basic"))
        self.basic_mode_combo.setCurrentIndex(0 if ui_mode == "basic" else 1)
        self.raw_preview.setPlainText(self._render_preview_text())
        self._sync_visibility()

    def _collect_data(self) -> dict[str, Any]:
        data = self.config_model.normalize(self.data)
        data["experiment_name"] = self.experiment_name_edit.text().strip() or "experiment"
        data["template_name"] = str(self.template_combo.currentData())
        data["case_preset"] = self.case_preset_combo.currentText()
        data["mixing_assumption"] = self.mapping_scheme_combo.currentText()
        data["mapping_scheme"] = "DETERMINISTIC_NEAREST"
        data["scalars"]["with_coag"] = 1 if self.with_coag_box.isChecked() else 0
        data["scalars"]["with_cond"] = 1 if self.with_cond_box.isChecked() else 0
        data["scalars"]["with_nucl"] = 1 if self.with_nucl_box.isChecked() else 0
        data["scalars"]["tag_external"] = 1 if self.tag_external_box.isChecked() else 0
        data["scalars"]["tagrho"] = int(self.tagrho_combo.currentData())
        data["scalars"]["init_scenario"] = int(self.scenario_combo.currentData())
        data["scalars"]["coefficient_file"] = self.coefficient_file_edit.text().strip()
        data["scalars"]["redistribution_option"] = str(self.redistribution_option_combo.currentData())
        for key, widget in self.field_widgets.items():
            if isinstance(widget, QSpinBox):
                data["scalars"][key] = widget.value()
            elif isinstance(widget, QDoubleSpinBox):
                data["scalars"][key] = widget.value()
        data["scalars"]["n_species"] = self.n_species_spin.value()
        data["scalars"]["n_sizebin"] = self.n_sizebin_spin.value()
        data["scalars"]["n_frac"] = self.n_frac_spin.value()

        species_records: list[dict[str, Any]] = []
        for row in range(self.species_meta_table.rowCount()):
            species_records.append(
                {
                    "species_id": int(self._table_text(self.species_meta_table, row, 0) or row + 1),
                    "species_name": self._table_text(self.species_meta_table, row, 1) or f"species_{row + 1}",
                    "group_id": int(self._table_text(self.species_meta_table, row, 2) or 1),
                    "init_gas": float(self._table_text(self.species_meta_table, row, 3) or 0.0),
                    "emission": float(self._table_text(self.species_meta_table, row, 4) or 0.0),
                    "notes": self._table_text(self.species_meta_table, row, 5),
                    "bin_values": [],
                }
            )
        data["species_records"] = species_records

        size_rows = []
        for row in range(self.size_bins_table.rowCount()):
            size_rows.append(
                {
                    "lower": float(self._table_text(self.size_bins_table, row, 1) or 0.0),
                    "upper": float(self._table_text(self.size_bins_table, row, 2) or 0.0),
                    "number": float(self._table_text(self.size_bins_table, row, 4) or 0.0),
                }
            )
        if size_rows:
            data["diameter_bounds"] = [size_rows[0]["lower"]] + [row["upper"] for row in size_rows]
            data["init_bin_number"] = [row["number"] for row in size_rows]

        data["fraction_bounds"] = []
        for row in range(self.fraction_table.rowCount()):
            lower = float(self._table_text(self.fraction_table, row, 1) or 0.0)
            upper = float(self._table_text(self.fraction_table, row, 2) or 0.0)
            if row == 0:
                data["fraction_bounds"].append(lower)
            data["fraction_bounds"].append(upper)

        emission_matrix: list[list[float]] = []
        n_emission_bins = max(self.emission_table.columnCount() - 2, 0)
        for row in range(self.species_meta_table.rowCount()):
            row_values: list[float] = []
            for col in range(n_emission_bins):
                row_values.append(float(self._table_text(self.emission_table, row, col + 1) or 0.0))
            emission_matrix.append(row_values)
        data["emission_matrix"] = emission_matrix
        data["init_bin_emission_species_1"] = emission_matrix[0] if emission_matrix else []
        data["init_bin_emission_species_2"] = emission_matrix[1] if len(emission_matrix) > 1 else []

        for row in range(self.initial_mass_table.rowCount()):
            values = []
            for col in range(self.initial_mass_table.columnCount()):
                values.append(float(self._table_text(self.initial_mass_table, row, col) or 0.0))
            if row < len(data["species_records"]):
                data["species_records"][row]["bin_values"] = values

        self.current_results_root = Path(self.output_dir_edit.text().strip() or str(self.current_results_root))
        self.plot_service.set_results_root(self.current_results_root)
        self.report_service.set_results_root(self.current_results_root)
        return self.config_model.normalize(data)

    def _render_preview_text(self) -> str:
        preview_path = self.run_service.generated_root / "_preview.cfg"
        snapshot = self.data if not hasattr(self, "species_meta_table") else self._collect_data()
        self.config_model.serialize(snapshot, preview_path)
        return preview_path.read_text(encoding="utf-8")

    def _on_table_cell_changed(self, _table: QTableWidget) -> None:
        """Update config preview when any structure-editor table cell is edited."""
        self.raw_preview.setPlainText(self._render_preview_text())

    def _sync_visibility(self, *_args: object) -> None:
        scheme = self.mapping_scheme_combo.currentText()
        ui_mode = self.basic_mode_combo.currentData() if hasattr(self.basic_mode_combo, "currentData") else "basic"
        with_cond = self.with_cond_box.isChecked()
        with_nucl = self.with_nucl_box.isChecked()
        external = scheme == "EXTERNAL_MIXING"
        use_fixed_density = self.tagrho_combo.currentData() == 0
        self.scheme_detail_widget.setVisible(False)
        self.nearest_note.setVisible(scheme == "EXTERNAL_MIXING")
        self.legacy_note.setVisible(scheme == "INTERNAL_MIXING")
        self.cond_only_widget.setVisible(bool(with_cond) and ui_mode == "advanced")
        self.nucl_only_widget.setVisible(bool(with_nucl) and ui_mode == "advanced")
        self.external_only_widget.setVisible(bool(external) and ui_mode == "advanced")
        self.grid_only_widget.setVisible(ui_mode == "advanced")
        self.field_widgets["fixed_density"].setVisible(use_fixed_density)
        self.basic_mode_combo.parentWidget().setVisible(True)
        self.raw_preview.setPlainText(self._render_preview_text())

    def refresh_structure_tables(self, from_widgets: bool = False) -> None:
        data = self._collect_data() if from_widgets else self.config_model.normalize(self.data)
        self.data = data
        species = data["species_records"]
        size_rows = self.config_model.size_rows(data)
        fraction_rows = self.config_model.fraction_rows(data)
        self._fill_table(
            self.species_meta_table,
            ["species_id", "species_name", "group_id", "init_gas", "emission", "notes"],
            [
                [
                    record["species_id"],
                    record["species_name"],
                    record["group_id"],
                    record["init_gas"],
                    record["emission"],
                    record["notes"],
                ]
                for record in species
            ],
        )
        self._fill_table(
            self.size_bins_table,
            ["bin_id", "lower_bound", "upper_bound", "representative_diameter", "initial_number", "notes"],
            [
                [
                    row["bin_id"],
                    row["lower_bound"],
                    row["upper_bound"],
                    row["representative_diameter"],
                    row["initial_number"],
                    row["notes"],
                ]
                for row in size_rows
            ],
        )
        self._fill_table(
            self.fraction_table,
            ["fraction_id", "lower_bound", "upper_bound", "notes"],
            [[row["fraction_id"], row["lower_bound"], row["upper_bound"], row["notes"]] for row in fraction_rows],
        )
        emission_matrix = data.get("emission_matrix", [])
        n_species = len(species)
        n_bins = len(data["init_bin_number"])
        # Remove stale cell widgets before resizing (fixes +/- button residue from previous n_bins)
        for r in range(self.emission_table.rowCount()):
            for c in range(self.emission_table.columnCount()):
                self.emission_table.removeCellWidget(r, c)
        self.emission_table.setRowCount(n_species)
        self.emission_table.setColumnCount(n_bins + 2)
        headers = [self.i18n.t("species_label")] + [f"bin_{idx + 1}" for idx in range(n_bins)] + [self.i18n.t("actions")]
        self.emission_table.setHorizontalHeaderLabels(headers)
        for row in range(n_species):
            name_item = QTableWidgetItem(str(species[row]["species_name"]))
            name_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.emission_table.setItem(row, 0, name_item)
            for col in range(n_bins):
                value = 0.0
                if row < len(emission_matrix) and col < len(emission_matrix[row]):
                    value = emission_matrix[row][col]
                self.emission_table.setItem(row, col + 1, QTableWidgetItem(str(value)))
            self.emission_table.setCellWidget(row, n_bins + 1, self._emission_actions_widget(row))

        n_size = len(data["init_bin_number"])
        self.initial_mass_table.setRowCount(len(species))
        self.initial_mass_table.setColumnCount(n_size)
        self.initial_mass_table.setHorizontalHeaderLabels([f"bin_{idx + 1}" for idx in range(n_size)])
        self.initial_mass_table.setVerticalHeaderLabels([str(record["species_name"]) for record in species])
        for row, record in enumerate(species):
            for col, value in enumerate(record["bin_values"]):
                self.initial_mass_table.setItem(row, col, QTableWidgetItem(str(value)))

        self.structure_tabs.setTabText(0, self.i18n.t("species_table"))
        self.structure_tabs.setTabText(1, self.i18n.t("size_bins_table"))
        self.structure_tabs.setTabText(2, self.i18n.t("fraction_table"))
        self.structure_tabs.setTabText(3, self.i18n.t("emission_table"))
        self.structure_tabs.setTabText(4, self.i18n.t("initial_mass_table"))

    def _emission_actions_widget(self, row: int) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        add_btn = QPushButton("+")
        remove_btn = QPushButton("-")
        add_btn.setFixedWidth(28)
        remove_btn.setFixedWidth(28)
        add_btn.clicked.connect(partial(self.add_species_row, row))
        remove_btn.clicked.connect(partial(self.remove_species_row, row))
        layout.addWidget(add_btn)
        layout.addWidget(remove_btn)
        layout.addStretch(1)
        return widget

    def add_species_row(self, row: int) -> None:
        data = self._collect_data()
        n_bins = len(data.get("init_bin_number", []))
        insert_at = min(max(row + 1, 0), len(data["species_records"]))
        new_id = insert_at + 1
        new_record = {
            "species_id": new_id,
            "species_name": f"species_{new_id}",
            "group_id": 1,
            "init_gas": 0.0,
            "emission": 0.0,
            "bin_values": [0.0] * n_bins,
            "notes": "",
        }
        data["species_records"].insert(insert_at, new_record)
        emission_row = [0.0] * n_bins
        emission_matrix = [list(row_vals) for row_vals in data.get("emission_matrix", [])]
        emission_matrix.insert(insert_at, emission_row)
        data["emission_matrix"] = emission_matrix
        data["scalars"]["n_species"] = len(data["species_records"])
        self.data = self.config_model.normalize(data)
        self.refresh_all()

    def remove_species_row(self, row: int) -> None:
        data = self._collect_data()
        if len(data["species_records"]) <= 1:
            QMessageBox.warning(self, self.i18n.t("validate_config"), self.i18n.t("cannot_remove_species"))
            return
        if 0 <= row < len(data["species_records"]):
            data["species_records"].pop(row)
        emission_matrix = [list(row_vals) for row_vals in data.get("emission_matrix", [])]
        if 0 <= row < len(emission_matrix):
            emission_matrix.pop(row)
        data["emission_matrix"] = emission_matrix
        data["scalars"]["n_species"] = len(data["species_records"])
        self.data = self.config_model.normalize(data)
        self.refresh_all()

    def generate_structure(self) -> None:
        self.data = self._collect_data()
        self.data["scalars"]["n_species"] = self.n_species_spin.value()
        self.data["scalars"]["n_sizebin"] = self.n_sizebin_spin.value()
        self.data["scalars"]["n_frac"] = self.n_frac_spin.value()
        self.data = self.config_model.normalize(self.data)
        self.refresh_all()

    def auto_fill_logspace_bounds(self) -> None:
        n_size = self.n_sizebin_spin.value()
        bounds = self.config_model._logspace_bounds(n_size)  # noqa: SLF001
        for row in range(min(self.size_bins_table.rowCount(), n_size)):
            self.size_bins_table.setItem(row, 1, QTableWidgetItem(str(bounds[row])))
            self.size_bins_table.setItem(row, 2, QTableWidgetItem(str(bounds[row + 1])))
            self.size_bins_table.setItem(row, 3, QTableWidgetItem(str(math.sqrt(bounds[row] * bounds[row + 1]))))

    def load_template(self) -> None:
        template_id = str(self.template_combo.currentData())
        self.data = self.template_service.load_template(template_id)
        self.data["experiment_name"] = template_id
        self.data["case_preset"] = self._match_case_preset(self.data)
        self.settings["last_template"] = template_id
        self.settings_service.save(self.settings)
        self.refresh_all()

    def _match_case_preset(self, data: dict[str, Any]) -> str:
        """Match process switches to the closest CASE_PRESETS entry."""
        scalars = data["scalars"]
        c, d, n = int(scalars["with_coag"]), int(scalars["with_cond"]), int(scalars["with_nucl"])
        for name, preset in CASE_PRESETS.items():
            if int(preset["with_coag"]) == c and int(preset["with_cond"]) == d and int(preset["with_nucl"]) == n:
                return name
        return ""

    def _on_mixing_scheme_changed(self, _index: int) -> None:
        """Revert any manual change to the mixing assumption combo."""
        if self._mixing_scheme_locked and self.mapping_scheme_combo.currentText() != self._mixing_scheme_locked:
            self.mapping_scheme_combo.blockSignals(True)
            self.mapping_scheme_combo.setCurrentText(self._mixing_scheme_locked)
            self.mapping_scheme_combo.blockSignals(False)
            self.statusBar().showMessage(self.i18n.t("mixing_scheme_readonly_tip"), 5000)
    def apply_case_preset(self, case_name: str) -> None:
        preset = CASE_PRESETS.get(case_name)
        if not preset:
            return
        self.with_coag_box.setChecked(bool(preset["with_coag"]))
        self.with_cond_box.setChecked(bool(preset["with_cond"]))
        self.with_nucl_box.setChecked(bool(preset["with_nucl"]))
        cast_widget = self.field_widgets.get("final_time_hours")
        if isinstance(cast_widget, QDoubleSpinBox):
            cast_widget.setValue(float(preset["duration_hours"]))
        self._sync_visibility()

    def load_config(self) -> None:
        path_text, _ = QFileDialog.getOpenFileName(self, self.i18n.t("load_config"), str(self.root / "core"), "Config (*.cfg)")
        if not path_text:
            return
        self.current_config_path = Path(path_text)
        self.data = self.config_model.parse(self.current_config_path)
        self.data["experiment_name"] = self.current_config_path.stem
        self.data["case_preset"] = self._match_case_preset(self.data)
        self.data["template_name"] = "__custom__"
        recent = [path_text] + [str(item) for item in self.settings.get("recent_configs", []) if str(item) != path_text]
        self.settings["recent_configs"] = recent[:8]
        self.settings_service.save(self.settings)
        self.refresh_all()

    def save_config(self) -> None:
        if self.current_config_path == self.config_model.default_path:
            self.save_config_as()
            return
        self.data = self._collect_data()
        target = self.current_config_path if self.current_config_path else self.run_service.generated_root / "app_saved.cfg"
        self.config_model.serialize(self.data, target)
        self.raw_preview.setPlainText(target.read_text(encoding="utf-8"))
        self.statusBar().showMessage(self.i18n.t("config_saved"))

    def save_config_as(self) -> None:
        path_text, _ = QFileDialog.getSaveFileName(self, self.i18n.t("save_as"), str(self.run_service.generated_root / "app_saved.cfg"), "Config (*.cfg)")
        if not path_text:
            return
        self.current_config_path = Path(path_text)
        self.save_config()

    def validate_config(self) -> None:
        self.data = self._collect_data()
        errors = self.config_model.validate(self.data)
        if errors:
            QMessageBox.warning(self, self.i18n.t("validate_config"), "\n".join(errors))
        else:
            QMessageBox.information(self, self.i18n.t("validate_config"), self.i18n.t("config_valid"))

    def new_from_defaults(self) -> None:
        self.data = self.template_service.load_template("gmd_paris_full")
        self.data["experiment_name"] = "gmd_paris_full"
        self.data["case_preset"] = self._match_case_preset(self.data)
        self.settings["last_template"] = "gmd_paris_full"
        self.settings_service.save(self.settings)
        self.refresh_all()

    def choose_output_directory(self) -> None:
        path_text = QFileDialog.getExistingDirectory(self, self.i18n.t("output_directory"), str(self.current_results_root))
        if path_text:
            self.current_results_root = Path(path_text)
            self.output_dir_edit.setText(path_text)
            self.settings_output_edit.setText(path_text)
            self.plot_service.set_results_root(self.current_results_root)
            self.report_service.set_results_root(self.current_results_root)
            self.settings["default_output_directory"] = path_text
            self.settings_service.save(self.settings)

    def choose_settings_output_directory(self) -> None:
        path_text = QFileDialog.getExistingDirectory(self, self.i18n.t("output_directory"), self.settings_output_edit.text())
        if path_text:
            self.settings_output_edit.setText(path_text)
            self.apply_settings()

    def apply_settings(self) -> None:
        output_text = self.settings_output_edit.text().strip()
        if output_text:
            self.current_results_root = Path(output_text).expanduser()
            self.current_results_root.mkdir(parents=True, exist_ok=True)
            self.output_dir_edit.setText(str(self.current_results_root))
            self.plot_service.set_results_root(self.current_results_root)
            self.report_service.set_results_root(self.current_results_root)
            self.settings["default_output_directory"] = str(self.current_results_root)
        self.settings["language"] = self.language_combo.currentText()
        self.settings["ui_mode"] = self.settings_ui_mode.currentData()
        self.settings_service.save(self.settings)
        self.statusBar().showMessage(self.i18n.t("settings_saved"))

    def choose_coefficient_file(self) -> None:
        path_text, _ = QFileDialog.getOpenFileName(self, self.i18n.t("coefficient_file"), str(self.root / "core"), "NetCDF (*.nc);;All (*)")
        if path_text:
            self.coefficient_file_edit.setText(Path(path_text).name if Path(path_text).parent == self.run_service.runtime_dir else path_text)

    def run_single_case(self) -> None:
        self._start_runs(compare=False)

    def run_compare_case(self) -> None:
        self._start_runs(compare=True)

    def _start_runs(self, compare: bool) -> None:
        if not self.run_service.executable_available():
            QMessageBox.critical(self, self.i18n.t("run"), self.i18n.t("runtime_missing"))
            return
        self.data = self._collect_data()
        errors = self.config_model.validate(self.data)
        if errors:
            QMessageBox.warning(self, self.i18n.t("validate_config"), "\n".join(errors))
            return
        mode_dir = "compare" if compare else "single"
        exp_name = self.experiment_name_edit.text().strip() or "experiment"
        case_name = self.case_preset_combo.currentText().strip()
        dir_name = f"{exp_name}_{case_name}" if case_name else exp_name
        output_root = self.current_results_root / mode_dir / dir_name
        output_root.mkdir(parents=True, exist_ok=True)
        self.plot_service.set_results_root(output_root)
        self.report_service.set_results_root(output_root)
        # Auto-save current config alongside the results
        auto_cfg = output_root / "experiment_config.cfg"
        self.config_model.serialize(self.data, auto_cfg)
        schemes = ("INTERNAL_MIXING", "EXTERNAL_MIXING") if compare else (self.mapping_scheme_combo.currentText(),)
        prepared_runs = [
            self.run_service.prepare_run(self.data, case_name, scheme, output_root=output_root) for scheme in schemes
        ]
        self.run_worker = RunWorker(self.run_service, prepared_runs)
        self.run_worker.stage_changed.connect(self._on_run_stage_changed)
        self.run_worker.message.connect(self._log)
        self.run_worker.completed.connect(self._on_run_completed)
        self.run_worker.failed.connect(self._on_run_failed)
        self.progress.setValue(0)
        self.run_status_list.clear()
        self.log_view.clear()
        self.run_worker.start()
        self.statusBar().showMessage(self.i18n.t("status_running"))

    def _on_run_stage_changed(self, prepared: dict[str, Any]) -> None:
        self.current_prepared = prepared
        self.current_run_started_at = time.perf_counter()
        self.monitor_timer.start(1000)
        self.monitor_labels["status"].setText(self.i18n.t("status_running"))
        self.monitor_labels["current_case"].setText(prepared["case_name"])
        self.monitor_labels["current_scheme"].setText(prepared["scheme"])
        self.monitor_labels["current_process_combo"].setText(prepared["case_name"])
        self.run_status_list.addItem(f"{prepared['case_name']} / {prepared['scheme']}")
        self.results_case_combo.setCurrentText(prepared["case_name"])

    def _on_run_completed(self, rows: list[dict[str, Any]]) -> None:
        self.monitor_timer.stop()
        self.progress.setValue(100 if rows else 0)
        self.monitor_labels["status"].setText(self.i18n.t("status_completed"))
        self.plot_service.generate_all(self.current_results_root)
        self.refresh_results_assets()
        if self.report_service.available():
            self.refresh_report_assets()
        self._log(self.i18n.t("comparison_finished") if len(rows) > 1 else self.i18n.t("run_finished"))
        self.statusBar().showMessage(self.i18n.t("comparison_finished"))

    def _on_run_failed(self, message: str) -> None:
        self.monitor_timer.stop()
        self.monitor_labels["status"].setText(self.i18n.t("status_failed"))
        self._log(message)
        self.statusBar().showMessage(self.i18n.t("status_failed"))

    def stop_run(self) -> None:
        if self.run_service.stop_current():
            self.monitor_labels["status"].setText(self.i18n.t("status_stopped"))
            self._log(self.i18n.t("status_stopped"))

    def _refresh_run_monitor(self) -> None:
        if self.current_prepared is None:
            return
        elapsed = time.perf_counter() - self.current_run_started_at
        metrics = self.run_service.read_live_metrics(Path(self.current_prepared["run_root"]), float(self.current_prepared["total_sim_seconds"]))
        simulated_hours = metrics["simulated_seconds"] / 3600.0
        eta_seconds = None
        if metrics["simulated_seconds"] > 0.0 and elapsed > 0.0:
            eta_seconds = elapsed * max(float(self.current_prepared["total_sim_seconds"]) / metrics["simulated_seconds"] - 1.0, 0.0)
        self.progress.setValue(int(metrics["progress"]))
        self.monitor_labels["elapsed_wallclock"].setText(f"{elapsed:.1f} s")
        self.monitor_labels["simulated_hours"].setText(f"{simulated_hours:.2f} h")
        self.monitor_labels["current_step"].setText(
            f"{metrics['timestep']} / ~{max(1, int(float(self.current_prepared['total_sim_seconds']) / max(self.field_widgets['dtmin_seconds'].value(), 1.0e-6)))}"
        )
        self.monitor_labels["eta"].setText("-" if eta_seconds is None else f"{eta_seconds:.1f} s")
        self.monitor_labels["current_total_number"].setText(self._fmt(metrics["current_total_number"]))
        self.monitor_labels["current_total_mass"].setText(self._fmt(metrics["current_total_mass"]))
        self.monitor_labels["average_diameter"].setText(self._fmt(metrics["average_diameter"]))
        self.monitor_labels["active_bins"].setText(str(metrics["active_bins"]))
        self.monitor_labels["active_pairs"].setText(str(metrics["active_pairs"]))
        self.monitor_labels["last_output_time"].setText(str(metrics["last_output_time"]))
        self.monitor_labels["current_module"].setText(str(metrics["current_module"]))
        self.monitor_labels["latest_warning"].setText(str(metrics["latest_warning"]))
        self.monitor_labels["latest_file"].setText(str(metrics["latest_file"]))

    def refresh_results_assets(self) -> None:
        self.plot_service.set_results_root(self.current_results_root)
        self.results_case_combo.blockSignals(True)
        self.results_case_combo.clear()
        runs_root = self.current_results_root / "runs"
        if runs_root.exists():
            for case_dir in sorted(runs_root.glob("*")):
                if case_dir.is_dir():
                    self.results_case_combo.addItem(case_dir.name)
        if self.results_case_combo.count() == 0:
            self.results_case_combo.addItem(self.case_preset_combo.currentText())
        preferred = self.case_preset_combo.currentText()
        index = self.results_case_combo.findText(preferred)
        self.results_case_combo.setCurrentIndex(index if index >= 0 else 0)
        self.results_case_combo.blockSignals(False)
        self.refresh_results_lists_for_case(self.results_case_combo.currentText())
        self.refresh_results_summary()

    def refresh_results_lists_for_case(self, case_name: str) -> None:
        self.figure_list.clear()
        self.csv_list.clear()
        self.log_list.clear()
        for path in sorted((self.current_results_root / "figures").glob(f"{case_name}*.png")):
            self.figure_list.addItem(path.name)
        summary_path = self.current_results_root / "final_state_summary.csv"
        perf_path = self.current_results_root / "performance_summary.csv"
        if summary_path.exists():
            self.csv_list.addItem(summary_path.name)
        if perf_path.exists():
            self.csv_list.addItem(perf_path.name)
        for path in sorted((self.current_results_root / "runs" / case_name).glob("*/csv/*.csv")):
            self.csv_list.addItem(str(path.relative_to(self.current_results_root)))
        for path in sorted((self.current_results_root / "runs" / case_name).glob("*/logs/run.log")):
            self.log_list.addItem(str(path.relative_to(self.current_results_root)))
        if self.figure_list.count():
            self.figure_list.setCurrentRow(0)
        elif self.csv_list.count():
            self.csv_list.setCurrentRow(0)

    def refresh_results_summary(self) -> None:
        case_name = self.results_case_combo.currentText()
        self.refresh_results_lists_for_case(case_name)
        summary_path = self.current_results_root / "final_state_summary.csv"
        if not summary_path.exists():
            return
        rows = [row for row in csv.DictReader(summary_path.open()) if row["case_name"] == case_name]
        if not rows:
            return
        external = next((row for row in rows if row["scheme"] == "EXTERNAL_MIXING"), rows[0])
        internal = next((row for row in rows if row["scheme"] == "INTERNAL_MIXING"), rows[0])
        self.results_summary_labels["summary_scheme"].setText("INTERNAL vs EXTERNAL")
        self.results_summary_labels["summary_runtime"].setText(self._runtime_summary(case_name))
        self.results_summary_labels["summary_final_mass"].setText(f"I {float(internal['final_total_mass']):.4f} / E {float(external['final_total_mass']):.4f}")
        self.results_summary_labels["summary_final_number"].setText(f"I {float(internal['final_total_number']):.3e} / E {float(external['final_total_number']):.3e}")
        self.results_summary_labels["summary_relative_diff"].setText(
            f"M {100.0 * float(internal['relative_difference_vs_external_mass']):.2f}% / N {100.0 * float(internal['relative_difference_vs_external_number']):.2f}%"
        )

    def refresh_report_assets(self) -> None:
        if not self.report_service.available():
            return
        self.report_results_dir.setText(str(self.current_results_root))
        self.report_figure_list.clear()
        for path in sorted((self.current_results_root / "figures").glob("*.png")):
            item = QListWidgetItem(path.name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.report_figure_list.addItem(item)

    def preview_result_item(self, kind: str, name: str) -> None:
        if not name:
            return
        self.result_preview_title.setText(name)
        if kind == "figure":
            path = self.current_results_root / "figures" / name
            pixmap = QPixmap(str(path))
            self.figure_preview.setPixmap(pixmap.scaled(900, 480, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.result_text_preview.setPlainText(path.name)
        elif kind == "csv":
            path = self.current_results_root / name
            self.figure_preview.clear()
            self.result_text_preview.setPlainText(path.read_text(encoding="utf-8", errors="replace") if path.exists() else "")
        else:
            path = self.current_results_root / name
            self.figure_preview.clear()
            self.result_text_preview.setPlainText(path.read_text(encoding="utf-8", errors="ignore") if path.exists() else "")

    def generate_report(self) -> None:
        selected = []
        for idx in range(self.report_figure_list.count()):
            item = self.report_figure_list.item(idx)
            if item.checkState() == Qt.Checked:
                selected.append(item.text())
        self.report_service.set_results_root(self.current_results_root)
        self.report_status_label.setText(self.i18n.t("report_generating"))
        self.statusBar().showMessage(self.i18n.t("report_generating"))
        try:
            tex_path, pdf_path = self.report_service.generate(selected)
        except Exception as exc:
            message = str(exc)
            self.report_log.append(message)
            self.report_status_label.setText(self.i18n.t("report_failed"))
            self.statusBar().showMessage(self.i18n.t("report_failed"))
            QMessageBox.critical(self, self.i18n.t("generate_report"), message)
            return
        self.report_log.append(f"Generated {tex_path}")
        self.report_log.append(f"Generated {pdf_path}")
        if self.report_service.last_backend_message:
            self.report_log.append(self.report_service.last_backend_message)
        self.report_status_label.setText(self.i18n.t("report_generated"))
        self.statusBar().showMessage(self.i18n.t("report_generated"))

    def change_language(self, language: str) -> None:
        self.data = self._collect_data()
        self.i18n.set_language(language)
        self.settings["language"] = language
        self.settings_service.save(self.settings)
        self._rebuild_ui()
        self.refresh_all()

    def open_output_directory(self) -> None:
        self.open_path(self.current_results_root)

    def open_figure_directory(self) -> None:
        self.open_path(self.current_results_root / "figures")

    def open_summary_csv(self) -> None:
        self.open_path(self.current_results_root / "final_state_summary.csv")

    def open_path(self, path: Path) -> None:
        if not path.exists():
            return
        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)

    def _open_report_tab(self) -> None:
        if self.report_service.available():
            self.tabs.setCurrentWidget(self.report_tab)

    def _update_template_description(self) -> None:
        template_id = str(self.template_combo.currentData())
        if template_id == "__custom__":
            self.template_description.setText(self.i18n.t("custom_config_desc"))
            return
        template = self.template_service.template_by_id(template_id)
        text = template["description_zh"] if self.i18n.language.startswith("zh") else template["description_en"]
        self.template_description.setText(text)

    def _build_help_text(self) -> str:
        return self._build_mixing_help_text()

    def _build_mixing_help_text(self) -> str:
        if self.i18n.language.startswith("zh"):
            return f"""SCRAM（Size-Composition-Resolved-Simulator）
版本号：{self.app_version}

一、软件定位
本软件用于把 SCRAM box model 封装成可直接操作的桌面程序，重点比较 internal mixing 与 external mixing 两种气溶胶混合状态假设。internal mixing 把同一粒径段的颗粒看作平均组成；external mixing 继续区分不同组成区间，因此可以分析 mixed / unmixed 颗粒比例和组成差异。

二、顶部工具栏与运行
1. 新建实验：恢复到默认教学模板。
2. 运行：运行当前选中的混合假设。
3. 停止：尝试停止正在运行的核心程序。
4. 查看结果：切换到结果分析页。
5. 导出报告：切换到报告页并生成 PDF 报告。
6. 比较 internal / external：在运行监控页点击「比较」按钮，连续运行两种混合假设并生成对比图和 final_state_summary.csv。

   输出归档规则：
   - 运行结果按「实验名称_案例预设」存入 single/ 或 compare/ 子目录。
   - 载入配置后实验名称自动设为配置文件名；运行前可手动修改。
   - 同名实验再次运行会覆盖历史结果，请区分命名。
   - 无论「运行」还是「比较」，都会自动保存实验配置到结果目录下的 experiment_config.cfg。
   - 案例预设会根据载入配置的实际过程开关（凝并/冷凝/成核）自动匹配。

三、实验设置页
1. 模板/预设：选择教学案例、GMD hazy 验证案例或 Greater Paris A/B/C/D 参考场景。
2. 混合假设：选择 INTERNAL_MIXING 或 EXTERNAL_MIXING。
3. 凝并 / 冷凝 / 成核：决定是否启用对应物理过程。
4. 模拟时长和最小时间步：控制积分长度和时间步下限。
5. 输出目录：显示当前实验结果根目录。

四、结构编辑页
先设定组分数、粒径分段数和质量分数分段数（顶行三个数字框），点击
「生成结构」创建表格。编辑表格数值后，左侧 config_preview 自动刷新；
点击「重建表格」可将当前表格值同步回内部数据模型。

⚠️ 「生成结构」会清空并重建所有表格。如果修改了 n_sizebin（粒径分段数）
或 n_frac（质量分数分段数），diameter_bounds（粒径边界）和 fraction_bounds
（分数边界）将重置为默认等间距值，之前手动调整的数据会丢失。

五个子表格：

(1) Species 表（n_species 行 × 6 列）
  - 每行一个化学组分：编号、名称、组别、初始气相浓度(µg/m³)、排放率、备注。
  - 增加 n_species：末尾追加空行，默认值全为零。
  - 减少 n_species：末尾多余行被截断丢弃。

(2) Size bins 表（n_sizebin 行 × 6 列）
  - 每行一个粒径段：编号、下界(µm)、上界(µm)、代表粒径、初始数浓度(#/m³)、备注。
  - 粒径边界按对数间距自动生成；可手动编辑单个边界值。
  - 增加 n_sizebin：diameter_bounds 重算，初始数浓度末尾补 1000。
  - 减少 n_sizebin：末尾行截断，diameter_bounds 重算。

(3) Fraction 表（n_frac 行 × 4 列）
  - 每行一个质量分数区间（仅 external mixing 使用）：编号、下界、上界、备注。
  - 默认均匀分割 [0, 1]；可手动编辑为不均匀区间。
  - 增加/减少 n_frac：均分重算边界（手动编辑的值会丢失）。
  - Greater Paris 案例示例：0-0.2、0.2-0.8、0.8-1.0 三个区间。

(4) Emission 表（n_species 行 × (n_sizebin+2) 列）
  - 各组分×各粒径段的排放率矩阵。第 1 列为组分名（只读），
    末列为操作按钮（+ 在上方插入新物种，− 删除当前行；至少保留 1 个物种）。
  - 增加/减少 n_species：行数跟随，多删少补零。
  - 增加/减少 n_sizebin：数据列数跟随，多删少补零。

(5) 初始质量表（n_species 行 × n_sizebin 列）
  - 各组分×各粒径段的初始质量浓度矩阵。纯数据，无额外列。
  - 增加/减少 n_species：行数跟随，多删少补零。
  - 增加/减少 n_sizebin：列数跟随，多删少补零。

五、运行监控页
运行时显示当前案例、混合假设、wall-clock、模拟时间、步数、ETA、总 number、总 mass、平均粒径、active bins、active pairs、最近日志和警告。

六、结果分析页
结果页会按当前实验过滤图、CSV 和日志。摘要卡片显示 internal 与 external 的终态质量、终态数量、运行时间差异；结果图还会给出 external mixed fraction 和不同粒径段中的 mixed/unmixed 质量分布。

七、推荐实验
1. GMD hazy 冷凝验证：验证 internal/external 在总粒径分布上的一致性。
2. Greater Paris 场景 A：排放。
3. Greater Paris 场景 B：排放 + 凝并。
4. Greater Paris 场景 C：排放 + 冷凝/蒸发。
5. Greater Paris 场景 D：排放 + 凝并 + 冷凝/蒸发 + 成核。

八、典型流程
选择“GMD Greater Paris scenario D”，点击“比较 internal / external”，等待两组运行结束；进入结果页查看总质量/总数量曲线、相对 external 差异、external mixed fraction 和粒径-混合状态分布；最后在报告页导出 PDF。
"""
        return f"""SCRAM (Size-Composition-Resolved-Simulator)
Version: {self.app_version}

1. Purpose
This desktop app wraps SCRAM as a workflow-oriented GUI for comparing internal mixing and external mixing assumptions. Internal mixing uses one average composition per size bin. External mixing resolves composition sections and can therefore diagnose mixed and unmixed particle populations.

2. Toolbar and Running
- New Experiment: reset to the default teaching template.
- Run: run the selected mixing assumption.
- Stop: stop the active process.
- View Results: open the results analysis tab.
- Export Report: open the report tab and generate a PDF.
- Compare internal / external: click "Compare" on the Run Monitor tab to run both assumptions and generate comparison figures and final_state_summary.csv.

  Output archiving:
  - Results are saved as 「experiment_name_case_preset」 under single/ or compare/.
  - Loading a config sets the experiment name to the config filename; rename before running.
  - Reusing the same experiment name overwrites previous results — use distinct names.
  - Both Run and Compare auto-save the config as experiment_config.cfg in the output directory.
  - The case preset is auto-matched from the loaded config's actual process switches.

3. Experiment Setup
- Template / Preset: teaching, GMD hazy validation, or Greater Paris reference cases.
- Mixing Assumption: INTERNAL_MIXING or EXTERNAL_MIXING.
- Coagulation / Condensation / Nucleation: process toggles.
- Simulation Time and Minimum Timestep: integration controls.
- Output Directory: current experiment result root.

4. Structure Editor
Set species count, size bins, and fraction sections (top-row spinboxes), then click
"Generate Structure" to create tables. Editing cell values updates the config preview
in real time. "Rebuild Tables" syncs current table values back to the internal data model.

⚠️ "Generate Structure" clears and recreates all tables. Changing n_sizebin or n_frac
resets diameter_bounds and fraction_bounds to default evenly-spaced values; any
manually edited boundary values will be lost.

Five Sub-tables:

(1) Species Table (n_species rows × 6 columns)
  - One chemical species per row: ID, name, group, initial gas (µg/m³), emission, notes.
  - Increasing n_species: append empty rows (all zeros) at the end.
  - Decreasing n_species: truncate extra rows from the end.

(2) Size Bins Table (n_sizebin rows × 6 columns)
  - One size bin per row: ID, lower bound (µm), upper bound, representative diameter,
    initial number (#/m³), notes. Bounds are auto-generated on a log scale.
  - Increasing n_sizebin: regenerates diameter_bounds, appends 1000 to init numbers.
  - Decreasing n_sizebin: truncates end rows, regenerates diameter_bounds.

(3) Fraction Table (n_frac rows × 4 columns)
  - One mass-fraction section per row (external mixing only): ID, lower, upper, notes.
  - Default evenly spaced [0, 1]; can be manually edited to non-uniform intervals.
  - Changing n_frac: evenly respaces bounds (manual edits will be lost).
  - Greater Paris example: 0–0.2, 0.2–0.8, 0.8–1.0 (three sections).

(4) Emission Table (n_species rows × (n_sizebin+2) columns)
  - Emission rate matrix: species × size bins. Column 1 = species name (read-only),
    last column = action buttons (+ insert species above, − delete current row;
    at least 1 species must remain).
  - Changing n_species: rows follow, truncated/padded with zeros.
  - Changing n_sizebin: data columns follow, truncated/padded with zeros.

(5) Initial Mass Table (n_species rows × n_sizebin columns)
  - Initial mass concentration matrix: species × size bins. Pure data, no extra columns.
  - Changing n_species: rows follow, truncated/padded with zeros.
  - Changing n_sizebin: columns follow, truncated/padded with zeros.

5. Run Monitor
Shows case, assumption, progress, ETA, total number, total mass, mean diameter, active bins, active pairs, logs, and warnings.

6. Results Analysis
Figures and CSV files are filtered by experiment. Summary cards compare internal and external final mass, number, and runtime; external results include mixed fraction and mixed/unmixed mass by size.

7. Recommended Workflow
Choose GMD Greater Paris scenario D, run the internal/external comparison, inspect the generated figures, and export the PDF report.
"""

    def _log(self, message: str) -> None:
        self.log_view.append(message)

    def _fill_table(self, table: QTableWidget, headers: list[str], rows: list[list[Any]]) -> None:
        table.blockSignals(True)
        table.setColumnCount(len(headers))
        table.setRowCount(len(rows))
        table.setHorizontalHeaderLabels(headers)
        for row_idx, row in enumerate(rows):
            for col_idx, value in enumerate(row):
                table.setItem(row_idx, col_idx, QTableWidgetItem(str(value)))
        table.resizeColumnsToContents()
        table.blockSignals(False)

    def _table_text(self, table: QTableWidget, row: int, col: int) -> str:
        item = table.item(row, col)
        return item.text().strip() if item else ""

    def _double_spin(
        self,
        minimum: float,
        maximum: float,
        value: float,
        decimals: int = 6,
        single_step: float | None = None,
    ) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(decimals)
        spin.setValue(value)
        spin.setSingleStep(single_step if single_step is not None else max((maximum - minimum) / 100.0, 0.001))
        return spin

    def _int_spin(self, minimum: int, maximum: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        return spin

    def _fmt(self, value: float) -> str:
        return "-" if math.isnan(value) else f"{value:.4e}"

    def _runtime_summary(self, case_name: str) -> str:
        path = self.current_results_root / "performance_summary.csv"
        if not path.exists():
            return "-"
        rows = [row for row in csv.DictReader(path.open()) if row["case_name"] == case_name]
        if not rows:
            return "-"
        return " / ".join(f"{row['scheme']} {float(row['wallclock']):.2f}s" for row in rows)
