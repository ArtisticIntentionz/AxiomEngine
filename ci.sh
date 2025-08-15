#!/bin/bash

set -ex -o pipefail

# Log some general info about the environment
echo "::group::Environment"
uname -a
env | sort
PROJECT='axiom_server'
ON_GITHUB_CI=true
echo "::endgroup::"

# If not running on Github's CI, discard the summaries
if [ -z "${GITHUB_STEP_SUMMARY+x}" ]; then
    GITHUB_STEP_SUMMARY=/dev/null
    ON_GITHUB_CI=false
fi

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
SPACY_VERSION=$(python -c 'import tomli; from pathlib import Path; print({p["name"]:p for p in tomli.loads(Path("uv.lock").read_text())["package"]}["spacy"]["version"])')
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

# Check if running on Linux and install spacy from binaries
if [[ "${RUNNER_OS:-}" == "Linux" ]]; then
    echo "::group::Installing dependencies for Linux"
    if $ON_GITHUB_CI; then
        sudo apt-get update -q
        sudo apt-get install -y -q libxml2-dev libxslt1-dev
    fi
    # Get the Ubuntu version
    UBUNTU_VERSION=$(lsb_release -rs)
    PYTHON_VERSION=$(python -c 'import sys; print("".join(map(str, sys.version_info[:2])))')
    # Install spacy from binaries
    uv add "spacy @ https://github.com/explosion/spaCy/releases/download/release-v${SPACY_VERSION}/spacy-${SPACY_VERSION}-cp${PYTHON_VERSION}-cp${PYTHON_VERSION}-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
    # Make sure installation was successful
    SPACY_RUN_VERSION=$(python -c "import importlib.metadata; print(importlib.metadata.version('spacy'))")
    if [[ "${SPACY_RUN_VERSION}" != "${SPACY_VERSION}" ]]; then
        echo "::error:: spacy linux installation failed, version does not match expected."
        exit 1
    fi
    echo "::endgroup::"
fi

if [ "$CHECK_FORMATTING" = "1" ]; then
    python -m uv sync --locked --extra tests --extra tools
    echo "::endgroup::"
    # Restore files to original state on Linux
    if [[ "${RUNNER_OS:-}" == "Linux" ]]; then
        git restore pyproject.toml uv.lock
    fi
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
        python -m uv sync --locked --extra tests
        flags=""
    fi
    # Restore files to original state on Linux
    if [[ "${RUNNER_OS:-}" == "Linux" ]]; then
        git restore pyproject.toml uv.lock
    fi

    echo "::endgroup::"

    echo "::group::Setup for tests"

    # We run the tests from inside an empty directory, to make sure Python
    # doesn't pick up any .py files from our working dir. Might have been
    # pre-created by some of the code above.
    mkdir empty || true
    cd empty

    python -m spacy download en_core_web_lg

    echo "::endgroup::"
    echo "::group:: Run Tests"
    if coverage run --rcfile=../pyproject.toml -m pytest -ra --junitxml=../test-results.xml ../tests --verbose --durations=10 $flags; then
        PASSED=true
    else
        PASSED=false
    fi
    echo "::endgroup::"
    echo "::group::Coverage"

    coverage combine --rcfile ../pyproject.toml
    coverage report -m --rcfile ../pyproject.toml
    coverage xml --rcfile ../pyproject.toml

    echo "::endgroup::"
    $PASSED
fi
