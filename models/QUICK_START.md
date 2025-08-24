# 🚀 Quick Start Guide - LLM Ruff Fixer with Reinforcement Learning

## Get Started in 3 Steps

### 1. Install Dependencies
```bash
# Install basic dependencies
pip install numpy

# Install PyTorch (optional, for neural network features)
pip install torch

# Install llama-cpp-python (optional, for LLM functionality)
pip install llama-cpp-python
```

### 2. Test the System
```bash
# Run the test suite
python3 test_rl_system.py

# Run the demonstration
python3 demo_rl_system.py
```

### 3. Use the System
```bash
# Process Python files with learning enabled
python3 llm_ruff_fixer.py

# View learning performance
python3 llm_ruff_fixer.py --report

# Train the model manually
python3 llm_ruff_fixer.py --train
```

## 🎯 What You'll See

### First Run
```
--- LLM Bulk Ruff Fixer with Reinforcement Learning ---
Current Success Rate: 0.00%
Total Learning Experiences: 0

Found 2 Python file(s) to process: file1.py, file2.py
```

### After Processing
```
--- Learning Progress ---
New experiences recorded: 5
Updated success rate: 80.00%
Average reward: 8.20
```

### Performance Report
```
--- LLM Learning Performance Report ---
Total Experiences: 15
Overall Success Rate: 86.67%
Recent Success Rate: 90.00%
Average Reward: 8.73

Error Code Performance:
  D401: 85.71%
  N802: 100.00%
  F821: 100.00%
```

## 🔧 Configuration

### Basic Configuration
The system works out of the box with default settings. For advanced users:

```python
# In llm_ruff_fixer.py, modify RL_CONFIG:
RL_CONFIG = {
    "memory_size": 10000,        # Max experiences to remember
    "reward_success": 10.0,      # Reward for successful fixes
    "penalty_syntax_error": -5.0, # Penalty for syntax errors
    # ... more options
}
```

### Model Configuration
```python
# LLM model settings
LLM_CONFIG = {
    "n_ctx": 16000,      # Context window size
    "n_threads": 6,      # CPU threads
    "n_batch": 1024,     # Batch size
}
```

## 📊 Understanding the Output

### Success Indicators
- ✅ **Valid fix**: +10 points
- ✅ **Efficient fix**: +1 bonus point
- ❌ **Syntax error**: -5 points
- ❌ **Unwanted explanation**: -2 points

### Learning Feedback
The system provides contextual guidance:
- "Good job! You've successfully fixed D401 errors 85% of the time"
- "Remember: Don't make syntax_error mistakes like in previous attempts"

### Performance Metrics
- **Success Rate**: Percentage of fixes that pass verification
- **Average Reward**: Mean reward across recent experiences
- **Error Code Performance**: Success rates for specific error types

## 🛠️ Troubleshooting

### Common Issues

**"PyTorch not available"**
- The system works without PyTorch (basic RL only)
- Install PyTorch for neural network features: `pip install torch`

**"llama-cpp-python not available"**
- The system works without LLM (testing mode only)
- Install for full functionality: `pip install llama-cpp-python`

**"ruff command not found"**
- Install Ruff: `pip install ruff`

### Performance Tips

**For Large Codebases**
- Process files in smaller batches
- Use `--test` mode to identify errors first
- Monitor memory usage with large models

**For Better Learning**
- Run regularly to accumulate experiences
- Use `--train` to force model training
- Monitor performance with `--report`

## 🎯 Next Steps

### Explore Advanced Features
1. **Custom Reward Functions**: Modify reward/penalty values
2. **Feature Engineering**: Enhance the learning features
3. **Model Architecture**: Experiment with different neural networks
4. **Performance Analytics**: Analyze learning curves and trends

### Integration
1. **CI/CD Pipeline**: Integrate into automated workflows
2. **Team Usage**: Share learning across team members
3. **Project-Specific**: Adapt to your codebase patterns

### Documentation
- **README_RL_SYSTEM.md**: Comprehensive documentation
- **IMPLEMENTATION_SUMMARY.md**: Technical details
- **test_rl_system.py**: Test suite and examples

## 🚀 Ready to Go!

The reinforcement learning system is now ready to help improve your code quality automatically. The more you use it, the better it gets!

**Happy coding! 🎉**
