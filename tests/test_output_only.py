"""Tests for mixed Batch and OutputOnly conversion."""

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

import pytest

from polyconv.cli.main import generate_test_data, make_parser
from polyconv.test_data import generate_cms_tests
from polyconv.test_data.test_data import (
    extract_output_only_tests,
    get_output_only_score_params,
    select_output_only_tests,
)


@pytest.fixture(name="polygon_path")
def fixture_polygon_path(tmp_path: Path) -> Path:
    """Create a self-contained Polygon package with mixed scoring policies."""
    polygon_path = tmp_path / "polygon"
    tests_path = polygon_path / "tests"
    tests_path.mkdir(parents=True)

    problem = ET.Element("problem")
    testset = ET.SubElement(ET.SubElement(problem, "judging"), "testset")
    tests = ET.SubElement(testset, "tests")
    test_data = [
        ("sample", "0"),
        ("sample", "0"),
        ("s1-OO", "30"),
        ("s1", "0"),
        ("s1", "0"),
        ("s2", "30"),
        ("s3", "40"),
    ]
    for test_id, (group, points) in enumerate(test_data, start=1):
        ET.SubElement(tests, "test", group=group, points=points)
        (tests_path / str(test_id)).write_text(f"input {test_id}")
        (tests_path / f"{test_id}.a").write_text(f"output {test_id}")

    groups = ET.SubElement(testset, "groups")
    s1 = ET.SubElement(groups, "group", name="s1", points="0")
    dependencies = ET.SubElement(s1, "dependencies")
    ET.SubElement(dependencies, "dependency", group="s1-OO")
    ET.SubElement(groups, "group", name="s1-OO", **{"points-policy": "each-test"})
    ET.SubElement(groups, "group", name="s2", points="30")
    s3 = ET.SubElement(groups, "group", name="s3", points="40")
    dependencies = ET.SubElement(s3, "dependencies")
    for group in ("s1", "s2", "sample"):
        ET.SubElement(dependencies, "dependency", group=group)
    ET.SubElement(groups, "group", name="sample", points="0")

    ET.ElementTree(problem).write(polygon_path / "problem.xml", encoding="unicode")
    return polygon_path


def test_archive_selection_cli_arguments() -> None:
    """Parse the optional OutputOnly substring and exact samples group."""
    args = make_parser().parse_args(
        ["package", "--output-only", "OO", "--samples", "sample"]
    )

    assert args.output_only == "OO"
    assert args.samples == "sample"


def test_output_only_selection_preserves_test_number_order() -> None:
    """Select every matching group without reordering its Polygon test number."""
    numbered_tests = [
        ("03", ET.Element("test", group="first-OO")),
        ("08", ET.Element("test", group="batch")),
        ("12", ET.Element("test", group="second-OO")),
    ]

    selected = select_output_only_tests(numbered_tests, "OO")

    assert [test_id for test_id, _ in selected] == ["03", "12"]


def test_output_only_selection_allows_more_than_100_tests() -> None:
    """Do not treat two-digit padding as a test-count limit."""
    numbered_tests = [
        (str(test_id), ET.Element("test", group="OO")) for test_id in range(101)
    ]

    selected = select_output_only_tests(numbered_tests, "OO")

    assert len(selected) == 101


def test_output_only_score_params_use_one_subtask_per_test() -> None:
    """Preserve each selected test's points in a one-test GroupMin subtask."""
    selected_tests = [
        ("03", ET.Element("test", group="first-OO", points="12")),
        ("12", ET.Element("test", group="second-OO", points="18")),
    ]

    score_params = get_output_only_score_params(selected_tests)

    assert json.loads(score_params) == [[12, 1], [18, 1]]


def test_output_only_numbering_continues_past_99(tmp_path: Path) -> None:
    """Keep two-digit minimum padding without limiting larger indexes."""
    polygon_path = tmp_path / "polygon"
    tests_path = polygon_path / "tests"
    tests_path.mkdir(parents=True)
    (tests_path / "1").write_text("input")
    (tests_path / "1.a").write_text("output")
    output_path = tmp_path / "output"
    output_path.mkdir()
    selected_tests = [("1", ET.Element("test", group="OO"))] * 101

    extract_output_only_tests(selected_tests, polygon_path, output_path)

    with ZipFile(output_path / "output_only.zip") as archive:
        assert "input.100.txt" in archive.namelist()
        assert "output.100.txt" in archive.namelist()
    with ZipFile(output_path / "attachment.zip") as archive:
        assert "input_100.txt" in archive.namelist()


def test_generate_mixed_batch_and_output_only_archives(
    tmp_path: Path, polygon_path: Path
) -> None:
    """Keep OO tests in Batch and create both OutputOnly archive formats."""
    output_path = tmp_path / "cms_out"

    score_params, output_only_score_params = generate_cms_tests(
        polygon_path,
        output_path=output_path,
        output_only="OO",
        samples="s1",
    )

    with ZipFile(output_path / "output_only.zip") as archive:
        assert set(archive.namelist()) == {"input.00.txt", "output.00.txt"}
        assert archive.read("input.00.txt") == (polygon_path / "tests/3").read_bytes()
        assert (
            archive.read("output.00.txt") == (polygon_path / "tests/3.a").read_bytes()
        )

    with ZipFile(output_path / "attachment.zip") as archive:
        assert archive.namelist() == ["input_00.txt"]
        assert archive.read("input_00.txt") == (polygon_path / "tests/3").read_bytes()

    with ZipFile(output_path / "samples.zip") as archive:
        assert set(archive.namelist()) == {
            f"{kind}.{test_id}_s1"
            for kind in ("input", "output")
            for test_id in range(4, 6)
        }

    with ZipFile(output_path / "tests.zip") as archive:
        assert "input.3_s1-OO" in archive.namelist()
        assert "output.3_s1-OO" in archive.namelist()

    parsed_score_params = json.loads(score_params)
    assert parsed_score_params[0] == [0, ".*_(s1|s1-OO)"]
    assert parsed_score_params[1] == [30, ".*3_s1-OO"]
    assert parsed_score_params[3] == [
        40,
        ".*_(s1|s1-OO|s2|s3|sample)",
    ]
    assert (output_path / "score_params.txt").read_text() == score_params
    assert json.loads(output_only_score_params) == [[30, 1]]
    assert (
        output_path / "output_only_score_params.txt"
    ).read_text() == output_only_score_params


def test_cli_outputs_both_score_params(
    tmp_path: Path, polygon_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Print separate Batch and OutputOnly score parameters when requested."""
    output_path = tmp_path / "cms_out"
    args = make_parser().parse_args(
        [str(polygon_path), "--out", str(output_path), "--output-only", "OO"]
    )

    generate_test_data(args)

    assert capsys.readouterr().out == (
        'CMS Batch Score Parameters:\n[[0, ".*_(s1|s1-OO)"], '
        '[30, ".*3_s1-OO"], [30, ".*_(s2)"], '
        '[40, ".*_(s1|s1-OO|s2|s3|sample)"], [0, ".*_(sample)"]]\n'
        "CMS OutputOnly Score Parameters:\n[[30, 1]]\n"
    )


def test_generate_samples_for_batch_without_output_only(
    tmp_path: Path, polygon_path: Path
) -> None:
    """Create exact-group samples independently of OutputOnly extraction."""
    output_path = tmp_path / "cms_out"

    _, output_only_score_params = generate_cms_tests(
        polygon_path, output_path=output_path, samples="sample"
    )

    with ZipFile(output_path / "samples.zip") as archive:
        assert set(archive.namelist()) == {
            f"{kind}.{test_id}_sample"
            for kind in ("input", "output")
            for test_id in range(1, 3)
        }
    assert output_only_score_params is None
    assert not (output_path / "output_only.zip").exists()
    assert not (output_path / "attachment.zip").exists()
    assert not (output_path / "output_only_score_params.txt").exists()


def test_output_only_substring_must_match_a_group(
    tmp_path: Path, polygon_path: Path
) -> None:
    """Reject a substring that selects no tests before creating output."""
    output_path = tmp_path / "cms_out"

    with pytest.raises(ValueError, match="No test groups contain"):
        generate_cms_tests(
            polygon_path,
            output_path=output_path,
            output_only="not-a-real-group",
        )

    assert not output_path.exists()
