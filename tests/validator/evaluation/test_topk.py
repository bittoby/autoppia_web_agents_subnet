"""
Unit tests for validator.evaluation.topk (canonicalization, fingerprints, similarity).
"""

from types import SimpleNamespace

import pytest


@pytest.mark.unit
class TestNormTextBucket:
    def test_norm_text_bucket_none(self):
        from autoppia_web_agents_subnet.validator.evaluation.topk import _norm_text_bucket

        assert _norm_text_bucket(None) == ("len_0", "pat_none")

    def test_norm_text_bucket_short(self):
        from autoppia_web_agents_subnet.validator.evaluation.topk import _norm_text_bucket

        bl, pat = _norm_text_bucket("hi")
        assert bl == "len_1_5"
        assert pat.startswith("pat_")

    def test_norm_text_bucket_long(self):
        from autoppia_web_agents_subnet.validator.evaluation.topk import _norm_text_bucket

        bl, _ = _norm_text_bucket("a" * 100)
        assert bl == "len_81p"


@pytest.mark.unit
class TestNormUrl:
    def test_norm_url_none(self):
        from autoppia_web_agents_subnet.validator.evaluation.topk import _norm_url

        assert _norm_url(None) == "url:none"

    def test_norm_url_returns_prefix(self):
        from autoppia_web_agents_subnet.validator.evaluation.topk import _norm_url

        out = _norm_url("https://example.com/path/to/page")
        assert out.startswith("url:")
        assert len(out) == 4 + 8  # "url:" + 8-char md5 hex


@pytest.mark.unit
class TestCanonicalToken:
    def test_canonical_token_consistent(self):
        from autoppia_web_agents_subnet.validator.evaluation.topk import canonical_token

        action = SimpleNamespace(type="click", selector=None, text="hello", value=None, url=None)
        for _ in ("up", "down", "left", "right"):
            if not hasattr(action, _):
                setattr(action, _, False)
        action.x = action.y = None
        t1 = canonical_token(action)
        t2 = canonical_token(action)
        assert t1 == t2
        assert len(t1) == 12

    def test_canonical_token_different_actions_different_tokens(self):
        from autoppia_web_agents_subnet.validator.evaluation.topk import canonical_token

        a1 = SimpleNamespace(type="click", selector=None, text="a", value=None, url=None)
        a2 = SimpleNamespace(type="click", selector=None, text="b", value=None, url=None)
        for a in (a1, a2):
            for d in ("up", "down", "left", "right"):
                setattr(a, d, False)
            a.x = a.y = None
        assert canonical_token(a1) != canonical_token(a2)


@pytest.mark.unit
class TestCanonicalSequence:
    def test_canonical_sequence(self):
        from autoppia_web_agents_subnet.validator.evaluation.topk import canonical_sequence

        action = SimpleNamespace(type="click", selector=None, text="x", value=None, url=None)
        for d in ("up", "down", "left", "right"):
            setattr(action, d, False)
        action.x = action.y = None
        sol = SimpleNamespace(actions=[action])
        tokens = canonical_sequence(sol)
        assert len(tokens) == 1
        assert len(tokens[0]) == 12


@pytest.mark.unit
class TestShingles:
    def test_shingles_short(self):
        from autoppia_web_agents_subnet.validator.evaluation.topk import shingles

        assert shingles(["a", "b"], k=4) == ["a|b"]

    def test_shingles_long(self):
        from autoppia_web_agents_subnet.validator.evaluation.topk import shingles

        tokens = ["a", "b", "c", "d", "e"]
        out = shingles(tokens, k=2)
        assert "a|b" in out
        assert "b|c" in out
        assert len(out) == 4


@pytest.mark.unit
class TestSeqHashEmbed:
    def test_seq_hash_embed_normalized(self):
        from autoppia_web_agents_subnet.validator.evaluation.topk import seq_hash_embed

        vec = seq_hash_embed(["a", "b", "c"], dim=256)
        assert len(vec) == 256
        norm = sum(x * x for x in vec) ** 0.5
        assert abs(norm - 1.0) < 1e-5

    def test_seq_hash_embed_empty(self):
        from autoppia_web_agents_subnet.validator.evaluation.topk import seq_hash_embed

        vec = seq_hash_embed([], dim=256)
        assert len(vec) == 256


@pytest.mark.unit
class TestCosine:
    def test_cosine_identical(self):
        from autoppia_web_agents_subnet.validator.evaluation.topk import cosine

        a = [1.0, 0.0, 0.0]
        assert cosine(a, a) == 1.0

    def test_cosine_orthogonal(self):
        from autoppia_web_agents_subnet.validator.evaluation.topk import cosine

        assert cosine([1.0, 0.0], [0.0, 1.0]) == 0.0


@pytest.mark.unit
class TestWeightedEditSimilarity:
    def test_weighted_edit_identical(self):
        from autoppia_web_agents_subnet.validator.evaluation.topk import weighted_edit_similarity

        assert weighted_edit_similarity(["a", "b"], ["a", "b"]) == 1.0

    def test_weighted_edit_both_empty(self):
        from autoppia_web_agents_subnet.validator.evaluation.topk import weighted_edit_similarity

        assert weighted_edit_similarity([], []) == 1.0

    def test_weighted_edit_different(self):
        from autoppia_web_agents_subnet.validator.evaluation.topk import weighted_edit_similarity

        sim = weighted_edit_similarity(["a"], ["b"])
        assert 0.0 <= sim < 1.0


@pytest.mark.unit
class TestBehaviorStats:
    def test_behavior_stats_length_32(self):
        from autoppia_web_agents_subnet.validator.evaluation.topk import behavior_stats

        out = behavior_stats(["a", "a", "b"])
        assert len(out) == 32
        assert abs(sum(out) - 1.0) < 1e-5 or sum(out) == 0


@pytest.mark.unit
class TestAggregateByMiner:
    def test_aggregate_by_miner_empty(self):
        from autoppia_web_agents_subnet.validator.evaluation.topk import aggregate_by_miner

        assert aggregate_by_miner([]) == 0.0

    def test_aggregate_by_miner_median_odd(self):
        from autoppia_web_agents_subnet.validator.evaluation.topk import aggregate_by_miner

        assert aggregate_by_miner([0.1, 0.5, 0.9]) == 0.5

    def test_aggregate_by_miner_median_even(self):
        from autoppia_web_agents_subnet.validator.evaluation.topk import aggregate_by_miner

        assert aggregate_by_miner([0.2, 0.4, 0.6, 0.8]) == 0.5


@pytest.mark.unit
class TestFingerprintSolution:
    def test_fingerprint_solution(self):
        from autoppia_web_agents_subnet.validator.evaluation.topk import (
            SolutionFingerprint,
            fingerprint_solution,
        )

        action = SimpleNamespace(type="click", selector=None, text="x", value=None, url=None)
        for d in ("up", "down", "left", "right"):
            setattr(action, d, False)
        action.x = action.y = None
        sol = SimpleNamespace(task_id="t1", actions=[action])
        fp = fingerprint_solution(sol)
        assert isinstance(fp, SolutionFingerprint)
        assert fp.task_id == "t1"
        assert len(fp.tokens) == 1
        assert len(fp.embed) == 256
        assert len(fp.stats) == 32


@pytest.mark.unit
class TestPairSimilarity:
    def test_pair_similarity_identical_fingerprints(self):
        from autoppia_web_agents_subnet.validator.evaluation.topk import (
            SolutionFingerprint,
            pair_similarity,
        )

        toks = ["abc"]
        sh = ["abc"]
        emb = [1.0] + [0.0] * 255
        st = [1.0] + [0.0] * 31
        fp = SolutionFingerprint("t1", toks, sh, None, emb, st)
        sim = pair_similarity(fp, fp)
        assert sim >= 0.99

    def test_pair_similarity_different(self):
        from autoppia_web_agents_subnet.validator.evaluation.topk import (
            SolutionFingerprint,
            pair_similarity,
        )

        fp1 = SolutionFingerprint("t1", ["a"], ["a"], None, [1.0] + [0.0] * 255, [1.0] + [0.0] * 31)
        fp2 = SolutionFingerprint("t1", ["b"], ["b"], None, [0.0, 1.0] + [0.0] * 254, [0.0, 1.0] + [0.0] * 30)
        sim = pair_similarity(fp1, fp2)
        assert 0.0 <= sim <= 1.0


@pytest.mark.unit
class TestGetSimilarityScore:
    def test_get_similarity_score(self):
        from autoppia_web_agents_subnet.validator.evaluation.topk import get_similarity_score

        action = SimpleNamespace(type="click", selector=None, text="x", value=None, url=None)
        for d in ("up", "down", "left", "right"):
            setattr(action, d, False)
        action.x = action.y = None
        sol1 = SimpleNamespace(task_id="t1", actions=[action])
        sol2 = SimpleNamespace(task_id="t1", actions=[action])
        score = get_similarity_score(sol1, sol2)
        assert 0.0 <= score <= 1.0
        assert score >= 0.9

    def test_get_similarity_score_assigns_task_id_when_missing(self):
        from autoppia_web_agents_subnet.validator.evaluation.topk import get_similarity_score

        action = SimpleNamespace(type="click", selector=None, text="x", value=None, url=None)
        for d in ("up", "down", "left", "right"):
            setattr(action, d, False)
        action.x = action.y = None
        sol1 = SimpleNamespace(actions=[action])
        sol2 = SimpleNamespace(actions=[action])
        assert not hasattr(sol1, "task_id")
        score = get_similarity_score(sol1, sol2)
        assert hasattr(sol1, "task_id") and sol1.task_id == "_task"
        assert 0.0 <= score <= 1.0


@pytest.mark.unit
class TestCandidateIndex:
    def test_candidate_index_add_query(self):
        from autoppia_web_agents_subnet.validator.evaluation.topk import (
            CandidateIndex,
            SolutionFingerprint,
        )

        fp = SolutionFingerprint("t1", ["a"], ["a"], None, [1.0] + [0.0] * 255, [1.0] + [0.0] * 31)
        idx = CandidateIndex(threshold=0.6)
        idx.add("key1", fp)
        assert "key1" in idx._store


@pytest.mark.unit
class TestClusterMiners:
    def test_cluster_miners_empty(self):
        from autoppia_web_agents_subnet.validator.evaluation.topk import cluster_miners

        result = cluster_miners([], {}, tau=0.85)
        assert result == []  # returns list of clusters (sets)

    def test_cluster_miners_single(self):
        from autoppia_web_agents_subnet.validator.evaluation.topk import cluster_miners

        result = cluster_miners(["m1"], {}, tau=0.85)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0] == {"m1"}


@pytest.mark.unit
class TestCompareSolutions:
    def test_compare_solutions_empty(self):
        from autoppia_web_agents_subnet.validator.evaluation.topk import compare_solutions

        result = compare_solutions([], min_shared_tasks=1, tau=0.5)
        assert result == {}

    def test_compare_solutions_single_miner(self):
        from autoppia_web_agents_subnet.validator.evaluation.topk import compare_solutions

        action = SimpleNamespace(type="click", selector=None, text="x", value=None, url=None)
        for d in ("up", "down", "left", "right"):
            setattr(action, d, False)
        action.x = action.y = None
        sol = SimpleNamespace(miner_id="m1", task_id="t1", actions=[action])
        result = compare_solutions([sol], min_shared_tasks=1, tau=0.5)
        assert "m1" in result
        assert result["m1"] == ["m1"]
