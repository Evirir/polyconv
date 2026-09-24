"""Create CMS archives and score parameters from Polygon tests."""

import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from string import Template

POLYGON_TESTS_DIR = "tests"
DEFAULT_OUT_DIR = "cms_out"
DEFAULT_CMS_TESTS_DIR = "tests"
DEFAULT_CMS_TESTS_ZIP_NAME = "tests"
DEFAULT_OUTPUT_ONLY_DIR = "output_only"
DEFAULT_OUTPUT_ONLY_ZIP_NAME = "output_only"
DEFAULT_OUTPUT_ONLY_ATTACHMENT_DIR = "attachment"
DEFAULT_OUTPUT_ONLY_ATTACHMENT_ZIP_NAME = "attachment"
DEFAULT_SAMPLES_DIR = "samples"
DEFAULT_SAMPLES_ZIP_NAME = "samples"
POLYGON_INPUT_TEMPLATE = Template("$id")
POLYGON_OUTPUT_TEMPLATE = Template("$id.a")
DEFAULT_CMS_INPUT_TEMPLATE = Template("input.${id}_$group")
DEFAULT_CMS_OUTPUT_TEMPLATE = Template("output.${id}_$group")
OUTPUT_ONLY_INPUT_TEMPLATE = Template("input.$id.txt")
OUTPUT_ONLY_OUTPUT_TEMPLATE = Template("output.$id.txt")
OUTPUT_ONLY_ATTACHMENT_INPUT_TEMPLATE = Template("input_$id.txt")
DEFAULT_GROUPS_REGEX = Template(".*_($groups)")
DEFAULT_EACH_TEST_REGEX = Template(".*${id}_$group")
DEFAULT_SCORE_PARAMS_FILENAME = "score_params.txt"


def dfs(dependencies: dict[str, set[str]], visited: set[str], group: str) -> None:
    """Add transitive prerequisites to one group."""
    if group in visited:
        return
    visited.add(group)
    new_prereqs = dependencies[group].copy()
    new_prereqs.add(group)
    for prereq in dependencies[group]:
        dfs(dependencies, visited, prereq)
        new_prereqs |= dependencies[prereq]
    dependencies[group] = new_prereqs


def copy_children_prereqs(dependencies: dict[str, set[str]]) -> None:
    """Add all transitive dependencies and each group itself."""
    visited = set()
    for group in dependencies:
        dfs(dependencies, visited, group)


def parse_dependencies(groups: list[ET.Element]) -> dict[str, list[str]]:
    """Return a mapping from group names to transitive prerequisites."""
    dependencies: dict[str, set[str]] = {}

    for group in groups:
        name = group.get("name")
        if name is None:
            raise ValueError("Group has no name")
        prereqs = group.find("dependencies")
        if prereqs is not None:
            prereqs = prereqs.findall("dependency")
        else:
            prereqs = []
        dependencies[name] = set()
        for prereq in prereqs:
            if (prereq_group := prereq.get("group")) is None:
                raise ValueError("Prerequisite is missing a group")
            dependencies[name].add(prereq_group)

    copy_children_prereqs(dependencies)
    return {group: sorted(prereqs) for group, prereqs in dependencies.items()}


def enumerate_tests(tests: ET.Element) -> list[tuple[str, ET.Element]]:
    """Pair tests with their one-based, zero-padded Polygon test numbers."""
    width = len(str(len(tests)))
    return [
        (str(test_id).zfill(width), test) for test_id, test in enumerate(tests, start=1)
    ]


def select_output_only_tests(
    numbered_tests: list[tuple[str, ET.Element]], group_substring: str
) -> list[tuple[str, ET.Element]]:
    """Select tests whose group contains the output-only substring."""
    if not group_substring:
        raise ValueError("The output-only group substring cannot be empty.")

    selected = [
        (test_id, test)
        for test_id, test in numbered_tests
        if group_substring in (test.get("group") or "")
    ]
    if not selected:
        raise ValueError(
            f'No test groups contain the output-only substring "{group_substring}".'
        )
    return selected


def select_exact_group_tests(
    numbered_tests: list[tuple[str, ET.Element]], group_name: str
) -> list[tuple[str, ET.Element]]:
    """Select tests whose group exactly matches the requested group name."""
    if not group_name:
        raise ValueError("The samples group name cannot be empty.")

    selected = [
        (test_id, test)
        for test_id, test in numbered_tests
        if test.get("group") == group_name
    ]
    if not selected:
        raise ValueError(f'No tests use the samples group "{group_name}".')
    return selected


def rename_tests(
    numbered_tests: list[tuple[str, ET.Element]],
    polygon_path: Path,
    output_path: Path,
    overwrite: bool = False,
) -> None:
    """Copy all Polygon tests and rename them to CMS Batch format.

    Args:
        numbered_tests: Polygon tests paired with their source test numbers.
        polygon_path: Path to the Polygon package folder.
        output_path: Path to the generated output folder.
        overwrite: Whether to replace an existing output folder.
    """
    # Check if cms_tests/ exists, delete if true
    if output_path.exists():
        if not overwrite:
            raise FileExistsError(
                "The output folder already exists. Delete it or use the --force flag "
                "to overwrite."
            )

        shutil.rmtree(output_path)

    cms_tests_dir = output_path / DEFAULT_CMS_TESTS_DIR
    shutil.copytree(polygon_path / POLYGON_TESTS_DIR, cms_tests_dir, dirs_exist_ok=True)

    for test_id, test in numbered_tests:
        group = test.get("group")
        if group is None:
            raise ValueError(f"Test {test_id} has no group")

        polygon_input_name = cms_tests_dir / POLYGON_INPUT_TEMPLATE.substitute(
            id=test_id
        )
        polygon_output_name = cms_tests_dir / POLYGON_OUTPUT_TEMPLATE.substitute(
            id=test_id
        )
        cms_input_name = cms_tests_dir / DEFAULT_CMS_INPUT_TEMPLATE.substitute(
            id=test_id, group=group
        )
        cms_output_name = cms_tests_dir / DEFAULT_CMS_OUTPUT_TEMPLATE.substitute(
            id=test_id, group=group
        )

        polygon_input_name.rename(cms_input_name)
        polygon_output_name.rename(cms_output_name)

    shutil.make_archive(
        (output_path / DEFAULT_CMS_TESTS_ZIP_NAME).as_posix(),
        "zip",
        root_dir=cms_tests_dir,
    )


def extract_output_only_tests(
    selected_tests: list[tuple[str, ET.Element]],
    polygon_path: Path,
    output_path: Path,
) -> None:
    """Create CMS OutputOnly dataset and input-only attachment archives.

    Args:
        selected_tests: Matching tests in ascending Polygon test-number order.
        polygon_path: Path to the Polygon package folder.
        output_path: Path to the generated output folder.
    """
    output_only_dir = output_path / DEFAULT_OUTPUT_ONLY_DIR
    attachment_dir = output_path / DEFAULT_OUTPUT_ONLY_ATTACHMENT_DIR
    output_only_dir.mkdir()
    attachment_dir.mkdir()

    for output_id, (polygon_id, _) in enumerate(selected_tests):
        output_id_string = f"{output_id:02d}"
        polygon_input = (
            polygon_path
            / POLYGON_TESTS_DIR
            / POLYGON_INPUT_TEMPLATE.substitute(id=polygon_id)
        )
        polygon_output = (
            polygon_path
            / POLYGON_TESTS_DIR
            / POLYGON_OUTPUT_TEMPLATE.substitute(id=polygon_id)
        )
        shutil.copy2(
            polygon_input,
            output_only_dir
            / OUTPUT_ONLY_INPUT_TEMPLATE.substitute(id=output_id_string),
        )
        shutil.copy2(
            polygon_output,
            output_only_dir
            / OUTPUT_ONLY_OUTPUT_TEMPLATE.substitute(id=output_id_string),
        )
        shutil.copy2(
            polygon_input,
            attachment_dir
            / OUTPUT_ONLY_ATTACHMENT_INPUT_TEMPLATE.substitute(id=output_id_string),
        )

    shutil.make_archive(
        (output_path / DEFAULT_OUTPUT_ONLY_ZIP_NAME).as_posix(),
        "zip",
        root_dir=output_only_dir,
    )
    shutil.make_archive(
        (output_path / DEFAULT_OUTPUT_ONLY_ATTACHMENT_ZIP_NAME).as_posix(),
        "zip",
        root_dir=attachment_dir,
    )


def extract_samples(
    selected_tests: list[tuple[str, ET.Element]], output_path: Path
) -> None:
    """Create an archive of exact-group samples using converted Batch names.

    Args:
        selected_tests: Tests from the exact requested samples group.
        output_path: Path to the generated output folder.
    """
    cms_tests_dir = output_path / DEFAULT_CMS_TESTS_DIR
    samples_dir = output_path / DEFAULT_SAMPLES_DIR
    samples_dir.mkdir()

    for test_id, test in selected_tests:
        group = test.get("group")
        if group is None:
            raise ValueError(f"Test {test_id} has no group")
        input_name = DEFAULT_CMS_INPUT_TEMPLATE.substitute(id=test_id, group=group)
        output_name = DEFAULT_CMS_OUTPUT_TEMPLATE.substitute(id=test_id, group=group)
        shutil.copy2(cms_tests_dir / input_name, samples_dir / input_name)
        shutil.copy2(cms_tests_dir / output_name, samples_dir / output_name)

    shutil.make_archive(
        (output_path / DEFAULT_SAMPLES_ZIP_NAME).as_posix(),
        "zip",
        root_dir=samples_dir,
    )


def get_score_params(
    groups: list[ET.Element],
    dependencies: dict[str, list[str]],
    numbered_tests: list[tuple[str, ET.Element]],
) -> str:
    """Return CMS GroupMin score parameters for all Polygon group policies."""
    tests_by_group: dict[str, list[tuple[str, ET.Element]]] = {}
    for test_id, test in numbered_tests:
        group_name = test.get("group")
        if group_name is None:
            raise ValueError(f"Test {test_id} has no group")
        tests_by_group.setdefault(group_name, []).append((test_id, test))

    score_params = []
    for group in groups:
        name = group.get("name")
        if name is None:
            raise ValueError("Group has no name")
        points_policy = group.get("points-policy", "complete-group")

        if points_policy == "complete-group":
            points = int(float(group.get("points", 0)))
            groups_string = "|".join(dependencies[name])
            score_params.append(
                [points, DEFAULT_GROUPS_REGEX.substitute(groups=groups_string)]
            )
            continue

        if points_policy != "each-test":
            raise ValueError(
                f'Group "{name}" uses unsupported points policy "{points_policy}".'
            )

        prerequisite_groups = [group for group in dependencies[name] if group != name]
        prerequisite_regex = DEFAULT_GROUPS_REGEX.substitute(
            groups="|".join(prerequisite_groups)
        )
        for test_id, test in tests_by_group.get(name, []):
            points = int(float(test.get("points", 0)))
            test_regex = DEFAULT_EACH_TEST_REGEX.substitute(id=test_id, group=name)
            if prerequisite_groups:
                test_regex = f"{test_regex}|{prerequisite_regex}"
            score_params.append([points, test_regex])

    return json.dumps(score_params)


def generate_cms_tests(
    polygon_path: Path,
    output_path: Path | str | None = None,
    overwrite: bool = False,
    output_only: str | None = None,
    samples: str | None = None,
) -> str:
    """Generate CMS Batch files and optional OutputOnly and samples archives.

    Args:
        polygon_path: Path to the Polygon package folder.
        output_path: Generated output folder. Defaults to ``<polygon_path>/cms_out``.
        overwrite: Whether to replace an existing output folder.
        output_only: Group-name substring selecting tests for OutputOnly archives.
        samples: Exact group name selecting tests for the samples archive.

    Returns:
        The CMS GroupMin score parameters string.
    """
    if output_path is None:
        output_path = polygon_path / DEFAULT_OUT_DIR
    else:
        output_path = Path(output_path)

    tree = ET.parse(polygon_path / "problem.xml")
    groups = tree.findall("judging/testset/groups/group")
    tests = tree.find("judging/testset/tests")
    if tests is None:
        raise ValueError("No tests found in problem.xml.")

    numbered_tests = enumerate_tests(tests)
    selected_output_only_tests = None
    if output_only is not None:
        selected_output_only_tests = select_output_only_tests(
            numbered_tests, output_only
        )
    selected_samples = None
    if samples is not None:
        selected_samples = select_exact_group_tests(numbered_tests, samples)

    rename_tests(numbered_tests, polygon_path, output_path, overwrite=overwrite)
    if selected_output_only_tests is not None:
        extract_output_only_tests(selected_output_only_tests, polygon_path, output_path)
    if selected_samples is not None:
        extract_samples(selected_samples, output_path)

    dependencies = parse_dependencies(groups)
    score_params = get_score_params(groups, dependencies, numbered_tests)
    with open(
        output_path / DEFAULT_SCORE_PARAMS_FILENAME, "w", encoding="utf-8"
    ) as file:
        file.write(score_params)

    return score_params
