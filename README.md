# Polygon converter

[![PyPI](https://img.shields.io/pypi/v/polyconv)](https://pypi.org/project/polyconv/)

Polygon refers to Codeforces' [Polygon](https://polygon.codeforces.com/).

This package creates a copy of the tests, renames the tests and outputs a string that can be used
for the `Score Parameters` field (use `GroupMin` score type) for
[Contest Management System (CMS)](https://cms-dev.github.io/). The renamed tests and the
score parameters capture Polygon's subtasks (groups) and dependencies in CMS.

This code uses `problem.xml` in the Polygon **full** package (either Windows or Linux is fine) to retrieve information about subtasks.

## How To Use

- Install this package: `pip install polyconv`
- Groups may use Polygon's `COMPLETE_GROUP` or `EACH_TEST` points policy.
- Generate a **full** package on Polygon for your problem and download the Linux version.
- Run `polyconv polygon_path`, where `polygon_path` is the path to the Polygon **full** package's root directory (where the folders `statements/` and `tests/` are). Add the `-f` flag to overwrite files if they exist.
- A new folder `cms_out` will be created in `polygon_path` (this can be changed with `-o`) containing the following:
  - A folder `tests/` containing renamed tests.
  - A `.zip` file `tests.zip` with the contents in the `tests/` folder above.
  - A `score_params.txt` file with the score parameters string. You should copy this to the Score Parameters field in CMS (use GroupMin score type).
- To also extract OutputOnly tests, pass `--output-only SUBSTRING`. Any test whose group name contains `SUBSTRING` remains in the Batch files and is additionally written to:
  - `output_only.zip`, using `input.XX.txt` and `output.XX.txt` names.
  - `attachment.zip`, using input-only `input_XX.txt` names.
  - Matching tests are ordered by their original Polygon test number and renumbered from `00`. Two digits are the minimum width, not a test-count limit.
- To also create `samples.zip`, pass `--samples GROUP`. This uses exact group matching and preserves converted Batch names such as `input.01_sample` and `output.01_sample`.
- The string in `score_params.txt` will also be output to the standard output.
