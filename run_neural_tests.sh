#!/bin/bash

# Script to activate conda environment and run neural network tests
# for the AxiomEngine neural verification and dispute system

set -e  # Exit on any error

echo "=========================================="
echo "AxiomEngine Neural Network Test Suite"
echo "=========================================="

# Check if conda is available
if ! command -v conda &> /dev/null; then
    echo "Error: conda is not installed or not in PATH"
    exit 1
fi

# Activate the Axiom10 conda environment
echo "Activating conda environment 'Axiom10'..."
source $(conda info --base)/etc/profile.d/conda.sh
conda activate Axiom10

if [ $? -ne 0 ]; then
    echo "Error: Failed to activate conda environment 'Axiom10'"
    echo "Please make sure the environment exists:"
    echo "  conda create -n Axiom10 python=3.11"
    echo "  conda activate Axiom10"
    echo "  pip install -e ."
    exit 1
fi

echo "✓ Conda environment 'Axiom10' activated successfully"

# Check Python version
python_version=$(python --version 2>&1)
echo "Python version: $python_version"

# Install/upgrade required packages
echo "Installing/upgrading required packages..."
pip install --upgrade pip
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install transformers scikit-learn pandas matplotlib seaborn plotly
pip install sentence-transformers huggingface-hub accelerate

# Install the project in development mode
echo "Installing AxiomEngine in development mode..."
pip install -e .

# Create models directory if it doesn't exist
mkdir -p models/fact_verifier

# Run the neural network tests
echo "=========================================="
echo "Running Neural Network Tests..."
echo "=========================================="

python test_neural_dispute_system.py

if [ $? -eq 0 ]; then
    echo "=========================================="
    echo "✓ All tests completed successfully!"
    echo "=========================================="
    echo ""
    echo "Neural Network Features Implemented:"
    echo "  ✓ BERT-based fact verification model"
    echo "  ✓ Automatic feature extraction and analysis"
    echo "  ✓ Confidence scoring and threshold management"
    echo "  ✓ Training interface with performance tracking"
    echo "  ✓ Dispute system with voting mechanism"
    echo "  ✓ P2P network dispute broadcasting"
    echo "  ✓ Enhanced fact processor integration"
    echo "  ✓ Auto-dispute creation for low-confidence facts"
    echo ""
    echo "The system is now ready to:"
    echo "  - Verify facts using neural networks"
    echo "  - Learn and improve over time"
    echo "  - Handle disputes across the P2P network"
    echo "  - Remove false facts from the ledger"
    echo ""
else
    echo "=========================================="
    echo "✗ Tests failed!"
    echo "=========================================="
    exit 1
fi

# Optional: Show system information
echo "System Information:"
echo "  - Conda Environment: Axiom10"
echo "  - Working Directory: $(pwd)"
echo "  - Python Path: $(which python)"
echo "  - Models Directory: models/fact_verifier/"

# Keep environment active for further use
echo ""
echo "Conda environment 'Axiom10' remains active for further development."
echo "To deactivate, run: conda deactivate"
