#!/bin/bash

set -ex

ON_GITHUB_CI=true
EXIT_STATUS=0

# If not running on Github's CI, discard the summaries
if [ -z "${GITHUB_STEP_SUMMARY+x}" ]; then
    GITHUB_STEP_SUMMARY=/dev/null
    ON_GITHUB_CI=false
fi

# Autoformatter *first*, to avoid double-reporting errors
echo "::group::Ruff format"
if ! ruff format --check; then
    echo "* Ruff formatting found issues" >> "$GITHUB_STEP_SUMMARY"
    EXIT_STATUS=1
    ruff format --diff
    echo "::endgroup::"
    echo "::error:: Ruff formatting found issues"
else
    echo "::endgroup::"
fi

# Run ruff, configured in pyproject.toml
echo "::group::Ruff"
if ! ruff check .; then
    echo "* ruff found issues." >> "$GITHUB_STEP_SUMMARY"
    EXIT_STATUS=1
    if $ON_GITHUB_CI; then
        ruff check --output-format github --diff .
    else
        ruff check --diff .
    fi
    echo "::endgroup::"
    echo "::error:: ruff found issues"
else
    echo "::endgroup::"
fi

# Run mypy on all supported platforms
# MYPY is set if any of them fail.
MYPY=0
echo "::group::Mypy"
# Cleanup previous runs.
rm -f mypy_annotate.dat
# Pipefail makes these pipelines fail if mypy does, even if mypy_annotate.py succeeds.
set -o pipefail
mypy --show-error-end --platform linux | python ./tools/mypy_annotate.py --dumpfile mypy_annotate.dat --platform Linux \
    || { echo "* Mypy (Linux) found type errors." >> "$GITHUB_STEP_SUMMARY"; MYPY=1; }
# Darwin tests FreeBSD too
mypy --show-error-end --platform darwin | python ./tools/mypy_annotate.py --dumpfile mypy_annotate.dat --platform Mac \
    || { echo "* Mypy (Mac) found type errors." >> "$GITHUB_STEP_SUMMARY"; MYPY=1; }
mypy --show-error-end --platform win32 | python ./tools/mypy_annotate.py --dumpfile mypy_annotate.dat --platform Windows \
    || { echo "* Mypy (Windows) found type errors." >> "$GITHUB_STEP_SUMMARY"; MYPY=1; }
set +o pipefail
# Re-display errors using Github's syntax, read out of mypy_annotate.dat
python ./tools/mypy_annotate.py --dumpfile mypy_annotate.dat
# Then discard.
rm -f mypy_annotate.dat
echo "::endgroup::"
# Display a big error if we failed, outside the group so it can't be collapsed.
if [ $MYPY -ne 0 ]; then
    echo "::error:: Mypy found type errors."
    EXIT_STATUS=1
fi

# Check pip compile is consistent
echo "::group::Pip Compile - Tests"
uv lock
echo "::endgroup::"

if git status --porcelain | grep -q "uv.lock"; then
    echo "::error::uv.lock changed."
    echo "::group::uv.lock changed"
    echo "* uv.lock changed" >> "$GITHUB_STEP_SUMMARY"
    git status --porcelain
    git --no-pager diff --color ./*uv.lock
    EXIT_STATUS=1
    echo "::endgroup::"
fi

# Finally, leave a really clear warning of any issues and exit
if [ $EXIT_STATUS -ne 0 ]; then
    cat <<EOF
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

Problems were found by static analysis (listed above).
To fix formatting and see remaining errors, run

    uv sync --extra tools
    ruff check src
    mypy
    ./check.sh

in your local checkout.

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
EOF
    exit 1
fi
echo "# Formatting checks succeeded." >> "$GITHUB_STEP_SUMMARY"
exit 0
