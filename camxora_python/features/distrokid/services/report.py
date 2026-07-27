"""
Automation Report Module

Tracks issues encountered during form automation — element resolution failures,
missed fields, unexpected page states, and blockers. Saves a structured JSON
report after each run so you can review what went wrong and improve the automation.
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class AutomationIssue:
    """A single issue encountered during automation."""

    timestamp: str
    severity: str          # "warning", "error", "blocker"
    category: str          # "element_not_found", "field_missed", "unexpected_state", "timeout", "interaction_failed"
    step: str              # Which questionnaire step was running
    description: str       # Human-readable description
    element: str = ""      # Element that was being targeted
    strategies_tried: list = field(default_factory=list)
    page_url: str = ""
    suggestion: str = ""   # Suggested fix or next step


@dataclass
class AutomationReport:
    """Complete report for a single automation run."""

    album_name: str
    started_at: str
    finished_at: str = ""
    success: bool = False
    total_steps_attempted: int = 0
    total_steps_completed: int = 0
    issues: list = field(default_factory=list)

    @property
    def blockers(self) -> list:
        return [i for i in self.issues if i.get("severity") == "blocker" or (isinstance(i, dict) and i.get("severity") == "blocker")]

    @property
    def warnings(self) -> list:
        return [i for i in self.issues if i.get("severity") == "warning" or (isinstance(i, dict) and i.get("severity") == "warning")]

    @property
    def errors(self) -> list:
        return [i for i in self.issues if i.get("severity") == "error" or (isinstance(i, dict) and i.get("severity") == "error")]

    @property
    def has_issues(self) -> bool:
        return len(self.issues) > 0

    def summary(self) -> str:
        """Generate a human-readable summary."""
        lines = [
            f"=== Automation Report: {self.album_name} ===",
            f"Status: {'SUCCESS' if self.success else 'FAILED'}",
            f"Steps: {self.total_steps_completed}/{self.total_steps_attempted}",
            f"Issues: {len(self.issues)} total "
            f"({len(self.blockers)} blockers, {len(self.errors)} errors, {len(self.warnings)} warnings)",
        ]
        if self.issues:
            lines.append("")
            lines.append("Issues encountered:")
            for i, issue in enumerate(self.issues, 1):
                sev = issue.get("severity", "?")
                cat = issue.get("category", "?")
                desc = issue.get("description", "?")
                step = issue.get("step", "?")
                lines.append(f"  {i}. [{sev.upper()}] {step}: {desc}")
                suggestion = issue.get("suggestion", "")
                if suggestion:
                    lines.append(f"     → Suggestion: {suggestion}")
        return "\n".join(lines)


class AutomationReporter:
    """Collects and persists automation issues during a run.

    Usage:
        reporter = AutomationReporter(album_name="My Album", report_dir=Path("output"))
        reporter.start()
        # ... during automation ...
        reporter.record_issue(severity="warning", category="element_not_found", ...)
        # ... at the end ...
        reporter.finish(success=True, steps_attempted=15, steps_completed=15)
        reporter.save()
    """

    def __init__(self, album_name: str, report_dir: Optional[Path] = None):
        """
        Initialize reporter.

        Args:
            album_name: Name of the album being processed.
            report_dir: Directory to save report files. Defaults to project output/.
        """
        self.album_name = album_name
        self.report_dir = report_dir or Path.home() / ".camxora" / "distrokid" / "reports"
        self._report = AutomationReport(
            album_name=album_name,
            started_at=datetime.now().isoformat(),
        )

    def start(self):
        """Mark the start of an automation run."""
        self._report.started_at = datetime.now().isoformat()

    def record_issue(
        self,
        severity: str,
        category: str,
        step: str,
        description: str,
        element: str = "",
        strategies_tried: list = None,
        page_url: str = "",
        suggestion: str = "",
    ):
        """Record an issue encountered during automation.

        Args:
            severity: "warning" (non-blocking), "error" (failed but continued),
                      "blocker" (halted automation)
            category: "element_not_found", "field_missed", "unexpected_state",
                      "timeout", "interaction_failed"
            step: Which questionnaire step was running
            description: Human-readable description
            element: The element being targeted
            strategies_tried: List of resolution strategies attempted
            page_url: Current page URL when the issue occurred
            suggestion: Suggested fix or action
        """
        issue = AutomationIssue(
            timestamp=datetime.now().isoformat(),
            severity=severity,
            category=category,
            step=step,
            description=description,
            element=element,
            strategies_tried=strategies_tried or [],
            page_url=page_url,
            suggestion=suggestion,
        )
        self._report.issues.append(asdict(issue))
        logger.info(f"[REPORT] [{severity.upper()}] {step}: {description}")

    def finish(self, success: bool, steps_attempted: int, steps_completed: int):
        """Finalize the report.

        Args:
            success: Whether automation completed successfully.
            steps_attempted: Total steps that were attempted.
            steps_completed: Steps that completed without error.
        """
        self._report.finished_at = datetime.now().isoformat()
        self._report.success = success
        self._report.total_steps_attempted = steps_attempted
        self._report.total_steps_completed = steps_completed

    def save(self) -> Path:
        """Save the report to a JSON file.

        Returns:
            Path to the saved report file.
        """
        self.report_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = self.album_name.replace(" ", "_").replace("/", "_")[:50]
        filename = f"automation_report_{safe_name}_{timestamp}.json"
        report_path = self.report_dir / filename

        report_data = asdict(self._report)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Automation report saved: {report_path}")
        return report_path

    def get_report(self) -> AutomationReport:
        """Get the current report object."""
        return self._report

    def get_summary(self) -> str:
        """Get a human-readable summary of the report."""
        return self._report.summary()
