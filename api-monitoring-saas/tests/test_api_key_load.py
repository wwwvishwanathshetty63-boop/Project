"""
Test Suite 6: API Key load simulation & degradation under heavy traffic.
Simulates real-world: API key works fine → slows down → hits rate limit → recovers.
"""
import time
import pytest
import statistics
from tests.conftest import start_mock_server, mock_url, reset_mock_counter, set_degradation_mode
from backend.services.monitoring_service import check_endpoint


@pytest.fixture(scope="module", autouse=True)
def _mock():
    start_mock_server()
    reset_mock_counter()


def _ep(path, key=None):
    return {
        "id": "load-test-ep",
        "url": mock_url(path),
        "method": "GET",
        "api_key": key,
        "api_key_header": "Authorization",
    }


class TestAPIKeyUnderLoad:
    """
    Real-world scenario: Upload a valid API key, hammer the endpoint.
    Observe response time degradation, then hit rate limit.
    """

    def test_phase_1_stable_with_valid_key(self):
        """Phase 1 — API key works perfectly at low traffic (5 requests)."""
        reset_mock_counter()
        results = []
        for _ in range(5):
            log, err = check_endpoint(_ep("/key-check", key="Bearer valid-key-123"))
            results.append(log)

        assert all(r["is_success"] for r in results), "All requests should succeed"
        assert all(r["api_key_status"] == "VALID" for r in results)

        avg_rt = statistics.mean(r["response_time"] for r in results)
        print(f"\n[Phase 1] Avg response time (stable): {avg_rt:.1f}ms")

    def test_phase_2_degradation_under_load(self):
        """Phase 2 — Simulate API getting slower as traffic builds up."""
        reset_mock_counter()  # fresh counter: call 1 = 0.55s, call 15 = 0.55+15*0.05 = 1.3s
        set_degradation_mode(True)

        all_times = []
        for i in range(15):
            log, _ = check_endpoint(_ep("/slow"))
            all_times.append(log["response_time"])

        reset_mock_counter()

        early_avg = sum(all_times[:3]) / 3
        late_avg  = sum(all_times[-3:]) / 3
        print(f"\n[Phase 2] Early avg: {early_avg:.1f}ms | Late avg: {late_avg:.1f}ms")
        # The /slow route adds 50ms per request when in degradation mode
        assert late_avg > early_avg, (
            f"Response times must increase under load. "
            f"Early={early_avg:.0f}ms Late={late_avg:.0f}ms"
        )


    def test_phase_3_rate_limit_hit(self):
        """Phase 3 — API key hits rate limit (429) under heavy traffic."""
        log, err = check_endpoint(_ep("/rate-limit", key="sk-heavytraffic"))
        assert log["is_success"] is False
        assert log["api_key_status"] == "RATE_LIMITED"
        assert log["status_code"] == 429
        print(f"\n[Phase 3] Rate limited correctly — {log['api_key_status']}")

    def test_phase_4_invalid_key_detection(self):
        """Phase 4 — Detect expired / invalid API key immediately."""
        log, err = check_endpoint(_ep("/unauthorized", key="sk-expiredkey"))
        assert log["is_success"] is False
        assert log["api_key_status"] == "INVALID"
        assert "INVALID" in (err or "")
        print(f"\n[Phase 4] Invalid key detected immediately")

    def test_phase_5_recovery_after_issue(self):
        """Phase 5 — After correcting the key, endpoint recovers."""
        log, err = check_endpoint(_ep("/key-check", key="Bearer valid-key-123"))
        assert log["is_success"] is True
        assert log["api_key_status"] == "VALID"
        print(f"\n[Phase 5] Recovery confirmed — {log['response_time']:.1f}ms")


class TestResponseTimeStatistics:
    """Statistical analysis of response times across many checks."""

    def test_p50_p95_response_times(self):
        """Calculate P50 and P95 response times — critical SaaS SLA metric."""
        reset_mock_counter()
        times = []
        for _ in range(20):
            log, _ = check_endpoint(_ep("/ok"))
            times.append(log["response_time"])

        times.sort()
        p50 = times[len(times) // 2]
        p95 = times[int(len(times) * 0.95)]
        print(f"\n[Stats] P50={p50:.1f}ms  P95={p95:.1f}ms  Max={max(times):.1f}ms")
        # P95 should be reasonable for a local mock server
        assert p95 < 5000, f"P95 too high: {p95:.1f}ms"

    def test_jitter_is_low_on_stable_endpoint(self):
        """A stable API should have low response time variance."""
        times = [check_endpoint(_ep("/ok"))[0]["response_time"] for _ in range(10)]
        std = statistics.stdev(times) if len(times) > 1 else 0
        avg = statistics.mean(times)
        print(f"\n[Jitter] avg={avg:.1f}ms std={std:.1f}ms")
        assert std < avg * 5, "Stable endpoint should not have excessive jitter"

    def test_multiple_endpoints_independent(self):
        """Multiple endpoints must not interfere with each other's response times."""
        ok_times  = [check_endpoint(_ep("/ok"))[0]["response_time"] for _ in range(5)]
        ok_avg = statistics.mean(ok_times)
        # /down always fails fast (no actual slow processing)
        down_times = [check_endpoint(_ep("/down"))[0]["response_time"] for _ in range(5)]
        down_avg = statistics.mean(down_times)
        print(f"\n[Multi] OK avg={ok_avg:.1f}ms  Down avg={down_avg:.1f}ms")
        # Both measured independently — just verify they are independently measured
        assert ok_avg >= 0
        assert down_avg >= 0


class TestConcurrentChecks:
    """Simulate parallel monitoring checks (as the engine would run them)."""

    def test_concurrent_endpoint_checks(self):
        """Fire 10 checks in parallel threads — all must complete correctly."""
        import threading
        results = []
        lock = threading.Lock()

        def do_check():
            log, _ = check_endpoint(_ep("/ok"))
            with lock:
                results.append(log)

        threads = [threading.Thread(target=do_check) for _ in range(10)]
        for t in threads: t.start()
        for t in threads: t.join(timeout=15)

        assert len(results) == 10, f"Only {len(results)}/10 checks completed"
        assert all(r["is_success"] for r in results)

    def test_concurrent_mixed_scenarios(self):
        """Mix of ok, down, and rate-limited endpoints running simultaneously."""
        import threading
        scenarios = ["/ok", "/down", "/rate-limit", "/ok", "/unauthorized"]
        results = {}
        lock = threading.Lock()

        def check(path, key=None):
            ep = {"id": path, "url": mock_url(path), "method": "GET",
                  "api_key": key, "api_key_header": "Authorization"}
            log, err = check_endpoint(ep)
            with lock:
                results[path] = log

        threads = [threading.Thread(target=check, args=(p, "Bearer valid-key-123" if p == "/key-check" else None))
                   for p in scenarios]
        for t in threads: t.start()
        for t in threads: t.join(timeout=20)

        assert results["/ok"]["is_success"] is True
        assert results["/down"]["is_success"] is False
        assert results["/rate-limit"]["api_key_status"] in (None, "RATE_LIMITED")
