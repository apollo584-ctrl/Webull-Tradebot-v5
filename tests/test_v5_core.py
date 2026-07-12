import sys
import unittest
from datetime import datetime
import hashlib
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from v5_eval.core import build_blind_request, canonicalize_records, sha256_text, validate_capture_manifest, validate_decision, validate_model_output
from v5_eval.scoring import bind_locked_labels, label_ready, score_records
from v5_eval.v4_baseline import normalize_parsed_signal, verify_label_lock
from v5_eval.workflow import apply_cluster_reviews, build_label_queue


class V5CoreTests(unittest.TestCase):
    @staticmethod
    def ready_label(decision, novelty="known_or_near_duplicate"):
        return {
            "label_version": 1,
            "case_id": "c1",
            "source_message_id": "m1",
            "labeled_at": "2026-07-13T10:00:00-04:00",
            "labeler_id": "tester",
            "label_pass": "primary",
            "blind_declaration": True,
            "allowed_context_hash": "A" * 64,
            "required_context": {"context_required": False, "position_state": "flat", "prior_message_ids": [], "notes": None},
            "decision": decision,
            "novelty_class": novelty,
            "confidence": "high",
            "adjudication_status": "not_required",
            "rationale": "test label",
        }

    def test_canonicalization_deduplicates_and_clusters(self):
        records = [
            {"message_id": "2", "timestamp": "2026-07-13T10:01:00-04:00", "raw_text": "Open SPY long"},
            {"message_id": "1", "timestamp": "2026-07-13T10:00:00-04:00", "raw_text": "Open SPY long"},
            {"message_id": "1", "timestamp": "2026-07-13T10:02:00-04:00", "raw_text": "Open SPY long"},
        ]
        cases = canonicalize_records(records, confirmation_start=datetime.fromisoformat("2026-07-13T00:00:00-04:00"), manifest_verified=True)
        self.assertEqual(len(cases), 2)
        self.assertEqual(cases[0]["cluster_id"], cases[1]["cluster_id"])

    def test_page_url_hash_is_case_insensitive_and_missing_source_is_rejected(self):
        record = {"message_id": "1", "timestamp": "2026-07-13T10:00:00-04:00", "raw_text": "watch SPY", "page_url": "https://source.test"}
        cases = canonicalize_records([record], source_channel_url_sha256=sha256_text(record["page_url"]).upper())
        self.assertEqual(len(cases), 1)
        with self.assertRaises(ValueError):
            canonicalize_records([{key: value for key, value in record.items() if key != "page_url"}])

    def test_blind_request_excludes_parser_fields(self):
        request = build_blind_request({"raw_text": "take the QQQ long", "message_timestamp": "2026-07-13T10:00:00-04:00", "parser_decision": "OPEN"}, recent_messages=["context"], position_state={"symbol": "QQQ", "direction": "LONG", "quantity": 100})
        self.assertNotIn("parser_decision", request)
        self.assertNotIn("expected_label", request)

    def test_invalid_action_status_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_decision({"action": "OPEN", "symbol": "SPY", "direction": "LONG", "status": "no_action"})
        self.assertEqual(validate_model_output('{"action":"NONE","symbol":null,"direction":null,"status":"no_action"}')['parse_status'], "ok")

    def test_saved_response_scoring(self):
        record = {
            "cluster_id": "cluster-0001",
            "cluster_review_status": "confirmed_split",
            "contamination_status": "clear",
            "independent_label": self.ready_label({"action": "OPEN", "symbol": "SPY", "direction": "LONG", "status": "actionable"}, "linguistically_novel"),
            "v4_baseline": {"action": "REVIEW", "symbol": None, "direction": None, "status": "ambiguous"},
            "model_output": {"action": "OPEN", "symbol": "SPY", "direction": "LONG", "status": "actionable"},
            "latency_ms": 100,
        }
        report = score_records([record])
        self.assertEqual(report["critical_errors"], 0)
        self.assertEqual(report["novel_cluster_weighted_accuracy"], 1)
        self.assertEqual(report["paired_cluster_bootstrap"]["lower"], 1)

    def test_label_readiness_requires_a_valid_novelty_class(self):
        label = self.ready_label({"action": "NONE", "symbol": None, "direction": None, "status": "no_action"})
        label.pop("novelty_class")
        self.assertFalse(label_ready(label))
        label["novelty_class"] = "bogus"
        self.assertFalse(label_ready(label))

    def test_locked_label_binding_rejects_missing_response_cases(self):
        case = {"case_id": "c1", "source_message_id": "m1", "cluster_id": "cluster-1", "cluster_review_status": "confirmed", "contamination_status": "clear", "contamination_flags": []}
        label = self.ready_label({"action": "NONE", "symbol": None, "direction": None, "status": "no_action"})
        with self.assertRaises(ValueError):
            bind_locked_labels([], [case], [label])

    def test_capture_manifest_audit_must_match_selected_count(self):
        manifest = {
            "capture_id": "capture-1",
            "imported_at": "2026-07-13T10:00:00-04:00",
            "snapshot_path": "data/raw/prospective/capture-1.jsonl",
            "snapshot_sha256": "A" * 64,
            "source_channel_url_sha256": "B585176665DD638BB6E8682C48F8469131AF9A5101D64619B8AD323117BE15BA",
            "time_start": "2026-07-13T10:00:00-04:00",
            "time_end": "2026-07-13T10:01:00-04:00",
            "record_count": 2,
            "parser_or_model_fields_absent": True,
            "capture_audit": {"input_records": 2, "selected_records": 1, "stress_channel_excluded": 0, "wrong_or_missing_source_excluded": 0, "pre_boundary_excluded": 0, "malformed_or_empty_excluded": 0},
        }
        with self.assertRaises(ValueError):
            validate_capture_manifest(manifest)

    def test_safe_deferral_is_not_critical_but_is_not_correct(self):
        record = {
            "cluster_id": "cluster-0001",
            "cluster_review_status": "confirmed",
            "contamination_status": "clear",
            "independent_label": self.ready_label({"action": "OPEN", "symbol": "SPY", "direction": "LONG", "status": "actionable"}),
            "model_output": {"action": "REVIEW", "symbol": None, "direction": None, "status": "ambiguous"},
            "latency_ms": 100,
        }
        report = score_records([record])
        self.assertEqual(report["critical_errors"], 0)
        self.assertEqual(report["message_weighted_accuracy"], 0)

    def test_invalid_output_stays_in_accuracy_denominator(self):
        record = {
            "cluster_id": "cluster-0001",
            "cluster_review_status": "confirmed",
            "contamination_status": "clear",
            "independent_label": self.ready_label({"action": "NONE", "symbol": None, "direction": None, "status": "no_action"}),
            "parse_status": "invalid_json",
            "normalized_decision": None,
            "latency_ms": 100,
        }
        report = score_records([record])
        self.assertEqual(report["eligible_clear"], 1)
        self.assertEqual(report["message_weighted_accuracy"], 0)
        self.assertEqual(report["structured_output_rate"], 0)

    def test_v4_parser_output_normalizes_without_runtime_state(self):
        option = SimpleNamespace(symbol="QQQ", stock_direction=SimpleNamespace(value="LONG"))
        parsed = SimpleNamespace(action=SimpleNamespace(value="OPEN"), option=option, target_symbol="", target_direction=None, dispatchable=True)
        self.assertEqual(normalize_parsed_signal(parsed)["decision"], {"action": "OPEN", "symbol": "QQQ", "direction": "LONG", "status": "actionable"})

        no_action = SimpleNamespace(action=None, option=None, target_symbol="SPY", target_direction=None, dispatchable=True)
        self.assertEqual(normalize_parsed_signal(no_action)["decision"], {"action": "NONE", "symbol": None, "direction": None, "status": "no_action"})

        blocked = SimpleNamespace(action=SimpleNamespace(value="OPEN"), option=option, target_symbol="", target_direction=None, dispatchable=False)
        self.assertEqual(normalize_parsed_signal(blocked)["decision"], {"action": "NONE", "symbol": None, "direction": None, "status": "no_action"})

    def test_v4_safety_metrics_use_the_same_labels(self):
        record = {
            "cluster_id": "cluster-0001",
            "cluster_review_status": "confirmed",
            "contamination_status": "clear",
            "independent_label": self.ready_label({"action": "NONE", "symbol": None, "direction": None, "status": "no_action"}),
            "v4_baseline": {"action": "OPEN", "symbol": "SPY", "direction": "LONG", "status": "actionable"},
            "model_output": {"action": "NONE", "symbol": None, "direction": None, "status": "no_action"},
            "latency_ms": 100,
        }
        report = score_records([record])
        self.assertEqual(report["v4_critical_errors"], 1)
        self.assertEqual(report["v4_false_execution_rate"], 1)
        self.assertEqual(report["v4_safe_handling_rate"], 0)

    def test_v4_baseline_requires_unviewed_hash_locked_labels(self):
        root = Path(__file__).resolve().parents[1]
        cases = root / "data" / "holdout" / "protocol.json"
        labels = root / "data" / "labels" / "README.md"
        lock = {
            "protocol_id": "v5-prospective-1",
            "labels_locked": True,
            "outcomes_viewed": False,
            "case_file": "data/holdout/protocol.json",
            "case_file_sha256": hashlib.sha256(cases.read_bytes()).hexdigest(),
            "label_file": "data/labels/README.md",
            "label_file_sha256": hashlib.sha256(labels.read_bytes()).hexdigest(),
        }
        verify_label_lock(lock, cases, root)
        lock["outcomes_viewed"] = True
        with self.assertRaises(ValueError):
            verify_label_lock(lock, cases, root)

    def test_reviewed_clusters_are_required_for_label_queue(self):
        case = {
            "case_id": "c1",
            "cluster_id": "cluster-1",
            "cluster_review_status": "pending_review",
            "source_message_id": "m1",
            "message_timestamp": "2026-07-13T10:00:00-04:00",
            "raw_text": "open SPY long",
        }
        with self.assertRaises(ValueError):
            build_label_queue([case])
        reviewed = apply_cluster_reviews([case], {"cluster-1": "confirm"})
        queue = build_label_queue(reviewed)
        self.assertEqual(queue[0]["case_id"], "c1")
        self.assertNotIn("parser_decision", queue[0])


if __name__ == "__main__":
    unittest.main()
