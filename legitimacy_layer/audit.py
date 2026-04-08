"""
audit.py — Append-only Audit Log.

Records every routing decision with its full input context, governance mode,
resulting directive, and a UTC timestamp. Supports JSON Lines and CSV output.
"""

import csv
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import List, Optional

from .controller import Directive, GovernanceMode, ImpactClass


# ---------------------------------------------------------------------------
# Audit record
# ---------------------------------------------------------------------------

@dataclass
class AuditRecord:
    timestamp: str
    uncertainty_score: float
    impact_class: str
    reversibility_flag: bool
    contestation_signal: bool
    governance_mode: str
    directive: str

    @staticmethod
    def create(
        uncertainty_score: float,
        impact_class: ImpactClass,
        reversibility_flag: bool,
        contestation_signal: bool,
        governance_mode: GovernanceMode,
        directive: Directive,
    ) -> "AuditRecord":
        return AuditRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            uncertainty_score=round(uncertainty_score, 6),
            impact_class=impact_class.value,
            reversibility_flag=reversibility_flag,
            contestation_signal=contestation_signal,
            governance_mode=governance_mode.value,
            directive=directive.value,
        )

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

class AuditLog:
    """
    Append-only audit log backed by a JSON Lines file.

    Each line in the output file is a self-contained JSON object
    (newline-delimited JSON / JSONL), making the log easy to stream,
    grep, and ingest into downstream tooling.
    """

    _FIELDNAMES = [
        "timestamp",
        "uncertainty_score",
        "impact_class",
        "reversibility_flag",
        "contestation_signal",
        "governance_mode",
        "directive",
    ]

    def __init__(self, path: str = "audit_log.jsonl") -> None:
        self._path = path
        self._records: List[AuditRecord] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def append(
        self,
        uncertainty_score: float,
        impact_class: ImpactClass,
        reversibility_flag: bool,
        contestation_signal: bool,
        governance_mode: GovernanceMode,
        directive: Directive,
    ) -> AuditRecord:
        """Create and persist one audit record."""
        record = AuditRecord.create(
            uncertainty_score=uncertainty_score,
            impact_class=impact_class,
            reversibility_flag=reversibility_flag,
            contestation_signal=contestation_signal,
            governance_mode=governance_mode,
            directive=directive,
        )
        self._records.append(record)
        self._write_line(record)
        return record

    def records(self) -> List[AuditRecord]:
        """Return an in-memory copy of all records appended this session."""
        return list(self._records)

    def export_csv(self, path: Optional[str] = None) -> str:
        """
        Export all in-memory records to a CSV file.

        Parameters
        ----------
        path : str, optional
            Output path. Defaults to the JSONL path with .csv extension.

        Returns
        -------
        str
            Absolute path to the written CSV file.
        """
        csv_path = path or self._path.replace(".jsonl", ".csv")
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self._FIELDNAMES)
            writer.writeheader()
            writer.writerows(r.to_dict() for r in self._records)
        return os.path.abspath(csv_path)

    @property
    def path(self) -> str:
        return self._path

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _write_line(self, record: AuditRecord) -> None:
        """Append one JSON line to the log file (atomic per-record write)."""
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict()) + "\n")
