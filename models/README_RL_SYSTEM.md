# LLM Ruff Fixer with Reinforcement Learning

## Overview

This enhanced version of the LLM Ruff Fixer includes a sophisticated reinforcement learning system that continuously improves the model's performance by learning from past fix attempts. The system rewards good fixes and penalizes bad ones, creating a feedback loop that makes the LLM progressively better at providing valid, clean code fixes.

## Key Features

### 🧠 Neural Network Learning
- **Reward Prediction Model**: A neural network that learns to predict the quality of potential fixes
- **Feature Extraction**: Converts fix attempts into numerical features for learning
- **Continuous Training**: Automatically retrains on new experiences

### 📊 Memory System
- **Experience Storage**: Remembers all fix attempts with outcomes
- **Performance Tracking**: Tracks success rates by error code
- **Learning Feedback**: Provides contextual guidance based on past performance

### 🎯 Reward/Penalty System
- **Success Rewards**: +10 points for valid fixes
- **Syntax Error Penalties**: -5 points for invalid Python code
- **Explanation Penalties**: -2 points for unwanted explanations
- **Deletion Penalties**: -8 points for excessive code removal
- **Efficiency Bonuses**: +1 point for concise fixes

### 🔄 Adaptive Prompts
- **Learning Feedback**: Prompts include guidance based on past performance
- **Error-Specific Guidance**: Different advice for docstring, naming, and import errors
- **Success Reinforcement**: Positive feedback for consistently good performance

## Installation

1. **Install Dependencies**:
   ```bash
   pip install -r requirements_rl.txt
   ```

2. **For Apple Silicon Macs** (optional performance boost):
   ```bash
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
   ```

## Usage

### Basic Usage
```bash
python llm_ruff_fixer.py
```
Processes all Python files in the current directory with learning enabled.

### View Learning Performance
```bash
python llm_ruff_fixer.py --report
```
Shows detailed performance metrics and learning progress.

### Train Model Manually
```bash
python llm_ruff_fixer.py --train
```
Forces training of the neural network on accumulated experiences.

### Test Mode (No LLM)
```bash
python llm_ruff_fixer.py --test
```
Runs in test mode to check for Ruff errors without using the LLM.

## How It Works

### 1. Experience Recording
Every fix attempt is recorded as a `FixExperience` with:
- Original code and error
- LLM response and fixed code
- Success/failure outcome
- Calculated reward/penalty
- Failure reason (if applicable)

### 2. Quality Verification
The system verifies fixes using multiple criteria:
- **Syntax Validation**: Ensures the fix produces valid Python code
- **Explanation Detection**: Checks for unwanted explanatory text
- **Code Preservation**: Ensures existing functionality isn't lost
- **Efficiency Assessment**: Rewards concise, clean fixes

### 3. Learning Feedback
The system generates contextual prompts based on past performance:
- **Success Reinforcement**: "Good job! You've successfully fixed D401 errors 85% of the time"
- **Failure Prevention**: "Remember: Don't make syntax_error mistakes like in previous attempts"
- **Error-Specific Guidance**: Different advice for docstring vs. naming errors

### 4. Neural Network Training
The reward prediction model learns from experiences:
- **Feature Extraction**: Converts experiences into numerical features
- **Batch Training**: Trains on batches of recent experiences
- **Model Persistence**: Saves trained models for future use

## Configuration

### RL Configuration (`RL_CONFIG`)
```python
RL_CONFIG = {
    "memory_file": "llm_learning_memory.pkl",  # Memory storage file
    "model_file": "llm_reward_model.pth",      # Neural network model file
    "learning_rate": 0.001,                    # Training learning rate
    "batch_size": 32,                          # Training batch size
    "memory_size": 10000,                      # Max experiences to remember
    "reward_success": 10.0,                    # Reward for successful fixes
    "penalty_syntax_error": -5.0,              # Penalty for syntax errors
    "penalty_explanation": -2.0,               # Penalty for explanations
    "penalty_deletion": -8.0,                  # Penalty for code deletion
    "bonus_efficiency": 1.0,                   # Bonus for efficient fixes
}
```

## Performance Metrics

The system tracks various performance indicators:

### Success Rates
- **Overall Success Rate**: Percentage of all fixes that pass verification
- **Error Code Success Rates**: Success rates for specific error types
- **Recent Success Rate**: Success rate of the last 100 attempts

### Learning Progress
- **Total Experiences**: Number of fix attempts recorded
- **Average Reward**: Mean reward across recent experiences
- **Training History**: When the model was last trained

### Error Code Performance
- **D401**: Docstring first line should be in imperative mood
- **N802**: Function name should be lowercase
- **F821**: Undefined name errors
- **D103**: Missing docstring in public function
- And many more...

## Example Output

```
--- LLM Bulk Ruff Fixer with Reinforcement Learning ---
Current Success Rate: 87.50%
Total Learning Experiences: 24

Found 2 Python file(s) to process: test_file.py, another_file.py

[*] Loading LLM model from: /path/to/model.gguf

--- Processing: test_file.py ---
[*] Found 3 errors to fix.

[*] Fixing Line 15: [D401] First line should be in imperative mood
    -> Special handling for docstring error (D401). Extracting full function.
    --- LLM's Suggested Fix ---
    def calculate_sum(a: int, b: int) -> int:
-        """Calculates the sum of two numbers."""
+        """Calculate the sum of two numbers."""
         return a + b
    ---------------------------
[+] LLM fix passed all checks. Reward: 11.00
    [*] ✅ Applying validated fix. Reward: 11.00

[*] Training reinforcement learning model...
[*] Model training completed. Average loss: 0.0234

--- Summary ---
Processed 2 file(s).
Modified 1 file(s):
  - test_file.py

--- Learning Progress ---
New experiences recorded: 3
Updated success rate: 88.89%
Average reward: 9.67

--- Done ---
```

## Benefits

### For Developers
- **Improved Fix Quality**: The LLM gets better at providing valid fixes over time
- **Reduced Manual Review**: Fewer syntax errors and unwanted explanations
- **Consistent Style**: Learning from successful patterns creates consistency

### For Teams
- **Knowledge Sharing**: The system learns from all team members' fixes
- **Quality Assurance**: Built-in verification prevents bad fixes from being applied
- **Performance Tracking**: Monitor and improve the system's effectiveness

### For Projects
- **Automated Code Quality**: Continuous improvement of automated fixes
- **Reduced Technical Debt**: Better fixes mean less manual cleanup
- **Scalable Learning**: The system improves with more usage

## Troubleshooting

### PyTorch Not Available
If PyTorch is not installed, the system will run with basic reinforcement learning (no neural network):
```
[!] PyTorch not available. Installing basic RL system without neural network.
```

### Memory Issues
If you encounter memory issues:
- Reduce `memory_size` in `RL_CONFIG`
- Reduce `batch_size` for training
- Use smaller models or fewer threads

### Model Training Failures
If training fails:
- Check that you have enough experiences (minimum 10)
- Verify PyTorch installation
- Check available memory

## Future Enhancements

### Planned Features
- **Multi-Model Support**: Learn from different LLM models
- **Advanced Features**: More sophisticated feature extraction
- **Online Learning**: Real-time model updates
- **Performance Analytics**: Detailed learning curves and metrics

### Research Opportunities
- **Transfer Learning**: Apply learning across different codebases
- **Meta-Learning**: Learn to learn new error types quickly
- **Ensemble Methods**: Combine multiple learning approaches

## Contributing

The reinforcement learning system is designed to be extensible. Key areas for contribution:

1. **Feature Engineering**: Improve the feature extraction process
2. **Reward Functions**: Design better reward/penalty schemes
3. **Model Architecture**: Experiment with different neural network designs
4. **Evaluation Metrics**: Develop better ways to measure learning progress

## License

This enhancement maintains the same license as the original LLM Ruff Fixer.
