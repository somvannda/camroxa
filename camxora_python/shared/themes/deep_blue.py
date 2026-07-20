"""Deep blue compact theme for Camxora.

Professional dark theme inspired by AutoDistroKid — native PySide6 widgets
styled via Fusion + QSS. Not a full custom design system; standard Qt controls
with a consistent deep-blue palette.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

MAIN_STYLESHEET = """
/* Global */
QWidget {
    background-color: #020617;
    color: #e0e0e0;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 9pt;
}

QWidget[shellPage="true"],
QScrollArea[shellPage="true"] {
    background-color: #020617;
}

QWidget#shell_content_host,
QWidget#shell_content_inner,
QStackedWidget#shell_page_stack {
    background-color: #020617;
}

QFrame#startup_page {
    background-color: #020617;
}

QFrame#startup_loading_card {
    background-color: rgba(139, 92, 246, 0.12);
    border: 1px solid rgba(167, 139, 250, 0.28);
    border-radius: 10px;
}

QFrame#startup_progress_track {
    background-color: rgba(255, 255, 255, 0.1);
    border: none;
    border-radius: 4px;
    min-height: 8px;
    max-height: 8px;
}

QFrame#startup_progress_fill {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 #7c3aed,
        stop: 1 #d946ef
    );
    border: none;
    border-radius: 4px;
    min-height: 8px;
    max-height: 8px;
}

/* Main Window — transparent so only window_surface paints the opaque shell */
QMainWindow {
    background: transparent;
}

QWidget#window_surface {
    background-color: #0f1923;
    border: 1px solid rgba(255, 255, 255, 0.06);
}

QWidget#window_surface[roundedCorners="true"] {
    border-radius: 8px;
}

QFrame#shell_sidebar {
    background-color: #050a1d;
    border-right: 1px solid rgba(255, 255, 255, 0.1);
}

QFrame#shell_sidebar QWidget#shell_nav_section,
QFrame#shell_sidebar QLabel {
    background: transparent;
    border: none;
}

QFrame#setup_notification_dropdown {
    background: transparent;
    border: none;
}

QLabel#notification_panel_title {
    background: transparent;
    border: none;
    color: #f8fafc;
    font-size: 16pt;
    font-weight: 600;
}

QLabel#notification_panel_subtitle {
    background: transparent;
    border: none;
    color: #94a3b8;
    font-size: 9pt;
}

QLabel#notification_group_title {
    background: transparent;
    border: none;
    color: #e2e8f0;
    font-size: 10pt;
    font-weight: 600;
    padding-top: 8px;
    padding-bottom: 4px;
}

QLabel#notification_item_title {
    background: transparent;
    border: none;
    color: #f1f5f9;
    font-size: 10pt;
    font-weight: 600;
}

QLabel#notification_item_message {
    background: transparent;
    border: none;
    color: #94a3b8;
    font-size: 9pt;
}

QLabel#notification_item_timestamp {
    background: transparent;
    border: none;
    color: #64748b;
    font-size: 8pt;
    padding-top: 2px;
}

QLabel#notification_empty_state {
    background: transparent;
    border: none;
    color: #64748b;
    font-size: 10pt;
    padding: 28px 12px;
}

QFrame#notification_divider {
    background-color: rgba(255, 255, 255, 0.08);
    border: none;
    max-height: 1px;
    min-height: 1px;
}

QWidget#notification_row {
    background: transparent;
    border: none;
}

QScrollArea#notification_scroll,
QWidget#notification_list_host {
    background: transparent;
    border: none;
}

QScrollArea#notification_scroll::viewport {
    background: transparent;
    border: none;
}

QScrollArea#notification_scroll QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 0 2px 0 0;
}

QScrollArea#notification_scroll QScrollBar::handle:vertical {
    background-color: #2a4a6c;
    border-radius: 3px;
    min-height: 24px;
}

QScrollArea#notification_scroll QScrollBar::handle:vertical:hover {
    background-color: #3b82b0;
}

QScrollArea#notification_scroll QScrollBar::add-page:vertical,
QScrollArea#notification_scroll QScrollBar::sub-page:vertical,
QScrollArea#notification_scroll QScrollBar::add-line:vertical,
QScrollArea#notification_scroll QScrollBar::sub-line:vertical {
    background: transparent;
    border: none;
    height: 0px;
}

QPushButton#notification_action_button {
    background-color: #1a3a5c;
    color: #e2e8f0;
    border: 1px solid #2d4f73;
    border-radius: 6px;
    padding: 4px 10px;
    margin-top: 4px;
}

QPushButton#notification_action_button:hover {
    background-color: #23486d;
    border-color: #4ac0ff;
}

QFrame#software_update_gate {
    background-color: rgba(2, 6, 23, 0.92);
    border: none;
}

QFrame#software_update_card {
    background-color: #0b1224;
    border: 1px solid rgba(74, 192, 255, 0.22);
    border-radius: 16px;
}

QLabel#software_update_logo {
    background: transparent;
    border: none;
}

QLabel#software_update_brand {
    background: transparent;
    border: none;
    color: #e2e8f0;
    font-size: 11pt;
    font-weight: 600;
    letter-spacing: 0.4px;
}

QLabel#software_update_title {
    background: transparent;
    border: none;
    color: #4ac0ff;
    font-size: 16pt;
    font-weight: 700;
}

QLabel#software_update_body {
    background: transparent;
    border: none;
    color: #94a3b8;
    font-size: 10pt;
    line-height: 1.35;
}

QLabel#software_update_versions {
    background: transparent;
    border: none;
    color: #64748b;
    font-size: 9pt;
}

QLabel#software_update_section {
    background: transparent;
    border: none;
    color: #cbd5e1;
    font-size: 9pt;
    font-weight: 600;
    margin-top: 4px;
}

QLabel#software_update_whats_new {
    background: transparent;
    border: none;
    color: #94a3b8;
    font-size: 9pt;
}

QLabel#software_update_status {
    background: transparent;
    border: none;
    color: #94a3b8;
    font-size: 9pt;
}

QProgressBar#software_update_progress {
    background-color: rgba(255, 255, 255, 0.08);
    border: none;
    border-radius: 4px;
    min-height: 8px;
    max-height: 8px;
    text-align: center;
}

QProgressBar#software_update_progress::chunk {
    background-color: #4ac0ff;
    border-radius: 4px;
}

QPushButton#software_update_primary {
    background-color: #1a6afe;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 10px 16px;
    font-size: 10pt;
    font-weight: 600;
    min-height: 40px;
}

QPushButton#software_update_primary:hover {
    background-color: #2a7aff;
}

QPushButton#software_update_primary:pressed {
    background-color: #1558d6;
}

QPushButton#software_update_primary:disabled {
    background-color: #1a2a3c;
    color: #5a6a7a;
}

QFrame#window_title_bar {
    background-color: #060b20;
    border: none;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

QLabel#window_brand_logo {
    background: transparent;
    border: none;
}

QLabel#window_brand_title {
    background: transparent;
    border: none;
    color: #ffffff;
}

QLabel#window_brand_subtitle {
    background: transparent;
    border: none;
    color: #64748b;
}

/* Buttons - Compact */
QPushButton {
    background-color: #1a3a5c;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 5px 12px;
    font-size: 9pt;
    min-height: 18px;
}

QPushButton:hover {
    background-color: #2a5a8c;
}

QPushButton:pressed {
    background-color: #0d2a4c;
}

QPushButton:disabled {
    background-color: #1a2a3c;
    color: #5a6a7a;
}

QPushButton#start_button {
    background-color: #00a86b;
    font-weight: bold;
    padding: 6px 16px;
}

QPushButton#start_button:hover {
    background-color: #00c88b;
}

QPushButton#stop_button {
    background-color: #c0392b;
}

QPushButton#stop_button:hover {
    background-color: #e74c3c;
}

QPushButton#nav_button {
    background-color: transparent;
    color: #c0c0c0;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 10px 12px;
    text-align: left;
    min-height: 20px;
    font-size: 9pt;
    font-weight: 500;
}

QPushButton#nav_button:hover {
    background-color: rgba(244, 63, 94, 0.1);
    border-color: rgba(244, 63, 94, 0.1);
    color: #fecdd3;
}

QPushButton#nav_button:checked {
    background-color: rgba(139, 92, 246, 0.15);
    border-color: rgba(167, 139, 250, 0.3);
    color: #ffffff;
}

QPushButton#nav_button:checked:hover {
    background-color: rgba(139, 92, 246, 0.22);
    border-color: rgba(167, 139, 250, 0.45);
    color: #ffffff;
}

/* Tree/Album List */
QTreeWidget, QScrollArea > QWidget, QListWidget {
    background-color: #0f1923;
    border: none;
}

QListWidget::item {
    padding: 6px 8px;
    border-radius: 3px;
    color: #c0c0c0;
}

QListWidget::item:selected {
    background-color: #1a3a5c;
    color: #4ac0ff;
}

QListWidget::item:hover {
    background-color: #1a2a3c;
}

QFrame#page_header, QFrame#account_card, QFrame#settings_footer {
    background-color: #1a2a3c;
    border: 1px solid #2a4a6c;
    border-radius: 4px;
}

QFrame#progress_detail_card {
    background-color: #1a2a3c;
    border: 1px solid #2a4a6c;
    border-radius: 4px;
    padding: 2px;
}

QFrame#history_batch_separator {
    background-color: rgba(139, 92, 246, 0.12);
    border-top: 1px solid rgba(139, 92, 246, 0.22);
    border-bottom: 1px solid rgba(139, 92, 246, 0.22);
}

QFrame#shell_logout_wrap {
    background: transparent;
    border-top: 1px solid rgba(255, 255, 255, 0.1);
}

QPushButton#shell_logout_button {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    color: #fda4af;
    padding: 10px 12px;
    min-height: 20px;
    text-align: left;
    font-size: 9pt;
    font-weight: 500;
}

QPushButton#shell_logout_button:hover {
    background-color: rgba(244, 63, 94, 0.1);
    border-color: rgba(244, 63, 94, 0.1);
    color: #fecdd3;
}

QPushButton#shell_logout_button:pressed {
    background-color: rgba(244, 63, 94, 0.14);
}

QFrame#shell_footer_bar {
    background-color: #060b20;
    border-top: 1px solid rgba(255, 255, 255, 0.1);
}

QLabel#shell_footer_message {
    color: #94a3b8;
    font-size: 8pt;
}

QLabel#shell_footer_message[tone="success"] {
    color: #a7f3d0;
}

QLabel#shell_footer_message[tone="error"] {
    color: #fecdd3;
}

QLabel#shell_footer_metric {
    color: #94a3b8;
    font-size: 8pt;
}

QLabel#shell_footer_env_badge,
QLabel#shell_footer_version_badge {
    color: #7dd3fc;
    font-size: 8pt;
    padding: 2px 8px;
    border-radius: 4px;
    background-color: rgba(56, 189, 248, 0.12);
}

QFrame#settings_footer_success {
    background-color: #0f3d32;
    border: 1px solid #10b981;
    border-radius: 6px;
}

QFrame#settings_footer_success QLabel,
QFrame#settings_footer_success QLabel#settings_footer_status {
    color: #d1fae5;
    background: transparent;
    border: none;
    padding: 0;
    border-radius: 0;
}

QFrame#settings_footer_warning {
    background-color: #3d2e0a;
    border: 1px solid #fbbf24;
    border-radius: 6px;
}

QFrame#settings_footer_warning QLabel,
QFrame#settings_footer_warning QLabel#settings_footer_status {
    color: #fef3c7;
    background: transparent;
    border: none;
    padding: 0;
    border-radius: 0;
}

QFrame#settings_footer_error {
    background-color: #3d1518;
    border: 1px solid #f87171;
    border-radius: 6px;
}

QFrame#settings_footer_error QLabel,
QFrame#settings_footer_error QLabel#settings_footer_status {
    color: #fecdd3;
    background: transparent;
    border: none;
    padding: 0;
    border-radius: 0;
}

QScrollArea#panel_scroll_area {
    background-color: transparent;
    border: none;
}

QScrollArea#panel_scroll_area::viewport,
QScrollArea#panel_scroll_area > QWidget {
    background-color: transparent;
    border: none;
}

QWidget#panel_scroll_content {
    background-color: transparent;
}

/* Thin "1-line" vertical scroll used by Video panel scrolls
   (make_panel_scroll_area / make_scrollable_tab_page). Same path for Music + Settings. */
QScrollArea#panel_scroll_area QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 0px;
    border: none;
}

QScrollArea#panel_scroll_area QScrollBar::handle:vertical {
    background-color: #2a4a6c;
    border-radius: 3px;
    min-height: 24px;
}

QScrollArea#panel_scroll_area QScrollBar::handle:vertical:hover {
    background-color: #4ac0ff;
}

QScrollArea#panel_scroll_area QScrollBar::add-page:vertical,
QScrollArea#panel_scroll_area QScrollBar::sub-page:vertical,
QScrollArea#panel_scroll_area QScrollBar::add-line:vertical,
QScrollArea#panel_scroll_area QScrollBar::sub-line:vertical {
    background: transparent;
    border: none;
    height: 0px;
}

QScrollArea#panel_scroll_area QScrollBar:horizontal {
    background: transparent;
    height: 6px;
    margin: 0px;
    border: none;
}

QScrollArea#panel_scroll_area QScrollBar::handle:horizontal {
    background-color: #2a4a6c;
    border-radius: 3px;
    min-width: 24px;
}

QScrollArea#panel_scroll_area QScrollBar::handle:horizontal:hover {
    background-color: #4ac0ff;
}

QScrollArea#panel_scroll_area QScrollBar::add-page:horizontal,
QScrollArea#panel_scroll_area QScrollBar::sub-page:horizontal,
QScrollArea#panel_scroll_area QScrollBar::add-line:horizontal,
QScrollArea#panel_scroll_area QScrollBar::sub-line:horizontal {
    background: transparent;
    border: none;
    width: 0px;
}

QWidget#settings_form_row,
QWidget#settings_path_row {
    background-color: transparent;
}

/* Flat nested hosts inside settings panels — global QWidget #020617 otherwise
   paints dark bands behind pack labels, Publish-at rows, and Suno columns. */
QFrame#account_card .QWidget {
    background-color: transparent;
}

QPushButton#settings_secondary_button {
    background-color: transparent;
    border: 1px solid #2a4a6c;
    color: #e0e0e0;
    padding: 4px 10px;
}

QPushButton#settings_secondary_button:hover {
    background-color: #1a2a3c;
    border-color: #4ac0ff;
}

QPushButton#settings_secondary_button:pressed {
    background-color: #0f1923;
}

QPushButton#settings_secondary_button:disabled {
    background-color: transparent;
    border-color: #1a2a3c;
    color: #5a6a7a;
}

QFrame#profile_identity_strip {
    background-color: #0f1923;
    border: 1px solid #2a4a6c;
    border-radius: 6px;
}

QFrame#profile_identity_avatar {
    background-color: rgba(255, 255, 255, 0.06);
    border: 1px solid #2a4a6c;
    border-radius: 24px;
}

QFrame#music_section {
    background-color: #0f1923;
    border: none;
}

QDateEdit#shell_date_edit {
    background-color: #0f1923;
    border: 1px solid #2a4a6c;
    border-radius: 3px;
    padding: 4px 8px;
    color: #e0e0e0;
    min-height: 24px;
}

QDateEdit#shell_date_edit:focus {
    border-color: #4ac0ff;
}

QTextEdit#shell_text_edit {
    background-color: #0f1923;
    border: 1px solid #2a4a6c;
    border-radius: 3px;
    padding: 4px 8px;
    color: #e0e0e0;
    font-size: 9pt;
    selection-background-color: #1a6afe;
}

QTextEdit#shell_text_edit:focus {
    border-color: #4ac0ff;
}

QFrame#dashboard_error_banner {
    background-color: rgba(244, 63, 94, 0.1);
    border: 1px solid rgba(244, 63, 94, 0.25);
    border-radius: 6px;
}

QLabel#dashboard_error_text {
    color: #fecdd3;
    font-size: 9pt;
}

QFrame#dashboard_plan_badge, QFrame#dashboard_quota_summary, QFrame#dashboard_chart_panel {
    background-color: #081028;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
}

QFrame#dashboard_chart_canvas {
    background-color: transparent;
    border: none;
}

/* ── Global badge / pill system (soft tonal fills) ──
   Non-clickable QLabel chips: soft fill + colored text, no border, no glow.
   ~5px radius. Inset owned by apply_badge_pill contentsMargins (14×3).
   Tone variants change fill + text only. No unicode icons. */
QLabel#badge_role,
QLabel#badge_stage,
QLabel#badge_success,
QLabel#badge_warning,
QLabel#badge_danger,
QLabel#badge_info,
QLabel#badge_muted,
QLabel#status_pill,
QLabel#status_pill_success,
QLabel#status_pill_warning,
QLabel#workflow_header_pill,
QLabel#workflow_pill_done,
QLabel#workflow_pill_running,
QLabel#workflow_pill_partial,
QLabel#workflow_pill_failed,
QLabel#workflow_pill_neutral,
QLabel#workflow_lane_role_pill,
QLabel#workflow_lane_status_pill,
QLabel#workflow_summary_chip,
QLabel#workflow_step_badge_done,
QLabel#workflow_step_badge_running,
QLabel#workflow_step_badge_partial,
QLabel#workflow_step_badge_failed,
QLabel#workflow_step_badge_inactive {
    min-height: 18px;
    /* All inset is apply_badge_pill contentsMargins (QLabel QSS padding stacks poorly). */
    padding-top: 0;
    padding-bottom: 0;
    padding-left: 0;
    padding-right: 0;
    margin: 0;
    border-radius: 5px;
    border: none;
    background-color: #243040;
    color: #c8d4e0;
    font-size: 8pt;
    font-weight: 600;
    letter-spacing: 0.2px;
}

/* Role / neutral — Primary, Secondary (slate) */
QLabel#badge_role,
QLabel#status_pill,
QLabel#workflow_header_pill,
QLabel#workflow_pill_neutral,
QLabel#workflow_lane_role_pill {
    background-color: #243040;
    color: #c8d4e0;
}

/* Muted / idle — Ready, Not started, Waiting, Not connected */
QLabel#badge_muted,
QLabel#workflow_lane_status_pill,
QLabel#workflow_summary_chip,
QLabel#workflow_step_badge_inactive {
    background-color: #1c2633;
    color: #8b9bab;
}

/* Stage / focus — Converter, Merger, Music, Image, … (sky tint) */
QLabel#badge_stage {
    background-color: #1a2e42;
    color: #93c5fd;
}

/* Success — Done, Completed, Uploaded, Verified, Connected (teal/green) */
QLabel#badge_success,
QLabel#status_pill_success,
QLabel#workflow_pill_done,
QLabel#workflow_step_badge_done {
    background-color: #16352c;
    color: #6ee7b7;
}

/* Warning — Partial (amber tint) */
QLabel#badge_warning,
QLabel#status_pill_warning,
QLabel#workflow_pill_partial,
QLabel#workflow_step_badge_partial {
    background-color: #2d2614;
    color: #fbbf24;
}

/* Danger — Failed / Error (rose tint) */
QLabel#badge_danger,
QLabel#workflow_pill_failed,
QLabel#workflow_step_badge_failed {
    background-color: #2d1c22;
    color: #fda4af;
}

/* Info / in progress — active work (sky/cyan tint) */
QLabel#badge_info,
QLabel#workflow_pill_running,
QLabel#workflow_step_badge_running {
    background-color: #1a2c3c;
    color: #7dd3fc;
}

/* Solid high-contrast action chips (optional CTA statuses) */
QLabel#badge_solid_success {
    min-height: 18px;
    padding-top: 0;
    padding-bottom: 0;
    padding-left: 0;
    padding-right: 0;
    margin: 0;
    border-radius: 5px;
    border: none;
    font-size: 8pt;
    font-weight: 600;
    background-color: #16352c;
    color: #6ee7b7;
}

QLabel#badge_solid_danger {
    min-height: 18px;
    padding-top: 0;
    padding-bottom: 0;
    padding-left: 0;
    padding-right: 0;
    margin: 0;
    border-radius: 5px;
    border: none;
    font-size: 8pt;
    font-weight: 600;
    background-color: #2d1c22;
    color: #fda4af;
}

/* Stage-card badges keep uppercase labels; same padding as global family */
QLabel#workflow_step_badge_done,
QLabel#workflow_step_badge_running,
QLabel#workflow_step_badge_partial,
QLabel#workflow_step_badge_failed,
QLabel#workflow_step_badge_inactive {
    font-size: 7.5pt;
    font-weight: 700;
    text-transform: uppercase;
    padding-top: 0;
    padding-bottom: 0;
    padding-left: 0;
    padding-right: 0;
    min-height: 18px;
}

QLabel#footer_status_error {
    color: #fca5a5;
    font-size: 8pt;
}

QPushButton#workflow_lane {
    background-color: rgba(15, 23, 42, 0.4);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    text-align: left;
    padding: 0;
}

QPushButton#workflow_lane:hover {
    border-color: rgba(255, 255, 255, 0.2);
    background-color: rgba(255, 255, 255, 0.05);
}

QPushButton#workflow_lane_attention {
    background-color: rgba(244, 63, 94, 0.04);
    border: 1px solid rgba(244, 63, 94, 0.2);
    border-radius: 12px;
    text-align: left;
    padding: 0;
}

QPushButton#workflow_lane_attention:hover {
    border-color: rgba(244, 63, 94, 0.35);
    background-color: rgba(244, 63, 94, 0.08);
}

QPushButton#workflow_lane_selected {
    background-color: rgba(56, 189, 248, 0.12);
    border: 1px solid rgba(56, 189, 248, 0.45);
    border-radius: 12px;
    text-align: left;
    padding: 0;
}

QFrame#workflow_empty_panel {
    background-color: rgba(2, 6, 23, 0.35);
    border: 1px dashed rgba(255, 255, 255, 0.1);
    border-radius: 16px;
    min-height: 120px;
}

QFrame#workflow_selected_header {
    background-color: rgba(217, 70, 239, 0.04);
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

QFrame#workflow_step_done {
    background-color: rgba(0, 168, 107, 0.08);
    border: 1px solid rgba(0, 168, 107, 0.35);
    border-radius: 12px;
}

QFrame#workflow_step_running {
    background-color: rgba(56, 189, 248, 0.08);
    border: 1px solid rgba(56, 189, 248, 0.4);
    border-radius: 12px;
}

QFrame#workflow_step_partial {
    background-color: rgba(251, 191, 36, 0.07);
    border: 1px solid rgba(251, 191, 36, 0.32);
    border-radius: 12px;
}

QFrame#workflow_step_failed {
    background-color: rgba(244, 63, 94, 0.08);
    border: 1px solid rgba(244, 63, 94, 0.4);
    border-radius: 12px;
}

QFrame#workflow_step_inactive {
    background-color: rgba(148, 163, 184, 0.08);
    border: 1px solid rgba(148, 163, 184, 0.22);
    border-radius: 12px;
}

QLabel#workflow_step_awaiting {
    background-color: rgba(0, 0, 0, 0.15);
    border: 1px dashed rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    padding: 6px 8px;
    color: inherit;
    font-size: 8pt;
}

QProgressBar#workflow_step_bar {
    background-color: rgba(255, 255, 255, 0.1);
    border: none;
    border-radius: 4px;
    max-height: 8px;
    min-height: 8px;
}

QProgressBar#workflow_step_bar::chunk {
    background-color: currentColor;
    border-radius: 4px;
}

QFrame#workflow_filter_card,
QFrame#workflow_empty_card {
    background-color: #1a2a3c;
    border: 1px solid #2a4a6c;
    border-radius: 6px;
}

QDateEdit#workflow_date_edit {
    min-height: 32px;
    max-height: 32px;
    padding: 0 8px;
    font-size: 9pt;
    background-color: rgba(2, 6, 23, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    color: #f1f5f9;
}

QDateEdit#workflow_date_edit:focus {
    border-color: rgba(255, 255, 255, 0.2);
}

QPushButton#workflow_inline_toggle {
    background-color: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    color: #cbd5e1;
    padding: 0 10px;
    font-size: 8pt;
    text-align: left;
}

QPushButton#workflow_inline_toggle_pressed {
    background-color: rgba(217, 70, 239, 0.12);
    border: 1px solid rgba(217, 70, 239, 0.35);
    border-radius: 10px;
    color: #fae8ff;
    padding: 0 10px;
    font-size: 8pt;
    text-align: left;
}

QPushButton#workflow_refresh_button {
    background-color: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    color: #cbd5e1;
    padding: 0 10px;
    font-size: 8pt;
}

QLabel#workflow_field_label {
    color: #94a3b8;
    font-size: 8pt;
}

QLabel#workflow_helper_text {
    color: #64748b;
    font-size: 8pt;
    line-height: 1.4;
    margin-top: 2px;
}

QLabel#workflow_empty_title {
    color: #ffffff;
    font-size: 9pt;
    font-weight: 600;
}

QLabel#workflow_empty_subtitle {
    color: #94a3b8;
    font-size: 8pt;
}

QFrame#workflow_selected_card {
    background-color: #0a1218;
    border: 1px solid #1a2838;
    border-radius: 8px;
}

QLabel#workflow_eyebrow {
    color: #94a3b8;
    font-size: 8pt;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}

QLabel#workflow_channel_title {
    color: #ffffff;
    font-size: 16pt;
    font-weight: 600;
}

QLabel#workflow_run_meta {
    color: #94a3b8;
    font-size: 9pt;
}

QLabel#workflow_focus_text {
    color: #e2e8f0;
    font-size: 9pt;
    line-height: 1.6;
}

QFrame#workflow_pipeline_badge {
    background-color: rgba(2, 6, 23, 0.45);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
}

QLabel#workflow_pipeline_value {
    color: #f1f5f9;
    font-size: 9pt;
    font-weight: 500;
}

QFrame#workflow_metric_tile {
    background-color: rgba(2, 6, 23, 0.45);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
}

QLabel#workflow_metric_label {
    color: #64748b;
    font-size: 8pt;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}

QLabel#workflow_metric_value {
    color: #ffffff;
    font-size: 9pt;
    font-weight: 500;
}

QFrame#workflow_detail_panel {
    background-color: #081028;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
}

QLabel#workflow_section_label {
    color: #64748b;
    font-size: 8pt;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}

QLabel#workflow_detail_text {
    color: #cbd5e1;
    font-size: 9pt;
    line-height: 1.6;
}

QLabel#workflow_detail_muted {
    color: #64748b;
    font-size: 8pt;
}

QLabel#workflow_lane_list_title {
    color: #ffffff;
    font-size: 10pt;
    font-weight: 600;
}

QLabel#workflow_lane_list_subtitle {
    color: #94a3b8;
    font-size: 8pt;
}

QLabel#workflow_lane_channel {
    color: #ffffff;
    font-size: 9pt;
    font-weight: 500;
}

QLabel#workflow_lane_meta,
QLabel#workflow_lane_metrics,
QLabel#workflow_lane_notes {
    color: #94a3b8;
    font-size: 8pt;
}

QFrame#workflow_step_icon_wrap {
    background-color: rgba(255, 255, 255, 0.1);
    border-radius: 20px;
}

QLabel#workflow_step_title {
    color: #f8fafc;
    font-size: 9pt;
    font-weight: 600;
}

QLabel#workflow_step_duration,
QLabel#workflow_step_percent,
QLabel#workflow_step_detail {
    color: #cbd5e1;
    font-size: 8pt;
}

QListWidget#workflow_lane_list {
    background-color: #0f1923;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 4px;
    outline: none;
}

QListWidget#workflow_lane_list::item {
    padding: 10px 10px;
    border-radius: 4px;
    color: #e2e8f0;
    min-height: 44px;
}

QListWidget#workflow_lane_list::item:selected {
    background-color: #1a3a5c;
    color: #4ac0ff;
}

QListWidget#workflow_lane_list::item:hover {
    background-color: #1a2a3c;
}

QTreeWidget::item {
    padding: 4px;
    border-bottom: 1px solid #1a2a3c;
}

QTreeWidget::item:selected {
    background-color: #1a3a5c;
}

QTreeWidget::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #3a5a7c;
    border-radius: 3px;
    background-color: #0f1923;
}

QTreeWidget::indicator:checked {
    background-color: #1a8afe;
    border-color: #1a8afe;
}

/* Progress Bar */
QProgressBar {
    background-color: #1a2a3c;
    border: none;
    border-radius: 3px;
    text-align: center;
    color: #ffffff;
    font-size: 8pt;
    min-height: 16px;
    max-height: 16px;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #1a6afe, stop:1 #4a9afe);
    border-radius: 2px;
}

/* Log Text */
QTextEdit {
    background-color: #0a1218;
    color: #8aa0b0;
    border: 1px solid #1a2a3c;
    border-radius: 4px;
    padding: 4px;
    font-family: 'Consolas', monospace;
    font-size: 8pt;
    selection-background-color: #1a3a5c;
}

/* Labels - Clean.
   Keep this generic rule BEFORE badge ID chrome if reordering; badge objectNames
   re-assert background/border below so transparent does not wipe pills. */
QLabel {
    color: #c0c0c0;
    background: transparent;
}

/* Keep QSS badge padding at 0 after generic QLabel rule.
   Real inset is apply_badge_pill(setContentsMargins(14,3,14,3)). */
QLabel#badge_role,
QLabel#badge_stage,
QLabel#badge_success,
QLabel#badge_warning,
QLabel#badge_danger,
QLabel#badge_info,
QLabel#badge_muted,
QLabel#badge_solid_success,
QLabel#badge_solid_danger,
QLabel#status_pill,
QLabel#status_pill_success,
QLabel#status_pill_warning,
QLabel#workflow_header_pill,
QLabel#workflow_pill_done,
QLabel#workflow_pill_running,
QLabel#workflow_pill_partial,
QLabel#workflow_pill_failed,
QLabel#workflow_pill_neutral,
QLabel#workflow_lane_role_pill,
QLabel#workflow_lane_status_pill,
QLabel#workflow_summary_chip,
QLabel#workflow_step_badge_done,
QLabel#workflow_step_badge_running,
QLabel#workflow_step_badge_partial,
QLabel#workflow_step_badge_failed,
QLabel#workflow_step_badge_inactive {
    padding-top: 0;
    padding-bottom: 0;
    padding-left: 0;
    padding-right: 0;
}

QLabel#title {
    font-size: 14pt;
    font-weight: bold;
    color: #4ac0ff;
}

QLabel#subtitle {
    color: #6a8a9a;
    font-size: 8pt;
}

QLabel#settings_footer_status {
    color: #6a8a9a;
    font-size: 8pt;
    background: transparent;
    border: none;
    padding: 0;
    border-radius: 0;
}

/* Line Edit */
QLineEdit {
    background-color: #1a2a3c;
    border: 1px solid #2a4a6c;
    border-radius: 3px;
    padding: 4px 8px;
    color: #e0e0e0;
    selection-background-color: #1a6afe;
}

QLineEdit:focus {
    border-color: #4ac0ff;
}

/* Combo Box */
QComboBox {
    background-color: #1a2a3c;
    border: 1px solid #2a4a6c;
    border-radius: 3px;
    padding: 4px 8px;
    color: #e0e0e0;
    min-width: 80px;
}

QComboBox:hover {
    border-color: #4ac0ff;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox::down-arrow {
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #4ac0ff;
}

QComboBox QAbstractItemView {
    background-color: #1a2a3c;
    border: 1px solid #2a4a6c;
    color: #e0e0e0;
    selection-background-color: #1a6afe;
}

/* Check Box */
QCheckBox {
    spacing: 6px;
    color: #c0c0c0;
    background: transparent;
}

QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #3a5a7c;
    border-radius: 3px;
    background-color: #0f1923;
}

QCheckBox::indicator:checked {
    background-color: #1a8afe;
    border-color: #1a8afe;
}

/* Slider — thin single-line track + cyan circular thumb (Music / Video / Settings). */
QSlider {
    background: transparent;
    border: none;
}

QSlider::groove:horizontal {
    border: none;
    height: 4px;
    background-color: #4a6480;
    border-radius: 2px;
}

/* Same opaque color as the groove so Fusion add/sub pages don’t wipe the track
   (transparent pages sat over the groove and vanished on #0b1622-ish panels). */
QSlider::sub-page:horizontal,
QSlider::add-page:horizontal {
    background-color: #4a6480;
    border: none;
    height: 4px;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background-color: #4ac0ff;
    border: none;
    width: 12px;
    height: 12px;
    margin: -4px 0;
    border-radius: 6px;
}

QSlider::handle:horizontal:hover {
    background-color: #6ad0ff;
}

QSlider::handle:horizontal:disabled {
    background-color: #3a5a7c;
}

QSlider::groove:horizontal:disabled,
QSlider::sub-page:horizontal:disabled,
QSlider::add-page:horizontal:disabled {
    background-color: #314858;
}

/* Tab Widget */
QTabWidget::pane {
    border: 1px solid #1a2a3c;
    background-color: #0f1923;
}

QTabBar::tab {
    background-color: #1a2a3c;
    color: #6a8a9a;
    padding: 6px 16px;
    border: none;
    border-bottom: 2px solid transparent;
    margin-right: 2px;
}

QTabBar::tab:selected {
    color: #4ac0ff;
    border-bottom: 2px solid #4ac0ff;
}

QTabBar::tab:hover {
    color: #8ac0ff;
}

/* Scroll Bar — same thin "1-line" handle as #panel_scroll_area (Video rails). */
QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 0px;
    border: none;
}

QScrollBar::handle:vertical {
    background-color: #2a4a6c;
    border-radius: 3px;
    min-height: 24px;
}

QScrollBar::handle:vertical:hover {
    background-color: #4ac0ff;
}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical,
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    background: transparent;
    border: none;
    height: 0px;
}

QScrollBar:horizontal {
    background: transparent;
    height: 6px;
    margin: 0px;
    border: none;
}

QScrollBar::handle:horizontal {
    background-color: #2a4a6c;
    border-radius: 3px;
    min-width: 24px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #4ac0ff;
}

QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal,
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    background: transparent;
    border: none;
    width: 0px;
}

/* Menu Bar */
QMenuBar {
    background-color: #0f1923;
    color: #c0c0c0;
    border-bottom: 1px solid #1a2a3c;
    padding: 2px;
}

QMenuBar::item:selected {
    background-color: #1a3a5c;
}

QMenu {
    background-color: #1a2a3c;
    border: 1px solid #2a4a6c;
    color: #c0c0c0;
    padding: 4px;
}

QMenu::item:selected {
    background-color: #1a6afe;
}

/* Status Bar */
QStatusBar {
    background-color: #0a1218;
    color: #5a7a8a;
    border-top: 1px solid #1a2a3c;
    font-size: 8pt;
}

/* Splitter */
QSplitter::handle {
    background-color: #1a2a3c;
}

QSplitter::handle:hover {
    background-color: #4ac0ff;
}

/* Group Box - Clean */
QGroupBox {
    border: none;
    border-radius: 0px;
    margin-top: 8px;
    padding-top: 8px;
    font-weight: bold;
    color: #4ac0ff;
    background: transparent;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
}

/* Frame - Clean */
QFrame {
    border: none;
    background: transparent;
}

/* Table Widget */
QTableWidget#data_table {
    background-color: #0a1218;
    alternate-background-color: #101c28;
    border: 1px solid #2a4a6c;
    gridline-color: #1a2a3c;
    color: #e0e0e0;
}

QTableWidget#data_table::item:selected {
    background-color: #1a3a5c;
    color: #4ac0ff;
}

QTableWidget#history_data_table {
    background-color: #0a1218;
    alternate-background-color: #0a1218;
    selection-background-color: rgba(217, 70, 239, 0.12);
    selection-color: #f0e8ff;
    gridline-color: #1a2a3c;
    border: 1px solid #2a4a6c;
    show-decoration-selected: 0;
}

QTableWidget#history_data_table::item {
    background-color: transparent;
    color: #e0e0e0;
    padding: 2px 8px;
    border: none;
    outline: none;
}

QTableWidget#history_data_table::item:hover {
    background-color: rgba(255, 255, 255, 0.05);
}

QTableWidget#history_data_table::item:selected,
QTableWidget#history_data_table::item:selected:active,
QTableWidget#history_data_table::item:focus {
    background-color: transparent;
    color: #f0e8ff;
    border: none;
    outline: none;
}

QPushButton#history_open_button {
    background-color: #1a3a5c;
    color: #d8e8f8;
    border: 1px solid #2a4a6c;
    border-radius: 3px;
    padding: 1px 8px;
    font-size: 8pt;
    min-height: 18px;
    max-height: 20px;
}

QPushButton#history_open_button:hover {
    background-color: #2a5a8c;
}

QPushButton#history_open_button:pressed {
    background-color: #0d2a4c;
}

QPushButton#history_open_button:disabled {
    background-color: #121c28;
    color: #5a6a7a;
    border-color: #1a2a3c;
}

QHeaderView::section {
    background-color: #1a2a3c;
    color: #8aa0b0;
    border: none;
    border-bottom: 1px solid #2a4a6c;
    padding: 6px 8px;
}

QToolTip {
    background-color: #1a3a5c;
    color: #e0e0e0;
    border: 1px solid #4ac0ff;
    border-radius: 3px;
    padding: 4px;
    font-size: 8pt;
}

/* Card-panel selects: same dark field fill as Progress filter/table-adjacent
   QComboBoxes (shell date / Electron Progress selects — not transparent).
   Spins stay transparent so Settings Suno/Publish rows don't regain dark slabs. */
QFrame#account_card QComboBox {
    background-color: #0f1923;
    border: 1px solid #2a4a6c;
    min-height: 28px;
    padding: 2px 8px;
}

/* Styling QSpinBox without ::up/down subcontrols hides Fusion steppers. */
QFrame#account_card QSpinBox,
QFrame#account_card QDoubleSpinBox {
    background-color: transparent;
    border: 1px solid #2a4a6c;
    padding-right: 18px;
    min-height: 28px;
}

QFrame#account_card QSpinBox::up-button,
QFrame#account_card QDoubleSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 16px;
    border-left: 1px solid #2a4a6c;
    border-bottom: 1px solid #2a4a6c;
    background-color: #1a2a3c;
}

QFrame#account_card QSpinBox::down-button,
QFrame#account_card QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 16px;
    border-left: 1px solid #2a4a6c;
    background-color: #1a2a3c;
}

QFrame#account_card QSpinBox::up-button:hover,
QFrame#account_card QDoubleSpinBox::up-button:hover,
QFrame#account_card QSpinBox::down-button:hover,
QFrame#account_card QDoubleSpinBox::down-button:hover {
    background-color: #2a4a6c;
}

QFrame#account_card QSpinBox::up-arrow,
QFrame#account_card QDoubleSpinBox::up-arrow {
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid #4ac0ff;
}

QFrame#account_card QSpinBox::down-arrow,
QFrame#account_card QDoubleSpinBox::down-arrow {
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #4ac0ff;
}

QFrame#account_card QComboBox QAbstractItemView {
    background-color: #0f1923;
    border: 1px solid #2a4a6c;
}

/* Video workspace — flat inner rows/labels; keep account_card section panels */
QWidget#video_workspace {
    background-color: transparent;
}

QWidget#video_workspace > QWidget {
    background-color: transparent;
}

/* Main card sections keep the panel fill; nested sub-cards use the darker base */
QWidget#video_workspace QFrame#account_card {
    background-color: #1a2a3c;
    border: 1px solid #2a4a6c;
    border-radius: 4px;
}

QWidget#video_workspace QFrame#account_card QFrame#account_card {
    background-color: #0f1923;
    border: 1px solid #2a4a6c;
    border-radius: 4px;
}

/* .QWidget = exact class only (plain container hosts), so buttons/inputs keep
   their global styling while layout rows stay flat on the card background. */
QWidget#video_workspace QFrame#account_card .QWidget,
QWidget#video_workspace QFrame#account_card QCheckBox,
QWidget#video_workspace QFrame#account_card QSlider {
    background-color: transparent;
    border: none;
}

QWidget#video_workspace QLabel {
    background-color: transparent;
    border: none;
}

/* Card action buttons (Install ZIP, Reload, ...) match the primary Save button */
QWidget#video_workspace QPushButton#settings_secondary_button {
    background-color: #1a3a5c;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 5px 12px;
}

QWidget#video_workspace QPushButton#settings_secondary_button:hover {
    background-color: #2a5a8c;
}

QWidget#video_workspace QPushButton#settings_secondary_button:pressed {
    background-color: #0d2a4c;
}

QWidget#video_workspace QPushButton#settings_secondary_button:disabled {
    background-color: #1a2a3c;
    color: #5a6a7a;
}

QWidget#video_workspace QLineEdit,
QWidget#video_workspace QComboBox,
QWidget#video_workspace QTextEdit {
    background-color: transparent;
    border: 1px solid #2a4a6c;
}

/* Export queue fields — compact Tier/Speed/FPS/Workers. */
QFrame#video_export_fields {
    background-color: transparent;
    border: none;
}

QFrame#video_export_fields QComboBox,
QFrame#video_export_fields QSpinBox,
QFrame#video_export_fields QDoubleSpinBox {
    background-color: #0f1923;
    border: 1px solid #2a4a6c;
    border-radius: 3px;
    min-height: 22px;
    max-height: 24px;
    min-width: 100px;
    padding: 0px 4px;
    padding-right: 18px;
    color: #e0e0e0;
    font-size: 8.5pt;
}

QFrame#video_export_fields QComboBox::drop-down {
    border: none;
    width: 18px;
}

QFrame#video_export_fields QSpinBox,
QFrame#video_export_fields QDoubleSpinBox {
    padding-right: 16px;
}

QFrame#video_export_fields QComboBox QAbstractItemView {
    background-color: #0f1923;
    border: 1px solid #2a4a6c;
    color: #e0e0e0;
    outline: none;
    min-width: 140px;
    font-size: 8.5pt;
}

QFrame#video_export_fields QComboBox QAbstractItemView::item {
    min-height: 20px;
    padding: 2px 6px;
}

QWidget#video_workspace QComboBox QAbstractItemView {
    background-color: #0f1923;
    border: 1px solid #2a4a6c;
}

QWidget#video_workspace QTabWidget::pane {
    background-color: transparent;
    border: none;
}

QWidget#video_workspace QTabBar::tab {
    background-color: transparent;
    border: none;
    border-bottom: 2px solid transparent;
}

QWidget#video_workspace QTabBar::tab:selected {
    background-color: transparent;
    border-bottom: 2px solid #4ac0ff;
}

QWidget#video_workspace QScrollArea,
QWidget#video_workspace QScrollArea::viewport,
QWidget#video_workspace QScrollArea > QWidget {
    background-color: transparent;
    border: none;
}

QWidget#video_workspace QProgressBar {
    background-color: transparent;
    border: 1px solid #2a4a6c;
}

QWidget#video_workspace QProgressBar::chunk {
    background-color: #1a6afe;
}

QWidget#video_workspace QGroupBox {
    background-color: transparent;
    border: none;
}
"""

COLORS = {
    "bg_dark": "#0f1923",
    "bg_medium": "#1a2a3c",
    "bg_light": "#1a3a5c",
    "border": "#2a4a6c",
    "accent": "#4ac0ff",
    "primary": "#1a6afe",
    "success": "#00a86b",
    "danger": "#c0392b",
    "text": "#e0e0e0",
    "text_muted": "#5a7a8a",
    "text_dim": "#3a5a6a",
}

# Object names for styled action buttons (set via QWidget.setObjectName)
START_BUTTON_ID = "start_button"
STOP_BUTTON_ID = "stop_button"
TITLE_LABEL_ID = "title"
SUBTITLE_LABEL_ID = "subtitle"
MUSIC_SECTION_ID = "music_section"
SUCCESS_STATUS_PILL_ID = "status_pill_success"
WARNING_STATUS_PILL_ID = "status_pill_warning"
# Canonical badge/pill IDs — see shared.themes.badge_pills
BADGE_ROLE_ID = "badge_role"
BADGE_STAGE_ID = "badge_stage"
BADGE_SUCCESS_ID = "badge_success"
BADGE_WARNING_ID = "badge_warning"
BADGE_DANGER_ID = "badge_danger"
BADGE_INFO_ID = "badge_info"
BADGE_MUTED_ID = "badge_muted"
BADGE_SOLID_SUCCESS_ID = "badge_solid_success"
BADGE_SOLID_DANGER_ID = "badge_solid_danger"
FOOTER_ERROR_STATUS_ID = "footer_status_error"
SETTINGS_FOOTER_ID = "settings_footer"
SETTINGS_FOOTER_STATUS_ID = "settings_footer_status"
SETTINGS_FOOTER_SUCCESS_ID = "settings_footer_success"
SETTINGS_FOOTER_WARNING_ID = "settings_footer_warning"
SETTINGS_FOOTER_ERROR_ID = "settings_footer_error"
SHELL_DATE_EDIT_ID = "shell_date_edit"
SHELL_TEXT_EDIT_ID = "shell_text_edit"
PANEL_SCROLL_AREA_ID = "panel_scroll_area"
PANEL_SCROLL_CONTENT_ID = "panel_scroll_content"
# Keep form controls clear of the vertical scrollbar (matches Video panel scrolls).
PANEL_SCROLL_RIGHT_GUTTER_PX = 14
# Thin "1-line" scrollbar track width (Video / Music / Settings panel scrolls).
PANEL_SCROLLBAR_WIDTH_PX = 6
PANEL_SCROLLBAR_HANDLE = "#2a4a6c"
PANEL_SCROLLBAR_HANDLE_HOVER = "#4ac0ff"
PROFILE_IDENTITY_STRIP_ID = "profile_identity_strip"
PROFILE_IDENTITY_AVATAR_ID = "profile_identity_avatar"
SETTINGS_FORM_ROW_ID = "settings_form_row"
SETTINGS_PATH_ROW_ID = "settings_path_row"
SETTINGS_SECONDARY_BUTTON_ID = "settings_secondary_button"
VIDEO_WORKSPACE_ID = "video_workspace"


def apply_theme(app: QApplication | None = None) -> None:
    """Apply Fusion style and the deep blue stylesheet to the application."""
    if app is None:
        app = QApplication.instance()
    if app is None:
        return
    app.setStyle("Fusion")
    app.setStyleSheet(MAIN_STYLESHEET)
