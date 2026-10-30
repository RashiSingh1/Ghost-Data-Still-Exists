"""Deterministic deletion audit pipeline for Ghost Data Still Exists."""

from __future__ import annotations

import csv
import json
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "dataset"
OUTPUT = ROOT / "output.csv"

OP_ORDER = {
    "REPORT_REMAINING_RECORD": 1,
    "REPORT_EXPOSED_PII": 2,
    "REPORT_ACTIVE_DATA_FLOW": 3,
    "REPORT_RESTORE_RISK": 4,
    "DISABLE_DATA_FLOW": 5,
    "BLOCK_RESTORE": 6,
    "DELETE_RECORD": 7,
    "REDACT_RECORD": 8,
    "ANONYMIZE_RECORD": 9,
    "VERIFY_RECORD_ABSENT": 10,
    "VERIFY_RECORD_PRESENT": 11,
    "VERIFY_RECORD_REDACTED": 12,
    "VERIFY_RECORD_ANONYMIZED": 13,
    "VERIFY_DATA_FLOW_DISABLED": 14,
    "VERIFY_RESTORE_BLOCKED": 15,
}
PHASE_ORDER = {"FINDING": 1, "REMEDIATION": 2, "VERIFICATION": 3}

CATEGORY_BY_TABLE = {
    "customer_profiles": "USER_PROFILE",
    "customer_profiles_primary": "USER_PROFILE",
    "customer_profiles_failover_replica": "USER_PROFILE",
    "customer_search_documents": "SEARCH_INDEX_ENTRY",
    "search_documents_primary": "SEARCH_INDEX_ENTRY",
    "customer_analytics_profiles": "ANALYTICS_PROFILE",
    "support_records": "SUPPORT_MESSAGE",
    "customer_exports": "USER_EXPORT",
    "connector_subscriptions": "DATA_FLOW",
    "backup_restore_entries": "BACKUP_ARCHIVE",
    "security_audit_records": "SECURITY_AUDIT_LOG",
}
CATEGORY_BY_COLLECTION = {
    "customer_profiles": "USER_PROFILE",
    "customer_search_documents": "SEARCH_INDEX_ENTRY",
    "customer_analytics_profiles": "ANALYTICS_PROFILE",
    "support_records": "SUPPORT_MESSAGE",
    "customer_exports": "USER_EXPORT",
    "connector_subscriptions": "DATA_FLOW",
    "backup_restore_entries": "BACKUP_ARCHIVE",
    "security_audit_records": "SECURITY_AUDIT_LOG",
    "security_audit_events": "SECURITY_AUDIT_LOG",
    "customer_analytics_reports": "ANALYTICS_PROFILE",
    "deleted_customer_references": "ACCOUNT_TOMBSTONE",
}
SYSTEM_BY_CATEGORY = {
    "USER_PROFILE": "account_service",
    "SECONDARY_IDENTIFIER": "identity_service",
    "SEARCH_INDEX_ENTRY": "search_service",
    "CACHE_ENTRY": "cache_service",
    "SUPPORT_MESSAGE": "support_platform",
    "SUPPORT_ATTACHMENT": "support_platform",
    "ANALYTICS_PROFILE": "analytics_platform",
    "PRODUCT_TELEMETRY": "analytics_platform",
    "USER_EXPORT": "export_service",
    "MARKETING_PROFILE": "marketing_service",
    "EMAIL_DELIVERY_LOG": "email_delivery_service",
    "SECURITY_AUDIT_LOG": "security_service",
    "LEGAL_HOLD_RECORD": "legal_service",
    "BACKUP_ARCHIVE": "backup_service",
    "ACCOUNT_TOMBSTONE": "identity_service",
    "DATA_FLOW": "integration_service",
}


def parse_time(value: str | None) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def norm(value: Any) -> str:
    return str(value).strip().lower() if value is not None else ""


def flatten(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(f"{flatten(k)} {flatten(v)}" for k, v in value.items())
    if isinstance(value, list):
        return " ".join(flatten(v) for v in value)
    return norm(value)


def contains_identifier(text: str, identifier: str) -> bool:
    if not identifier:
        return False
    return re.search(
        rf"(?<![a-z0-9]){re.escape(identifier.lower())}(?![a-z0-9])",
        text.lower(),
    ) is not None


def identifier_pattern(identifiers: set[str]) -> re.Pattern[str] | None:
    values = sorted((value.lower() for value in identifiers if value), key=len, reverse=True)
    if not values:
        return None
    return re.compile(
        rf"(?<![a-z0-9])(?:{'|'.join(re.escape(value) for value in values)})(?![a-z0-9])"
    )


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


@dataclass
class EvidenceRecord:
    evidence_id: str
    captured_at: datetime
    category: str
    system_id: str
    resource_id: str
    values: dict[str, Any]
    text: str = ""
    _searchable: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._searchable = flatten(self.values) + " " + self.text.lower()

    def searchable(self) -> str:
        return self._searchable


@dataclass
class Finding:
    record: EvidenceRecord
    operation: str
    state: str
    remediation: str
    verification: str


def json_records(value: Any, inherited: dict[str, Any] | None = None) -> Iterable[dict[str, Any]]:
    inherited = inherited or {}
    if isinstance(value, dict):
        current = dict(inherited)
        current.update({key: child for key, child in value.items() if not isinstance(child, (dict, list))})
        if "resource_id" in value:
            current.update(value)
            yield current
        for child in value.values():
            yield from json_records(child, current)
    elif isinstance(value, list):
        for child in value:
            yield from json_records(child, inherited)


def category_for(category_hint: str, values: dict[str, Any], table: str = "") -> str:
    hint = f"{category_hint} {table} {flatten(values)}".lower()
    for key, category in CATEGORY_BY_COLLECTION.items():
        if key.lower() in hint:
            return category
    if "tombstone" in hint or "deleted_customer_reference" in hint:
        return "ACCOUNT_TOMBSTONE"
    if "marketing" in hint:
        return "MARKETING_PROFILE"
    if "telemetry" in hint:
        return "PRODUCT_TELEMETRY"
    if "attachment" in hint:
        return "SUPPORT_ATTACHMENT"
    if "email_delivery" in hint or "delivery_log" in hint:
        return "EMAIL_DELIVERY_LOG"
    return "USER_PROFILE" if "account" in hint or "profile" in hint else "SECONDARY_IDENTIFIER"


def system_for(category: str, values: dict[str, Any]) -> str:
    if category == "DATA_FLOW":
        return "integration_service"
    return SYSTEM_BY_CATEGORY.get(category, norm(values.get("origin_system")) or "account_service")


def category_for_resource(resource: str) -> str | None:
    prefix = resource.split("_", 1)[0]
    return {
        "account": "USER_PROFILE",
        "search": "SEARCH_INDEX_ENTRY",
        "cache": "CACHE_ENTRY",
        "support": "SUPPORT_MESSAGE",
        "export": "USER_EXPORT",
        "analytics": "ANALYTICS_PROFILE",
        "telemetry": "PRODUCT_TELEMETRY",
        "marketing": "MARKETING_PROFILE",
        "backup": "BACKUP_ARCHIVE",
        "audit": "SECURITY_AUDIT_LOG",
        "tombstone": "ACCOUNT_TOMBSTONE",
        "data": "DATA_FLOW",
    }.get(prefix)


def parse_sql(path: Path, evidence_id: str, captured_at: datetime) -> list[EvidenceRecord]:
    result: list[EvidenceRecord] = []
    connection = sqlite3.connect(":memory:")
    try:
        connection.executescript(path.read_text(encoding="utf-8", errors="replace"))
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        for (table,) in tables:
            columns = [row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')]
            for raw in connection.execute(f'SELECT * FROM "{table}"'):
                values = dict(zip(columns, raw))
                if table == "snapshot_scope":
                    continue
                if "record_json" in values:
                    try:
                        nested = json.loads(values["record_json"])
                        values.update(nested if isinstance(nested, dict) else {})
                    except json.JSONDecodeError:
                        pass
                resource = norm(values.get("resource_id"))
                if not resource:
                    continue
                category = (
                    category_for_resource(resource)
                    or CATEGORY_BY_TABLE.get(table, category_for(table, values, table))
                )
                result.append(
                    EvidenceRecord(
                        evidence_id,
                        captured_at,
                        category,
                        system_for(category, values),
                        resource,
                        values,
                        flatten(values),
                    )
                )
    finally:
        connection.close()
    return result


def parse_text(path: Path, evidence_id: str, captured_at: datetime) -> list[EvidenceRecord]:
    text = path.read_text(encoding="utf-8", errors="replace")
    result: list[EvidenceRecord] = []
    started: dict[str, dict[str, Any]] = {}
    for line in text.splitlines():
        ids = re.findall(
            r"\b(?:account|search|cache|support|export|analytics|telemetry|marketing|"
            r"email_delivery|audit_record|legal_hold|backup|data_flow|tombstone)_\d+\b",
            line,
            flags=re.I,
        )
        values: dict[str, Any] = {"line": line}
        for match in re.finditer(r'(\w+)=(?:"([^"]*)"|([^\s]+))', line):
            values[match.group(1)] = match.group(2) if match.group(2) is not None else match.group(3)
        trace_id = str(values.get("trace_id", ""))
        if str(values.get("event", "")).endswith("_started"):
            if trace_id:
                started[trace_id] = values
            continue
        if not ids:
            continue
        resource = ids[0]
        if trace_id in started:
            for key in ("lookup_key", "subject_reference", "customer_reference"):
                if key not in values and started[trace_id].get(key):
                    values[key] = started[trace_id][key]
        if "|" in line:
            parts = [part.strip() for part in line.split("|")]
            values.update({"system": parts[1] if len(parts) > 1 else "", "category": parts[3] if len(parts) > 3 else "", "status": parts[4] if len(parts) > 4 else ""})
        category = category_for(str(values.get("category", "")), values)
        if "data_flow" in resource:
            category = "DATA_FLOW"
        elif "backup" in resource:
            category = "BACKUP_ARCHIVE"
        elif "search" in resource:
            category = "SEARCH_INDEX_ENTRY"
        elif "support" in resource:
            category = "SUPPORT_ATTACHMENT" if str(values.get("category", "")).upper() == "SUPPORT_ATTACHMENT" else "SUPPORT_MESSAGE"
        elif "export" in resource:
            category = "USER_EXPORT"
        elif "analytics" in resource:
            category = "ANALYTICS_PROFILE"
        elif "audit_record" in resource:
            category = "SECURITY_AUDIT_LOG"
        result.append(EvidenceRecord(evidence_id, captured_at, category, system_for(category, values), resource, values, line))
    return result


def parse_json(path: Path, evidence_id: str, captured_at: datetime) -> list[EvidenceRecord]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    result: list[EvidenceRecord] = []
    for item in json_records(value):
        resource = norm(item.get("resource_id"))
        if not resource:
            continue
        category = category_for(
            str(item.get("collection", "")),
            item,
            str(item.get("collection", "")),
        )
        category = category_for_resource(resource) or category
        if "enabled" in item and ("flow" in resource or "connector" in flatten(item)):
            category = "DATA_FLOW"
        if "restore_allowed" in item:
            category = "BACKUP_ARCHIVE"
        result.append(EvidenceRecord(evidence_id, captured_at, category, system_for(category, item), resource, item, flatten(item)))
    return result


def manual_image_records(evidence_id: str, captured_at: datetime) -> list[EvidenceRecord]:
    # These are transcriptions of visible, participant-facing fields in the supplied screenshots.
    items = {
        "evidence_04": [("USER_PROFILE", "account_service", "account_5762", {"user_id": "user_11", "email": "haruka.s1838@zoho.com", "status": "ACTIVE"})],
        "evidence_09": [("SEARCH_INDEX_ENTRY", "search_service", "search_428", {"user_id": "user_13", "email": "g.silva76@gmail.com", "status": "PRESENT"}), ("SEARCH_INDEX_ENTRY", "search_service", "search_1874", {"email": "g.silva76jr@gmail.com", "status": "PRESENT"})],
        "evidence_14": [("DATA_FLOW", "integration_service", "data_flow_1121", {"email": "jain.aditi@gmail.com", "enabled": True}), ("DATA_FLOW", "integration_service", "data_flow_9846", {"email": "lucia-torres@gmail.com", "enabled": True})],
        "evidence_19": [("ANALYTICS_PROFILE", "analytics_platform", "analytics_7438", {"user_id": "user_20", "email": "darwish.omar@icloud.com", "status": "IDENTIFIABLE"})],
        "evidence_23": [("USER_EXPORT", "export_service", "export_1260", {"email": "ingrid.dahl@outlook.com", "status": "READY"})],
        "evidence_28": [("SUPPORT_MESSAGE", "support_platform", "support_1034", {"user_id": "user_22", "email": "kagyeman8947@fastmail.com", "shared_order_context": True})],
        "evidence_32": [("BACKUP_ARCHIVE", "backup_service", "backup_9287", {"email": "areed1433@gmail.com", "restore_allowed": True})],
        "evidence_37": [("SECURITY_AUDIT_LOG", "security_service", "audit_record_003", {"user_id": "user_03", "retention_until": "2027-08-25T04:03:00Z"})],
        "evidence_42": [("ACCOUNT_TOMBSTONE", "identity_service", "tombstone_user_17", {"user_id": "user_17", "stable_reference": True, "direct_identifiers": False})],
        "evidence_46": [],
        "evidence_60": [("MARKETING_PROFILE", "marketing_service", "marketing_001", {"email": "sj.park@naver.com", "status": "LIVE"})],
    }
    return [EvidenceRecord(evidence_id, captured_at, c, s, r, v, flatten(v)) for c, s, r, v in items.get(evidence_id, [])]


def load_evidence() -> list[EvidenceRecord]:
    result: list[EvidenceRecord] = []
    for manifest in rows(DATASET / "evidence_files.csv"):
        path = DATASET / manifest["file_path"]
        captured = parse_time(manifest["captured_at"])
        if path.suffix.lower() == ".sql":
            result.extend(parse_sql(path, manifest["file_id"], captured))
        elif path.suffix.lower() == ".json":
            result.extend(parse_json(path, manifest["file_id"], captured))
        elif path.suffix.lower() in {".txt", ".log"}:
            result.extend(parse_text(path, manifest["file_id"], captured))
        elif path.suffix.lower() == ".pdf":
            try:
                from pypdf import PdfReader

                text = "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
                result.extend(parse_text_from_blob(text, manifest["file_id"], captured))
            except ImportError:
                pass
        elif path.suffix.lower() == ".png":
            result.extend(manual_image_records(manifest["file_id"], captured))
    return result


def parse_text_from_blob(text: str, evidence_id: str, captured_at: datetime) -> list[EvidenceRecord]:
    result = []
    for line in text.splitlines():
        ids = re.findall(r"\b(?:account|support|audit_record|export|backup|analytics|marketing|data_flow)_\d+\b", line)
        if not ids:
            continue
        resource = next((x for x in ids if "_" in x and not x.startswith("user_")), ids[0])
        values = {"line": line}
        emails = re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
        if emails:
            values["email"] = emails[0]
        phones = re.findall(r"\+\d[\d ()-]{7,}", text)
        if phones:
            values["phone"] = phones[0].strip()
        category = category_for(line, values)
        if "support" in resource and "attachment" in text.lower():
            category = "SUPPORT_ATTACHMENT"
        elif "order" in text.lower() and "support" in resource:
            category = "SUPPORT_MESSAGE"
        return_record = EvidenceRecord(evidence_id, captured_at, category, system_for(category, values), resource, values, line)
        result.append(return_record)
    return result


def identifiers_for(email: str, identities: list[dict[str, str]], audits: list[dict[str, str]]) -> tuple[str | None, set[str]]:
    needle = norm(email)
    candidates = [row for row in identities if norm(row["email"]) == needle]
    if not candidates:
        candidates = [row for row in identities if norm(row["email"]) == needle.lower()]
    if not candidates:
        for audit in audits:
            if norm(audit["old_value"]) == needle or norm(audit["new_value"]) == needle:
                candidates = [row for row in identities if row["user_id"] == audit["user_id"]]
                if candidates:
                    break
    if not candidates:
        return None, {needle}
    user_id = candidates[0]["user_id"]
    values: set[str] = {norm(user_id)}
    for row in candidates:
        values.update(norm(row[k]) for k in ("name", "email", "phone", "email_hash") if row.get(k))
    for audit in audits:
        if audit["user_id"] == user_id:
            values.update(norm(audit[k]) for k in ("old_value", "new_value") if audit.get(k))
    return user_id, {value for value in values if value}


def authorized(text: str) -> bool:
    value = norm(text)
    deletion_markers = (
        "delet", "eras", "remov", "close my account", "close this account",
        "account is gone", "profile is gone", "account still existed",
        "audit the deletion", "verify that my account was deleted",
        "permanent", "suppression", "삭제", "削除", "exclusão",
        "eliminación", "eliminare",
    )
    if any(marker in value for marker in deletion_markers):
        return True
    non_deletion_markers = (
        "access my data", "access my information", "data access request",
        "correct my", "rectify my", "change my email", "marketing opt",
        "unsubscribe", "export my data", "download my data",
    )
    return not any(marker in value for marker in non_deletion_markers) and (
        "close" in value or "remove" in value or "erase" in value
    )


def state_and_action(record: EvidenceRecord) -> tuple[str, str, str, str] | None:
    data = {norm(k): v for k, v in record.values.items()}
    text = record.searchable()
    category = record.category
    def present(key: str) -> bool:
        return norm(data.get(key)) not in {"", "null", "none", "false", "0"}
    if category == "DATA_FLOW":
        if (
            norm(data.get("enabled")) in {"1", "true", "yes"}
            or norm(data.get("status")) in {"active", "enabled"}
            or "enabled=true" in text
            or " active " in f" {text} "
        ):
            return "ACTIVE", "REPORT_ACTIVE_DATA_FLOW", "DISABLE_DATA_FLOW", "VERIFY_DATA_FLOW_DISABLED"
        return None
    if category == "BACKUP_ARCHIVE":
        if (
            norm(data.get("restore_allowed")) in {"1", "true", "yes"}
            or norm(data.get("status")) in {"active", "enabled"}
            or norm(data.get("eligible")) in {"1", "true", "yes"}
            and norm(data.get("deletion_block")) not in {"1", "true", "yes"}
            or "restore_allowed=true" in text
            or "restore access" in text
            and "can still" in text
        ):
            return "ACTIVE", "REPORT_RESTORE_RISK", "BLOCK_RESTORE", "VERIFY_RESTORE_BLOCKED"
        return "BLOCKED", "", "", "VERIFY_RESTORE_BLOCKED"
    if category in {"SECURITY_AUDIT_LOG", "LEGAL_HOLD_RECORD"}:
        return "PRESENT", "", "", "VERIFY_RECORD_PRESENT"
    if category == "ACCOUNT_TOMBSTONE":
        direct_fields = ("name", "email", "phone", "email_hash")
        direct = any(
            norm(data.get(key)) not in {"", "null", "none", "false", "0"}
            for key in direct_fields
        )
        direct_flag = norm(data.get("direct_identifiers")) in {"1", "true", "yes"}
        direct = direct or direct_flag
        if direct:
            return "PRESENT", "REPORT_EXPOSED_PII", "REDACT_RECORD", "VERIFY_RECORD_REDACTED"
        return "REDACTED", "", "", "VERIFY_RECORD_REDACTED"
    if category in {"ANALYTICS_PROFILE", "PRODUCT_TELEMETRY"}:
        identifiable = any(
            present(k)
            for k in (
                "email",
                "phone",
                "email_hash",
                "user_id",
                "customer_reference",
                "correlation_key",
                "email_opt_in",
                "status",
            )
            if k in data
        )
        if "anonymized" in text and not identifiable:
            return "ANONYMIZED", "", "", "VERIFY_RECORD_ANONYMIZED"
        if identifiable:
            return "PRESENT", "REPORT_EXPOSED_PII", "ANONYMIZE_RECORD", "VERIFY_RECORD_ANONYMIZED"
        return "ANONYMIZED", "", "", "VERIFY_RECORD_ANONYMIZED"
    if category == "SUPPORT_MESSAGE":
        has_direct = any(
            present(k)
            for k in (
                "email",
                "requester_email",
                "phone",
                "requester_phone",
                "matched_value",
            )
        )
        if norm(data.get("marker_found")) in {"false", "0", "no"}:
            return "PRESENT", "REPORT_REMAINING_RECORD", "DELETE_RECORD", "VERIFY_RECORD_ABSENT"
        if norm(data.get("status")) in {"identifiable", "present", "exposed"}:
            return "PRESENT", "REPORT_EXPOSED_PII", "REDACT_RECORD", "VERIFY_RECORD_REDACTED"
        if "redacted" in text and not has_direct:
            return "REDACTED", "", "", "VERIFY_RECORD_REDACTED"
        if not has_direct:
            return "REDACTED", "", "", "VERIFY_RECORD_REDACTED"
        if any(key in text for key in ("shared_order_context", "order", "agent")):
            return "PRESENT", "REPORT_EXPOSED_PII", "REDACT_RECORD", "VERIFY_RECORD_REDACTED"
        return "PRESENT", "REPORT_EXPOSED_PII", "REDACT_RECORD", "VERIFY_RECORD_REDACTED"
    if category == "SUPPORT_ATTACHMENT":
        return "PRESENT", "REPORT_REMAINING_RECORD", "DELETE_RECORD", "VERIFY_RECORD_ABSENT"
    if any(x in category for x in ("USER_PROFILE", "SEARCH_INDEX_ENTRY", "CACHE_ENTRY", "USER_EXPORT", "MARKETING_PROFILE", "EMAIL_DELIVERY_LOG", "SECONDARY_IDENTIFIER")):
        if any(x in text for x in ("not_found", "not found", "404", "absent", "null profile", "status_code 404", "http_status=404")):
            return "ABSENT", "", "", "VERIFY_RECORD_ABSENT"
        return "PRESENT", "REPORT_REMAINING_RECORD", "DELETE_RECORD", "VERIFY_RECORD_ABSENT"
    return None


def build_steps(request: dict[str, str], identity_values: set[str], user_id: str | None, evidence: list[EvidenceRecord]) -> tuple[str, list[dict[str, Any]]]:
    audit_at = parse_time(request["audit_at"])
    identifier_re = identifier_pattern(identity_values)
    relevant_by_key: dict[tuple[str, str, str], tuple[EvidenceRecord, tuple[str, str, str, str]]] = {}
    for record in evidence:
        if record.captured_at > audit_at:
            continue
        searchable = record.searchable()
        if identifier_re is None or identifier_re.search(searchable) is None:
            continue
        record_key = (record.evidence_id, record.category, record.resource_id)
        state = state_and_action(record)
        if state:
            previous = relevant_by_key.get(record_key)
            if previous is None or (not previous[1][1] and state[1]):
                relevant_by_key[record_key] = (record, state)
    relevant = list(relevant_by_key.values())
    findings: list[dict[str, Any]] = []
    remediations: list[dict[str, Any]] = []
    verifications: list[dict[str, Any]] = []
    relevant_resources = {record.resource_id for record, _ in relevant}
    for record, (state, finding_op, remediation_op, verification_op) in relevant:
        if finding_op:
            findings.append({"phase": "FINDING", "system_id": record.system_id, "resource_id": record.resource_id, "operation": finding_op, "state": state, "evidence_id": record.evidence_id})
            remediations.append({"phase": "REMEDIATION", "system_id": record.system_id, "resource_id": record.resource_id, "operation": remediation_op, "state": {"DELETE_RECORD": "ABSENT", "REDACT_RECORD": "REDACTED", "ANONYMIZE_RECORD": "ANONYMIZED", "DISABLE_DATA_FLOW": "DISABLED", "BLOCK_RESTORE": "BLOCKED"}[remediation_op], "evidence_id": ""})
        verifications.append({"phase": "VERIFICATION", "system_id": record.system_id, "resource_id": record.resource_id, "operation": verification_op, "state": state if not finding_op else {"VERIFY_RECORD_ABSENT": "ABSENT", "VERIFY_RECORD_REDACTED": "REDACTED", "VERIFY_RECORD_ANONYMIZED": "ANONYMIZED", "VERIFY_DATA_FLOW_DISABLED": "DISABLED", "VERIFY_RESTORE_BLOCKED": "BLOCKED"}.get(verification_op, state), "evidence_id": record.evidence_id if not finding_op else ""})
    if findings:
        for record, _ in relevant:
            source_resource = norm(record.values.get("source_resource_id"))
            if (
                source_resource
                and source_resource not in relevant_resources
                and category_for_resource(source_resource) == "USER_PROFILE"
            ):
                verifications.append(
                    {
                        "phase": "VERIFICATION",
                        "system_id": "account_service",
                        "resource_id": source_resource,
                        "operation": "VERIFY_RECORD_ABSENT",
                        "state": "ABSENT",
                        "evidence_id": "",
                    }
                )
    incomplete = bool(findings)
    if incomplete:
        # Future remediation and verification are intentionally evidence-free.
        for step in remediations + verifications:
            step["evidence_id"] = ""
    all_steps = findings + remediations + verifications
    all_steps.sort(key=lambda step: (PHASE_ORDER[step["phase"]], OP_ORDER[step["operation"]], step["system_id"], step["resource_id"]))
    for number, step in enumerate(all_steps, 1):
        step["step_no"] = number
        step = {key: step[key] for key in ("step_no", "phase", "system_id", "resource_id", "operation", "state", "evidence_id")}
        all_steps[number - 1] = step
    return ("INCOMPLETE" if incomplete else "COMPLETE"), all_steps


def main() -> None:
    identities = rows(DATASET / "user_identities.csv")
    audits = rows(DATASET / "user_audit_log.csv")
    evidence = load_evidence()
    outputs = []
    for request in rows(DATASET / "deletion_requests.csv"):
        if not authorized(request["request_text"]):
            outputs.append({"case_id": request["case_id"], "deletion_status": "NOT_APPLICABLE", "steps_json": "[]"})
            continue
        user_id, identifiers = identifiers_for(request["email"], identities, audits)
        status, steps = build_steps(request, identifiers, user_id, evidence)
        outputs.append({"case_id": request["case_id"], "deletion_status": status, "steps_json": json.dumps(steps, ensure_ascii=False, separators=(",", ":"))})
    outputs.sort(key=lambda row: row["case_id"])
    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["case_id", "deletion_status", "steps_json"])
        writer.writeheader()
        writer.writerows(outputs)
    print(f"Wrote {len(outputs)} rows to {OUTPUT}")


if __name__ == "__main__":
    main()