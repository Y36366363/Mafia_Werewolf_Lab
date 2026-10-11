"""Selection isolation, balanced seed blocks and independent artifact auditing."""

from copy import deepcopy
from hashlib import sha256
from itertools import permutations
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mafia_lab import large_experiment
from mafia_lab.large_experiment import build_spec, run_experiment, select_from_train
from mafia_lab.statistics import win_summary
from scripts.verify_large_game_v04 import pure_selection, validate_directory


ROOT = Path(__file__).resolve().parents[1]


def small_config():
    config = json.loads((ROOT / "configs/large_game_v04.json").read_text())
    config["good_policies"] = [p for p in config["good_policies"] if p["name"] in {"uncovered", "cover50"}]
    config["mafia_policies"] = [p for p in config["mafia_policies"] if p["name"] in {"signal_mimic", "history_mimic"}]
    config["good_contrasts"] = [{"control": "uncovered", "treatment": "cover50"}]
    config["mafia_contrasts"] = [{"control": "signal_mimic", "treatment": "history_mimic"}]
    for index, phase in enumerate(("train", "test", "sensitivity")):
        config[phase]["n"] = 3
        config[phase]["seed_start"] = 31_000_000 + 100 * index
    config["sensitivity"]["rule_variants"] = [config["sensitivity"]["rule_variants"][0]]
    return config


class TrainSelectionTests(unittest.TestCase):
    def test_policy_reordering_cannot_change_selection_or_tie_breaks(self):
        names_g, names_m = ["uncovered", "z", "a"], ["z", "a", "b"]
        rates = [[0.4, 0.1, 0.6], [0.7, 0.5, 0.2], [0.7, 0.5, 0.2]]
        expected = {
            "baseline_good": "uncovered", "mafia_response": "a", "good_response": "a",
            "second_mafia_response": "b", "robust_pure_good": "a",
            "robust_train_worst_mafia": "b", "tie_break": "lexicographic policy name, after objective",
        }
        for rows in permutations(range(3)):
            for cols in permutations(range(3)):
                reordered = [[rates[i][j] for j in cols] for i in rows]
                good, mafia = [names_g[i] for i in rows], [names_m[j] for j in cols]
                self.assertEqual(select_from_train(reordered, good, mafia), expected)
                self.assertEqual(pure_selection(reordered, good, mafia), expected)

    def test_input_data_is_not_mutated(self):
        rates = [[0.1, 0.4], [0.3, 0.2]]
        before = deepcopy(rates)
        select_from_train(rates, ["uncovered", "cover"], ["signal", "history"])
        self.assertEqual(rates, before)

    def test_invalid_rate_or_shape_rejected(self):
        for rates in ([[0.1], [0.2]], [[0.1, float("nan")], [0.2, 0.4]], [[0.1, -0.1], [0.2, 0.4]]):
            with self.assertRaises(ValueError):
                select_from_train(rates, ["uncovered", "cover"], ["signal", "history"])


class ProtocolValidationTests(unittest.TestCase):
    def test_seed_overlap_rejected_including_last_training_seed(self):
        config = small_config()
        config["test"]["seed_start"] = config["train"]["seed_start"] + config["train"]["n"] - 1
        with self.assertRaises(ValueError):
            build_spec(config)

    def test_adjacent_seed_blocks_are_disjoint(self):
        config = small_config()
        config["test"]["seed_start"] = config["train"]["seed_start"] + config["train"]["n"]
        build_spec(config)

    def test_invalid_sample_count_and_bool_seed_rejected(self):
        for phase, key, value in (("train", "n", 1), ("test", "n", True),
                                  ("sensitivity", "seed_start", True), ("train", "seed_start", -1)):
            config = small_config()
            config[phase][key] = value
            with self.assertRaises(ValueError):
                build_spec(config)

    def test_duplicate_names_and_unknown_contrast_rejected(self):
        config = small_config()
        config["good_policies"][1]["name"] = config["good_policies"][0]["name"]
        with self.assertRaises(ValueError):
            build_spec(config)
        config = small_config()
        config["good_contrasts"][0]["treatment"] = "unregistered"
        with self.assertRaises(ValueError):
            build_spec(config)


class SmallFrozenRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.directory = Path(cls.temp.name)
        cls.config = small_config()
        cls.manifest = run_experiment(cls.config, cls.directory, workers=1, progress=lambda _: None)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_small_run_independent_audit_and_archived_terminal_replay(self):
        result = validate_directory(self.directory, replay=True)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["executed_games"], self.manifest["executed_games"])
        self.assertEqual(result["distinct_seed_units"], 9)
        self.assertEqual(result["archived_game_replays"], 2 * result["checked_cells"])

    def test_balanced_raw_cells_and_pretest_selection(self):
        train, test = [json.loads((self.directory / f"{phase}.json").read_text()) for phase in ("train", "test")]
        selection = json.loads((self.directory / "selection_before_test.json").read_text())
        self.assertEqual(selection["selection"], train["selection"])
        self.assertEqual(selection["selection"], test["selection_from_train"])
        # Replacing every held-out payoff cannot change the training function's output.
        before = deepcopy(train)
        for cell in test["cells"]:
            cell["raw_outcomes"] = [1 - x for x in cell["raw_outcomes"]]
        self.assertEqual(select_from_train(train["matrix"]["rates"], train["matrix"]["good"],
                                          train["matrix"]["mafia"]), selection["selection"])
        self.assertEqual(before, train)
        for report in (train, test):
            expected = self.config[report["phase"]]
            self.assertEqual({(c["seed_start"], c["n"]) for c in report["cells"]},
                             {(expected["seed_start"], expected["n"])})

    def test_completed_output_cannot_be_overwritten(self):
        with self.assertRaises(ValueError):
            run_experiment(self.config, self.directory, workers=1, progress=lambda _: None)

    def test_selection_is_saved_before_test_and_invariant_to_inverted_test_results(self):
        expected = json.loads((self.directory / "selection_before_test.json").read_text())["selection"]
        original_evaluate = large_experiment.evaluate_cell
        test_calls = []
        with tempfile.TemporaryDirectory() as other:
            output = Path(other)

            def inverted_test(job):
                is_test = job[-1] == self.config["test"]["seed_start"]
                if is_test:
                    saved = json.loads((output / "selection_before_test.json").read_text())
                    self.assertEqual(saved["selection"], expected)
                    test_calls.append((job[1].name, job[2].name))
                cell = original_evaluate(job)
                if is_test:
                    cell["raw_outcomes"] = [1 - x for x in cell["raw_outcomes"]]
                    cell["summary"] = win_summary(cell["raw_outcomes"])
                return cell

            with patch("mafia_lab.large_experiment.evaluate_cell", side_effect=inverted_test):
                run_experiment(self.config, output, workers=1, progress=lambda _: None)
            self.assertEqual(len(test_calls), 4)
            test = json.loads((output / "test.json").read_text())
            self.assertEqual(test["selection_from_train"], expected)
            self.assertEqual(validate_directory(output)["status"], "passed")

    def test_outcome_or_seed_corruption_is_detected_even_with_updated_file_hash(self):
        # Update manifest SHA alongside malicious report edits so semantic checks,
        # not only integrity checks, must identify the inconsistency.
        original_report = (self.directory / "test.json").read_bytes()
        original_manifest = (self.directory / "manifest.json").read_bytes()
        try:
            for field in ("outcome", "seed", "familywise_interval"):
                report = json.loads(original_report)
                cell = report["cells"][0]
                if field == "outcome":
                    cell["raw_outcomes"][0] = 1 - cell["raw_outcomes"][0]
                elif field == "seed":
                    cell["seed_start"] += 1
                else:
                    report["all_prespecified_contrasts"][0]["paired"]["ci95_familywise_hoeffding"][0] = 0.99
                content = json.dumps(report).encode()
                (self.directory / "test.json").write_bytes(content)
                manifest = json.loads(original_manifest)
                manifest["files"]["test.json"] = sha256(content).hexdigest()
                (self.directory / "manifest.json").write_text(json.dumps(manifest))
                with self.assertRaises(ValueError):
                    validate_directory(self.directory)
        finally:
            (self.directory / "test.json").write_bytes(original_report)
            (self.directory / "manifest.json").write_bytes(original_manifest)

    def test_archived_source_corruption_is_detected(self):
        source = self.directory / "source/mafia_lab/strategies_v04.py"
        original = source.read_bytes()
        try:
            source.write_bytes(original + b"\n# altered\n")
            with self.assertRaises(ValueError):
                validate_directory(self.directory)
        finally:
            source.write_bytes(original)

    def test_archived_config_byte_and_entrypoint_hashes_are_verified(self):
        manifest = json.loads((self.directory / "manifest.json").read_text())
        self.assertIn("source/config.json", manifest["source_assets"])
        for relative in manifest["source_assets"]:
            path = self.directory / relative
            original = path.read_bytes()
            try:
                # Extra whitespace preserves JSON semantics but must fail its
                # byte-for-byte archival provenance check.
                path.write_bytes(original + b"\n")
                with self.assertRaises(ValueError):
                    validate_directory(self.directory)
            finally:
                path.write_bytes(original)

    def test_asset_manifest_rejects_missing_config_or_unknown_paths(self):
        path = self.directory / "manifest.json"
        original = path.read_bytes()
        try:
            for kind in ("missing_config", "unknown_path"):
                manifest = json.loads(original)
                if kind == "missing_config":
                    del manifest["source_assets"]["source/config.json"]
                else:
                    manifest["source_assets"]["source/unregistered.py"] = "0" * 64
                path.write_text(json.dumps(manifest))
                with self.assertRaises(ValueError):
                    validate_directory(self.directory)
        finally:
            path.write_bytes(original)


if __name__ == "__main__":
    unittest.main()
