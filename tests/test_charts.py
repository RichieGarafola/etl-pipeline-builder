"""
Regression tests for the "Row Count After Each Step" chart.

Plotly places bars that share an x category in the same slot and stacks
them, so two executions of a step with the same name (e.g. two
NormalizeText steps) rendered as one bar of double height. Every executed
step must get its own x position.
"""

from src.charts import build_row_count_figure
from src.pipeline import run_pipeline, default_steps
from src.transformer import NormalizeText, DropDuplicates


def _bar(result):
    return build_row_count_figure(result).data[0]


def test_default_pipeline_has_repeated_step_names():
    # Precondition for the regression: the sample pipeline repeats a name.
    names = [r.name for r in run_pipeline(default_steps()).step_log]
    assert len(names) == 9
    assert len(set(names)) < len(names)


def test_each_executed_step_has_distinct_x_position():
    result = run_pipeline(default_steps())
    bar = _bar(result)
    assert len(bar.x) == len(result.step_log) + 1
    assert len(set(bar.x)) == len(bar.x)


def test_bar_values_match_audit_trail_in_order():
    result = run_pipeline(default_steps())
    bar = _bar(result)
    expected = [result.rows_extracted] + [r.rows_out for r in result.step_log]
    assert list(bar.y) == expected
    assert list(bar.y) == [90, 90, 90, 80, 76, 76, 76, 76, 76, 76]


def test_no_position_sums_counts_across_executions():
    # Summing y per x position must never exceed the largest audit count.
    result = run_pipeline(default_steps())
    bar = _bar(result)
    per_position: dict = {}
    for x, y in zip(bar.x, bar.y):
        per_position[x] = per_position.get(x, 0) + y
    assert max(per_position.values()) == result.rows_extracted == 90


def test_repeated_name_labels_remain_visible():
    result = run_pipeline(default_steps())
    fig = build_row_count_figure(result)
    ticktext = [str(t).replace("<br>", " ") for t in fig.layout.xaxis.ticktext or ()]
    hover    = [c[0] for c in fig.data[0].customdata]
    assert ticktext[6:8] == ["6. Normalize Text", "7. Normalize Text"]
    assert hover[6:8] == ["6. Normalize Text", "7. Normalize Text"]


def test_generic_repeated_steps_not_merged():
    # Not specific to NormalizeText: any repeated step name stays separate.
    steps = [DropDuplicates(), DropDuplicates(), NormalizeText(columns=["status"])]
    result = run_pipeline(steps)
    bar = _bar(result)
    assert len(set(bar.x)) == 4
    assert list(bar.y) == [result.rows_extracted] + [r.rows_out for r in result.step_log]
