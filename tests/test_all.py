from __future__ import annotations

import numpy as np
import pytest
from pytest_cases import fixture, parametrize

import mfpbench
from mfpbench import Benchmark, YAHPOBenchmark

SEED = 1

# We can get all the benchmarks her
available_benchmarks = [(name, task_id) for name, _, task_id in mfpbench.available()]


# We expect the default download location for each
@fixture(scope="module")
@parametrize(item=available_benchmarks)
def benchmark(item: tuple[str, str | None]) -> Benchmark:
    """The JAHSBench series of benchmarks"""
    name, task_id = item
    benchmark = mfpbench.get(name=name, task_id=task_id, seed=SEED)

    # We force benchmarks to load if they must
    benchmark.load()

    return benchmark


@parametrize("n_samples", [1, 10, 100])
def test_benchmark_sampling(benchmark: Benchmark, n_samples: int) -> None:
    """
    Expects
    -------
    * Can sample 1 or many configs
    * They are all of type benchmark.Config
    * All sampled configs are valid
    """
    config = benchmark.sample()
    assert isinstance(config, benchmark.Config)
    config.validate()

    configs = benchmark.sample(n_samples)
    assert len(configs) == n_samples
    assert all(isinstance(config, benchmark.Config) for config in configs)

    for config in configs:
        config.validate()


def test_query_api_validity(benchmark: Benchmark) -> None:
    """
    Expects
    -------
    * Can query a sampled config
    * Can query from a Configuration from config space
    * Can query with the dict version of either of the above
    """
    sample = benchmark.sample()
    result = benchmark.query(sample)
    assert result.config == sample

    sample_dict = sample.dict()
    result = benchmark.query(sample_dict)
    assert result.config == sample_dict

    configspace_sample = benchmark.space.sample_configuration()
    result = benchmark.query(configspace_sample)
    assert result.config == configspace_sample

    configspace_sample_dict = {**configspace_sample}
    result = benchmark.query(configspace_sample_dict)
    assert result.config == configspace_sample_dict


def test_query_through_entire_fidelity_range(benchmark: Benchmark) -> None:
    """
    Expects
    -------
    * Should be able to query the benchmark over the entire fidelity range
    * All results should have their fidelity between the start and step
    """
    start, stop, step = benchmark.fidelity_range
    dtype = int if isinstance(start, int) else float
    fidelities = np.arange(start=start, stop=step, step=step, dtype=dtype)

    config = benchmark.sample()

    results = [benchmark.query(config, at=x) for x in fidelities]
    for r in results:
        assert start <= r.fidelity <= stop
        assert r.config == config


def test_repeated_query(benchmark: Benchmark) -> None:
    """
    Expects
    -------
    * Repeating the same query multiple times will give the same results
    """
    configs = benchmark.sample(10)
    for f in benchmark.iter_fidelities():

        results1 = [benchmark.query(config, at=f) for config in configs]
        results2 = [benchmark.query(config, at=f) for config in configs]

        for r1, r2 in zip(results1, results2):
            assert r1 == r2, f"{r1}\n{r2}"


def test_repeated_trajectory(benchmark: Benchmark) -> None:
    """
    Expects
    -------
    * Repeating the same trajectory multiple times will give the same results
    """
    configs = benchmark.sample(10)

    for config in configs:

        results = np.asarray(
            [[benchmark.trajectory(config)] for _ in range(3)],
            dtype=object,
        )

        for row in results.T:
            first = row[0]
            for other in row[1:]:
                assert first == other


def test_query_default_is_max_fidelity(benchmark: Benchmark) -> None:
    """
    Expects
    -------
    * A query with no args is the same as using the max fidelity directly
    """
    config = benchmark.sample()
    r1 = benchmark.query(config, at=benchmark.end)
    r2 = benchmark.query(config)

    assert r1 == r2


def test_query_same_as_trajectory(benchmark: Benchmark) -> None:
    """
    Expects
    -------
    * Querying every point individually should be the same as using trajectory
    """
    config = benchmark.sample()
    if isinstance(benchmark, YAHPOBenchmark):
        pytest.skip(
            "YAHPOBench gives slight numerical instability when querying in bulk vs"
            " each config individually."
        )

    query_results = [benchmark.query(config, at=f) for f in benchmark.iter_fidelities()]
    trajectory_results = benchmark.trajectory(config)

    for qr, tr in zip(query_results, trajectory_results):
        assert qr == tr, f"{qr}\n{tr}"


def test_trajectory_is_over_full_range_by_default(benchmark: Benchmark) -> None:
    """
    Expects
    -------
    * The trajectory should by default go from the start fidelity to the max
    """
    config = benchmark.sample()
    results = benchmark.trajectory(config)

    for r, fidelity in zip(results, benchmark.iter_fidelities()):
        assert r.fidelity == fidelity
