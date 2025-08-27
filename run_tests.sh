#!/bin/bash

# Axiom Engine Test Runner
# This script runs all tests using pytest with proper configuration

echo "Running Axiom Engine Tests..."
echo "=============================="

# Activate conda environment
source ~/miniconda3/etc/profile.d/conda.sh
conda activate Axiom10

# Run all tests with verbose output
python -m pytest tests/ -v

echo ""
echo "Tests completed!"
