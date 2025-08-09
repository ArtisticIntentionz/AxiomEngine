#!/bin/bash

set -ex -o pipefail

# Log some general info about the environment
echo "::group::Environment"
uname -a
env | sort
PROJECT='axiom_server'
echo "::endgroup::"


################################################################
# We have a Python environment!
################################################################

echo "::group::Versions"
python -c "import sys, struct; print('python:', sys.version); print('version_info:', sys.version_info); print('bits:', struct.calcsize('P') * 8)"
echo "::endgroup::"

echo "::group::Install dependencies"
python -m pip install -U pip tomli
python -m pip --version
UV_VERSION=$(python -c 'import tomli; from pathlib import Path; print({p["name"]:p for p in tomli.loads(Path("uv.lock").read_text())["package"]}["uv"]["version"])')
python -m pip install uv==$UV_VERSION
python -m uv --version

UV_VENV_SEED="pip"
python -m uv venv --seed --allow-existing

# Determine the platform and activate the virtual environment accordingly
case "$OSTYPE" in
  linux-gnu*|linux-musl*|darwin*)
    source .venv/bin/activate
    ;;
  cygwin*|msys*)
    source .venv/Scripts/activate
    ;;
  *)
    echo "::error:: Unknown OS. Please add an activation method for '$OSTYPE'."
    exit 1
    ;;
esac

# Install uv in virtual environment
python -m pip install uv==$UV_VERSION

if [ "$CHECK_FORMATTING" = "1" ]; then
    python -m uv sync --locked --extra tests --extra tools
    echo "::endgroup::"
    source check.sh
else
    # Actual tests
    # expands to 0 != 1 if NO_TEST_REQUIREMENTS is not set, if set the `-0` has no effect
    # https://pubs.opengroup.org/onlinepubs/9699919799/utilities/V3_chap02.html#tag_18_06_02
    if [ "${NO_TEST_REQUIREMENTS-0}" == 1 ]; then
        python -m uv sync --locked --extra tests
        flags=""
        #"--skip-optional-imports"
    else
        python -m uv sync --locked --extra tests --extra tools
        flags=""
    fi

    echo "::endgroup::"

    echo "::group::Setup for tests"

    # We run the tests from inside an empty directory, to make sure Python
    # doesn't pick up any .py files from our working dir. Might have been
    # pre-created by some of the code above.
    mkdir empty || true
    cd empty

    python -m spacy download en_core_web_sm

    INSTALLDIR=$(python -c "import os, $PROJECT; print(os.path.dirname($PROJECT.__file__))")
    cp ../pyproject.toml "$INSTALLDIR"

    echo "::endgroup::"
    echo "::group:: Run Tests"
    if coverage run --rcfile=../pyproject.toml -m pytest -ra --junitxml=../test-results.xml ../tests --verbose --durations=10 $flags; then
        PASSED=true
    else
        PASSED=false
    fi
    PREV_DIR="$PWD"
    cd "$INSTALLDIR"
    rm pyproject.toml
    cd "$PREV_DIR"
    echo "::endgroup::"
    echo "::group::Coverage"

    coverage combine --rcfile ../pyproject.toml
    coverage report -m --rcfile ../pyproject.toml
    coverage xml --rcfile ../pyproject.toml

    echo "::endgroup::"
    $PASSED
fi
