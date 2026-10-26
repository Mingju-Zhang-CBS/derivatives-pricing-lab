import pytest


def test_quantlib_parameter_grid():
    pytest.importorskip('QuantLib')
    from pricing_lab.diagnostics.benchmark import compare_grid
    result = compare_grid()
    assert len(result) == 1296
    assert result.filter(like='_error').abs().max().max() < 1e-8
