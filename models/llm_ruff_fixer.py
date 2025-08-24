# bulk_ruff_fixer.py
import ast
import glob
import os
import re
import subprocess
import tempfile
import json
import pickle
import hashlib
from datetime import datetime
from difflib import unified_diff
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass, asdict
from pathlib import Path

try:
    import numpy as np
except ImportError:
    print("[!] NumPy not available. Using basic array operations.")
    np = None

try:
    from llama_cpp import Llama
    LLAMA_AVAILABLE = True
except ImportError:
    print("[!] llama-cpp-python not available. LLM functionality will be disabled.")
    LLAMA_AVAILABLE = False
    # Create a dummy Llama class for testing
    class Llama:
        def __init__(self, *args, **kwargs):
            pass
        def __call__(self, *args, **kwargs):
            return {"choices": [{"text": "Test response"}]}

# --- REINFORCEMENT LEARNING IMPORTS ---
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import Dataset, DataLoader
    RL_AVAILABLE = True
except ImportError:
    print("[!] PyTorch not available. Installing basic RL system without neural network.")
    RL_AVAILABLE = False

# --- CONFIGURATION ---
PROJECT_ROOT_PATH = "/Users/vic/AxiomEngine"
# --- NEW, BETTER MODEL (Recommended) ---
LLM_MODEL_PATH = (
    "/Users/vic/AxiomEngine/models/codellama-13b-instruct.Q4_K_M.gguf"
)

# if you choose Mistral:
# LLM_MODEL_PATH = "/Users/vic/AxiomEngine/models/mistral-7b-instruct-v0.2.Q4_K_M.gguf"

# Number of lines of code before and after an error to provide to the LLM for context.
CONTEXT_LINES = 30

# Intel Mac LLM Configuration for CodeLlama 13B Instruct
# Optimized settings for Intel Mac compatibility with larger model
LLM_CONFIG = {
    "n_ctx": 16000,  # Larger context window for 13B model
    "n_threads": 6,  # More CPU threads for larger model
    "n_batch": 1024,  # Larger batch size for better performance
    "use_mmap": True,  # Memory mapping for better performance
    "use_mlock": False,  # Disable mlock on macOS
    "verbose": True,  # Enable verbose to see loading details
}

# --- REINFORCEMENT LEARNING CONFIGURATION ---
RL_CONFIG = {
    "memory_file": "llm_learning_memory.pkl",
    "model_file": "llm_reward_model.pth",
    "learning_rate": 0.001,
    "batch_size": 32,
    "memory_size": 10000,  # Maximum number of experiences to remember
    "reward_success": 10.0,  # Reward for successful fixes
    "penalty_syntax_error": -5.0,  # Penalty for syntax errors
    "penalty_explanation": -2.0,  # Penalty for unwanted explanations
    "penalty_deletion": -8.0,  # Penalty for deleting existing code
    "bonus_efficiency": 1.0,  # Bonus for efficient fixes
}

# --- INSTRUCTIONS ---
# 1. Place this script in the directory with the Python files you want to fix.
# 2. Run the script from your terminal: `python bulk_ruff_fixer.py`
# 3. The script will find all `.py` files (except itself), check them with Ruff,
#    and use the LLM to fix any found errors.
#
# !! IMPORTANT !!
# This script OVERWRITES files. Ensure your code is under version control (like Git)
# so you can review and revert any changes if needed.
# --- END CONFIGURATION & INSTRUCTIONS ---


# --- REINFORCEMENT LEARNING DATA STRUCTURES ---
@dataclass
class FixExperience:
    """Represents a single fix attempt with its outcome."""
    timestamp: str
    error_code: str
    error_message: str
    original_code: str
    llm_response: str
    fixed_code: str
    success: bool
    reward: float
    failure_reason: Optional[str] = None
    code_hash: Optional[str] = None
    
    def __post_init__(self):
        if self.code_hash is None:
            self.code_hash = hashlib.md5(
                (self.original_code + self.error_code).encode()
            ).hexdigest()


@dataclass
class LearningMemory:
    """Stores the learning memory and provides methods to manage it."""
    experiences: List[FixExperience]
    model_performance: Dict[str, float]
    last_training: Optional[str] = None
    
    def add_experience(self, experience: FixExperience) -> None:
        """Add a new experience to memory."""
        self.experiences.append(experience)
        # Keep only the most recent experiences
        if len(self.experiences) > RL_CONFIG["memory_size"]:
            self.experiences = self.experiences[-RL_CONFIG["memory_size"]:]
    
    def get_recent_experiences(self, count: int = 100) -> List[FixExperience]:
        """Get the most recent experiences."""
        return self.experiences[-count:]
    
    def get_experiences_by_error_code(self, error_code: str) -> List[FixExperience]:
        """Get all experiences for a specific error code."""
        return [exp for exp in self.experiences if exp.error_code == error_code]
    
    def get_success_rate(self, error_code: Optional[str] = None) -> float:
        """Calculate success rate for all experiences or a specific error code."""
        if error_code:
            experiences = self.get_experiences_by_error_code(error_code)
        else:
            experiences = self.experiences
        
        if not experiences:
            return 0.0
        
        successful = sum(1 for exp in experiences if exp.success)
        return successful / len(experiences)


# --- NEURAL NETWORK FOR REWARD PREDICTION ---
if RL_AVAILABLE:
    class RewardPredictor(nn.Module):
        """Neural network to predict the reward for a given fix attempt."""
        
        def __init__(self, input_size: int = 512, hidden_size: int = 256):
            super(RewardPredictor, self).__init__()
            self.encoder = nn.Sequential(
                nn.Linear(input_size, hidden_size),
                nn.ReLU(),
                nn.Dropout(0.2),
                nn.Linear(hidden_size, hidden_size // 2),
                nn.ReLU(),
                nn.Dropout(0.2),
            )
            self.predictor = nn.Sequential(
                nn.Linear(hidden_size // 2, hidden_size // 4),
                nn.ReLU(),
                nn.Linear(hidden_size // 4, 1),
                nn.Tanh()  # Output between -1 and 1
            )
        
        def forward(self, x):
            encoded = self.encoder(x)
            return self.predictor(encoded)
    
    class FixDataset(Dataset):
        """Dataset for training the reward predictor."""
        
        def __init__(self, experiences: List[FixExperience]):
            self.experiences = experiences
        
        def __len__(self):
            return len(self.experiences)
        
        def __getitem__(self, idx):
            exp = self.experiences[idx]
            # Create feature vector from experience
            features = self._extract_features(exp)
            return torch.FloatTensor(features), torch.FloatTensor([exp.reward])
        
        def _extract_features(self, exp: FixExperience) -> List[float]:
            """Extract numerical features from an experience."""
            features = []
            
            # Error code features (one-hot encoding for common codes)
            common_codes = ['D401', 'D205', 'D400', 'N802', 'F821', 'D103', 'D107', 'D200', 'D404']
            for code in common_codes:
                features.append(1.0 if exp.error_code.startswith(code) else 0.0)
            
            # Code length features
            features.append(len(exp.original_code) / 1000.0)  # Normalized length
            features.append(len(exp.fixed_code) / 1000.0)
            
            # Response length features
            features.append(len(exp.llm_response) / 1000.0)
            
            # Success indicator
            features.append(1.0 if exp.success else 0.0)
            
            # Time-based features
            timestamp = datetime.fromisoformat(exp.timestamp)
            features.append(timestamp.hour / 24.0)  # Hour of day
            features.append(timestamp.weekday() / 7.0)  # Day of week
            
            # Pad or truncate to fixed size
            target_size = 512
            if len(features) < target_size:
                features.extend([0.0] * (target_size - len(features)))
            else:
                features = features[:target_size]
            
            return features
        
        @staticmethod
        def extract_features(exp: FixExperience) -> List[float]:
            """Static method to extract features from an experience."""
            features = []
            
            # Error code features (one-hot encoding for common codes)
            common_codes = ['D401', 'D205', 'D400', 'N802', 'F821', 'D103', 'D107', 'D200', 'D404']
            for code in common_codes:
                features.append(1.0 if exp.error_code.startswith(code) else 0.0)
            
            # Code length features
            features.append(len(exp.original_code) / 1000.0)  # Normalized length
            features.append(len(exp.fixed_code) / 1000.0)
            
            # Response length features
            features.append(len(exp.llm_response) / 1000.0)
            
            # Success indicator
            features.append(1.0 if exp.success else 0.0)
            
            # Time-based features
            timestamp = datetime.fromisoformat(exp.timestamp)
            features.append(timestamp.hour / 24.0)  # Hour of day
            features.append(timestamp.weekday() / 7.0)  # Day of week
            
            # Pad or truncate to fixed size
            target_size = 512
            if len(features) < target_size:
                features.extend([0.0] * (target_size - len(features)))
            else:
                features = features[:target_size]
            
            return features


# --- REINFORCEMENT LEARNING MANAGER ---
class RLManager:
    """Manages the reinforcement learning system."""
    
    def __init__(self):
        self.memory = self._load_memory()
        self.reward_model = None
        if RL_AVAILABLE:
            self.reward_model = RewardPredictor()
            self._load_model()
    
    def _load_memory(self) -> LearningMemory:
        """Load learning memory from file."""
        memory_path = Path(RL_CONFIG["memory_file"])
        if memory_path.exists():
            try:
                with open(memory_path, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                print(f"[!] Failed to load memory: {e}")
        
        return LearningMemory(experiences=[], model_performance={})
    
    def _save_memory(self) -> None:
        """Save learning memory to file."""
        try:
            with open(RL_CONFIG["memory_file"], 'wb') as f:
                pickle.dump(self.memory, f)
        except Exception as e:
                print(f"[!] Failed to save memory: {e}")
    
    def _load_model(self) -> None:
        """Load the trained reward model."""
        model_path = Path(RL_CONFIG["model_file"])
        if model_path.exists():
            try:
                self.reward_model.load_state_dict(torch.load(model_path))
                self.reward_model.eval()
            except Exception as e:
                print(f"[!] Failed to load reward model: {e}")
    
    def _save_model(self) -> None:
        """Save the trained reward model."""
        if self.reward_model:
            try:
                torch.save(self.reward_model.state_dict(), RL_CONFIG["model_file"])
            except Exception as e:
                print(f"[!] Failed to save reward model: {e}")
    
    def record_experience(self, experience: FixExperience) -> None:
        """Record a new fix experience."""
        self.memory.add_experience(experience)
        self._save_memory()
        
        # Update performance metrics
        error_code = experience.error_code
        if error_code not in self.memory.model_performance:
            self.memory.model_performance[error_code] = 0.0
        
        # Update success rate for this error code
        success_rate = self.memory.get_success_rate(error_code)
        self.memory.model_performance[error_code] = success_rate
    
    def get_learning_prompt(self, error_code: str, error_message: str) -> str:
        """Generate a learning-enhanced prompt based on past experiences."""
        # Get recent experiences for this error code
        recent_experiences = self.memory.get_experiences_by_error_code(error_code)
        
        if not recent_experiences:
            return ""
        
        # Find successful examples
        successful_examples = [exp for exp in recent_experiences if exp.success]
        failed_examples = [exp for exp in recent_experiences if not exp.success]
        
        learning_notes = []
        
        if successful_examples:
            # Add positive reinforcement
            success_rate = len(successful_examples) / len(recent_experiences)
            learning_notes.append(
                f"Good job! You've successfully fixed {error_code} errors {success_rate:.1%} of the time. "
                f"Keep providing clean, syntax-correct fixes without explanations."
            )
        
        if failed_examples:
            # Add negative reinforcement
            common_failures = {}
            for exp in failed_examples:
                reason = exp.failure_reason or "unknown"
                common_failures[reason] = common_failures.get(reason, 0) + 1
            
            if common_failures:
                most_common_failure = max(common_failures.items(), key=lambda x: x[1])
                learning_notes.append(
                    f"Remember: Don't make {most_common_failure[0]} mistakes like in previous attempts. "
                    f"Focus on clean, valid Python code only."
                )
        
        # Add specific guidance based on error code
        if error_code.startswith("D"):
            learning_notes.append("For docstring errors, focus on the specific formatting requirements.")
        elif error_code.startswith("N"):
            learning_notes.append("For naming errors, ensure proper snake_case formatting.")
        elif error_code.startswith("F"):
            learning_notes.append("For import/undefined errors, add the correct import statements.")
        
        return " ".join(learning_notes)
    
    def train_model(self) -> None:
        """Train the reward prediction model on recent experiences."""
        if not RL_AVAILABLE or not self.reward_model:
            return
        
        recent_experiences = self.memory.get_recent_experiences(1000)
        if len(recent_experiences) < 10:
            print("[*] Not enough experiences to train the model.")
            return
        
        try:
            dataset = FixDataset(recent_experiences)
            dataloader = DataLoader(dataset, batch_size=RL_CONFIG["batch_size"], shuffle=True)
            
            optimizer = optim.Adam(self.reward_model.parameters(), lr=RL_CONFIG["learning_rate"])
            criterion = nn.MSELoss()
            
            self.reward_model.train()
            total_loss = 0.0
            
            for batch_features, batch_rewards in dataloader:
                optimizer.zero_grad()
                predictions = self.reward_model(batch_features)
                loss = criterion(predictions, batch_rewards)
                loss.backward()
                optimizer.step()
                total_loss += loss.item()
            
            avg_loss = total_loss / len(dataloader)
            print(f"[*] Model training completed. Average loss: {avg_loss:.4f}")
            
            self.memory.last_training = datetime.now().isoformat()
            self._save_model()
            self._save_memory()
            
        except Exception as e:
            print(f"[!] Model training failed: {e}")
    
    def predict_reward(self, experience: FixExperience) -> float:
        """Predict the reward for a potential fix attempt."""
        if not RL_AVAILABLE or not self.reward_model:
            return 0.0
        
        try:
            self.reward_model.eval()
            with torch.no_grad():
                features = torch.FloatTensor(FixDataset.extract_features(experience))
                prediction = self.reward_model(features.unsqueeze(0))
                return prediction.item()
        except Exception as e:
            print(f"[!] Reward prediction failed: {e}")
            return 0.0
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get a summary of the model's performance."""
        summary = {
            "total_experiences": len(self.memory.experiences),
            "overall_success_rate": self.memory.get_success_rate(),
            "error_code_performance": self.memory.model_performance,
            "last_training": self.memory.last_training,
        }
        
        if self.memory.experiences:
            recent_experiences = self.memory.get_recent_experiences(100)
            summary["recent_success_rate"] = self.memory.get_success_rate()
            summary["average_reward"] = sum(exp.reward for exp in recent_experiences) / len(recent_experiences)
        
        return summary


# --- GLOBAL RL MANAGER INSTANCE ---
rl_manager = RLManager()


# --- ENHANCED VERIFICATION FUNCTIONS ---
def verify_fix_quality(original_code: str, fixed_code: str, llm_response: str) -> Tuple[bool, float, Optional[str]]:
    """Verify the quality of a fix and calculate reward."""
    reward = 0.0
    failure_reason = None
    
    # Check for syntax errors
    try:
        ast.parse(fixed_code)
        reward += RL_CONFIG["reward_success"]
    except SyntaxError as e:
        failure_reason = f"syntax_error: {str(e)}"
        reward += RL_CONFIG["penalty_syntax_error"]
        return False, reward, failure_reason
    
    # Check for unwanted explanations in the response
    unwanted_patterns = [
        r"I've made the following changes",
        r"Here's the corrected code",
        r"The fix involves",
        r"Explanation:",
        r"Note:",
        r"IMPORTANT:",
        r"Remember:",
    ]
    
    for pattern in unwanted_patterns:
        if re.search(pattern, llm_response, re.IGNORECASE):
            failure_reason = "unwanted_explanation"
            reward += RL_CONFIG["penalty_explanation"]
            break
    
    # Check for code deletion (ensure we're not losing functionality)
    original_lines = original_code.split('\n')
    fixed_lines = fixed_code.split('\n')
    
    # Simple heuristic: if we lost more than 20% of the original code, it might be bad
    if len(fixed_lines) < len(original_lines) * 0.8:
        failure_reason = "excessive_deletion"
        reward += RL_CONFIG["penalty_deletion"]
    
    # Bonus for efficient fixes (shorter response, same functionality)
    if len(fixed_code) < len(original_code) * 1.1:  # Not much longer
        reward += RL_CONFIG["bonus_efficiency"]
    
    success = failure_reason is None
    return success, reward, failure_reason


def create_enhanced_llm_prompt(error: dict, code_snippet: str) -> str:
    """Creates an enhanced prompt with learning feedback."""
    base_prompt = create_llm_prompt(error, code_snippet)
    
    # Add learning feedback
    learning_feedback = rl_manager.get_learning_prompt(error["error_code"], error["message"])
    
    if learning_feedback:
        # Insert learning feedback into the system prompt
        enhanced_prompt = base_prompt.replace(
            "You are CodeLlama, an expert Python developer and code refactoring assistant. Your task is to fix Python code based on Ruff linting errors.",
            f"You are CodeLlama, an expert Python developer and code refactoring assistant. Your task is to fix Python code based on Ruff linting errors.\n\nLEARNING FEEDBACK: {learning_feedback}"
        )
        return enhanced_prompt
    
    return base_prompt


def run_ruff(file_path: str, select_codes: list = None) -> str:
    """Runs ruff on the specified file."""
    if not os.path.exists(file_path):
        return ""

    command = [
        "ruff",
        "check",
        file_path,
        "--no-cache",
        "--output-format=concise",
    ]

    result = subprocess.run(command, capture_output=True, text=True)

    # Ruff returns 0 for success, 1 for errors found
    if result.returncode == 0:
        return ""
    if result.returncode == 1:
        return result.stdout
    return result.stderr or result.stdout


def check_for_syntax_errors(file_path: str) -> bool:
    """Runs a pre-check for fatal syntax errors."""
    # Try to parse the file with Python to check for syntax errors
    try:
        with open(file_path) as f:
            compile(f.read(), file_path, "exec")
        return False
    except SyntaxError as e:
        print(f"[!] Critical syntax error in {file_path}: {e}")
        return True
    except Exception as e:
        print(f"[!] Error reading {file_path}: {e}")
        return True


def parse_ruff_output(output: str) -> list[dict]:
    """Parses the text output from Ruff to extract error details."""
    if not output.strip():
        return []

    # Handle the concise format: file:line:col: code message
    # Example: test_file_with_errors.py:4:8: F401 `os` imported but unused
    # Example: test_file_with_errors.py:4:5: N802 Function name `testFunction` should be lowercase
    pattern = re.compile(
        r"^(.*?):(\d+):(\d+):\s([A-Z]+\d+)\s(.*)$",
        re.MULTILINE,
    )

    errors = []
    for match in pattern.finditer(output):
        try:
            errors.append(
                {
                    "file_path": match.group(1),
                    "line_number": int(match.group(2)),
                    "column": int(match.group(3)),
                    "error_code": match.group(4),
                    "message": match.group(5).strip(),
                },
            )
        except (ValueError, IndexError):
            continue

    errors.sort(key=lambda x: x["line_number"], reverse=True)
    return errors


def extract_code_snippet(
    lines: list[str],
    error_line_num: int,
    context: int,
) -> tuple[str, int, int]:
    """Extracts a snippet of code around the error line for context."""
    error_line_index = error_line_num - 1
    start_index = max(0, error_line_index - context)
    end_index = min(len(lines), error_line_index + context + 1)
    snippet_lines = lines[start_index:end_index]
    return "".join(snippet_lines), start_index, end_index


def extract_full_function_source(
    file_path: str,
    function_line: int,
) -> Tuple[Optional[str], int, int]:
    """Extracts the full source code of a function definition from a file
    using its starting line number.

    Returns a tuple of (source_code, start_line_index, end_line_index) or (None, 0, 0).
    """
    try:
        with open(file_path, encoding="utf-8") as f:
            source_code = f.read()

        tree = ast.parse(source_code)

        for node in ast.walk(tree):
            # We check for FunctionDef and AsyncFunctionDef
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Check if the error line is within this function
                if node.lineno <= function_line <= node.end_lineno:
                    # Found the function!
                    start_index = node.lineno - 1
                    end_index = node.end_lineno

                    source_lines = source_code.splitlines(
                        True,
                    )  # Keep newlines
                    function_snippet = "".join(
                        source_lines[start_index:end_index],
                    )

                    return function_snippet, start_index, end_index
    except (SyntaxError, FileNotFoundError, Exception) as e:
        print(f"[!] AST parsing failed for {file_path}: {e}")

    return None, 0, 0


def create_llm_prompt(error: dict, code_snippet: str) -> str:
    """Creates a highly specific, context-aware prompt with guidance for the LLM."""
    special_instructions = "Follow the general instructions to fix the error."
    error_code = error["error_code"]

    if error_code.startswith("D401"):
        # Extract the problematic text from the error message
        try:
            problematic_text = error["message"].split('"')[1]
            special_instructions = f"""The first line of the docstring should be in imperative mood. 
The current docstring starts with "{problematic_text}" which should be changed to imperative mood.
Examples: "Main function to run..." → "Run...", "Queries the node..." → "Query the node...", "Calculates the sum..." → "Calculate the sum..."
IMPORTANT: You MUST change the actual docstring text, not just reformat it."""
        except (IndexError, KeyError):
            special_instructions = "Rewrite the first line of the docstring to be in the imperative mood. For example, change 'Generates a...' to 'Generate a...', 'Queries...' to 'Query...'."
    elif error_code.startswith("D205"):
        special_instructions = "Insert a single blank line between the summary line and the description/args section of the docstring."
    elif error_code.startswith("D400") or error_code.startswith("D415"):
        special_instructions = (
            "Add a period (.) to the end of the first line of the docstring."
        )
    elif error_code.startswith("N802"):
        special_instructions = "Rename the function to use snake_case. For example, 'checkForContradiction' should become 'check_for_contradiction'."
    elif error_code.startswith("F821"):
        try:
            undefined_name = error["message"].split("'")[1]
            special_instructions = f"The name `{undefined_name}` is undefined. This likely requires an import. Add the correct import statement (e.g., `from spacy.tokens import Doc`, `from sqlalchemy.orm import Session`) at the beginning of the snippet. If it's a missing type hint, you might also need `from __future__ import annotations`."
        except (IndexError, KeyError):
            special_instructions = "An undefined name was found. This likely requires an import. Add the correct import statement at the beginning of the snippet."
    elif error_code.startswith("D103"):
        special_instructions = """The public function below is missing a docstring. Your task is to write one.
1. Analyze the function's name, arguments, type hints, and code to understand its purpose.
2. Write a concise, one-line summary in the imperative mood (e.g., "Calculate the average..." not "Calculates the...").
3. If the function has arguments, a return value, or raises exceptions, add 'Args:', 'Returns:', and 'Raises:' sections as appropriate.
4. Place the complete docstring (using triple quotes) immediately after the function definition line.
5. Your response MUST be the entire, complete function with the new docstring included.
IMPORTANT: Do not add any markdown formatting, explanatory text, or closing tags. Return ONLY the corrected function."""
    elif error_code.startswith("D107"):
        special_instructions = """The __init__ method is missing a docstring. Your task is to write one.

CRITICAL REQUIREMENTS:
1. You MUST return the COMPLETE __init__ method including:
   - The method definition line (def __init__(self, ...):)
   - The docstring you add (with triple quotes)
   - ALL the existing method body code (self.text = text, etc.)
2. Do NOT return just the docstring - return the entire method
3. Keep all existing indentation and code structure
4. Add the docstring right after the method definition line

Example of what you should return:
```python
def __init__(self, text: str, similarity_map: dict[str, float] | None = None):
    \"\"\"Initialize the text similarity object.
    
    Args:
        text: The text to compare against
        similarity_map: Optional map of similarities
    \"\"\"
    self.text = text
    self.similarity_map = similarity_map or {}
```

IMPORTANT: Return ONLY the corrected method, no explanations."""
    elif error_code.startswith("D200"):
        special_instructions = """The docstring spans multiple lines but should fit on one line. 
1. Rewrite the docstring to be a single line that fits within reasonable length (typically under 80-100 characters).
2. Keep the meaning clear and concise.
3. Use triple quotes on the same line as the content.
4. Your response MUST be the entire, complete function with the corrected docstring.
IMPORTANT: Do not add any markdown formatting, explanatory text, or closing tags. Return ONLY the corrected function."""
    elif error_code.startswith("D404"):
        special_instructions = """The docstring starts with "This" which is not allowed. 
1. Rewrite the docstring to start with a different word (e.g., "The", "A", "An", or a verb).
2. Keep the meaning clear and maintain the same information.
3. Your response MUST be the entire, complete function with the corrected docstring.
IMPORTANT: Do not add any markdown formatting, explanatory text, or closing tags. Return ONLY the corrected function."""

    elif error_code.startswith("FA102"):
        special_instructions = "The file is using modern type hints without the required future import. Add `from __future__ import annotations` as the very first line of code in the snippet."
    elif error_code == "B001":
        special_instructions = "Do not use a blind `except: Exception`. Replace it with a more specific exception type like `ValueError`, `IOError`, or `requests.RequestException` based on the code in the `try` block. If multiple different errors are possible, catch them in separate `except` blocks."
    elif error_code == "SIM117":
        special_instructions = "Combine multiple `with` statements into a single one, separating the context managers with a comma. For example, `with open(...) as f: with another(...) as g:` should become `with open(...) as f, another(...) as g:`."
    elif error_code == "UP032":  # From 'UP' (pyupgrade)
        special_instructions = "This is a Python 3.9+ project. Rewrite the f-string using the modern `:=` operator if it simplifies the code, otherwise use a standard f-string format."
    elif error_code == "FURB109":  # From 'FURB' (refurb)
        special_instructions = "Refactor the code to use `pathlib.Path.read_text()` instead of `with open(...)` for reading the entire file content into a string."
    elif error_code == "RET504":
        special_instructions = "Remove the unnecessary assignment to the variable before the return statement. Return the value directly instead of assigning it to a variable first."
    elif error_code == "UP035":
        special_instructions = "Replace deprecated typing imports with built-in types. Change `typing.Dict` to `dict`, `typing.List` to `list`, `typing.Set` to `set`, etc. Only modify the import statements, not the usage."
    elif error_code == "D100":
        special_instructions = "Add a module-level docstring at the very beginning of the file. The docstring should briefly describe what this module does."
    elif error_code == "S110":
        special_instructions = "Replace the bare `except:` with a more specific exception type or add logging. Instead of `except: pass`, use `except Exception as e: logger.warning(f'Error: {e}')` or catch a specific exception type."
    elif error_code.startswith("UP"):
        special_instructions = "Update the code to use modern Python syntax. For UP006, replace `List` with `list`, `Dict` with `dict`, etc. For other UP errors, follow the pyupgrade recommendations. DO NOT add any import statements - only change the type annotations."

    return f"""<|system|>
You are CodeLlama, an expert Python developer and code refactoring assistant. Your task is to fix Python code based on Ruff linting errors.
</s>

<|user|>
Fix this Python code to resolve the {error_code} error: "{error["message"]}"

{special_instructions}

```python
{code_snippet}
```

Return ONLY the corrected code, maintaining exact indentation and structure.
</s>

<|assistant|>
```python"""


def get_llm_fix(llm: Llama, prompt: str) -> str:
    """Sends the prompt to the LLM and extracts the fixed code snippet."""
    response = llm(prompt, max_tokens=2048, echo=False)
    text = response["choices"][0]["text"]

    # Try to extract code from markdown blocks first
    match = re.search(r"```python\n(.*?)\n```", text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # For CodeLlama, try to extract after the assistant tag
    if "<|assistant|>" in text:
        assistant_part = text.split("<|assistant|>")[-1]
        # Remove any remaining tags
        assistant_part = re.sub(r"<\|.*?\|>", "", assistant_part)
        # Try to extract code block
        code_match = re.search(
            r"```python\n(.*?)(?:\n```|$)",
            assistant_part,
            re.DOTALL,
        )
        if code_match:
            return code_match.group(1).strip()
        # If no code block, return the cleaned assistant response
        return assistant_part.strip()

    # If no markdown block, try to extract after the prompt
    lines = text.split("\n")
    code_lines = []
    in_code = False

    for line in lines:
        if "Original code:" in line:
            in_code = True
            continue
        if in_code and line.strip():
            if line.startswith("```"):
                break
            if line.startswith("IMPORTANT:"):
                break
            code_lines.append(line)

    if code_lines:
        return "\n".join(code_lines).strip()

    # Fallback: return the entire response, but clean it up
    cleaned_text = text.strip()
    # Remove any markdown formatting
    cleaned_text = re.sub(r"```.*?```", "", cleaned_text, flags=re.DOTALL)
    cleaned_text = re.sub(r"^```python\s*", "", cleaned_text)
    cleaned_text = re.sub(r"\s*```$", "", cleaned_text)
    # Remove any remaining tags
    cleaned_text = re.sub(r"<\|.*?\|>", "", cleaned_text)
    # Remove any trailing markdown closing tags that might cause syntax errors
    cleaned_text = re.sub(r"\s*</s>\s*$", "", cleaned_text)
    cleaned_text = re.sub(r"\s*```\s*$", "", cleaned_text)
    # Remove any trailing backticks or markdown artifacts
    cleaned_text = re.sub(r"```\s*$", "", cleaned_text)
    cleaned_text = re.sub(
        r"</assistant>.*$",
        "",
        cleaned_text,
        flags=re.DOTALL,
    )
    # Remove any explanatory text after the code
    lines = cleaned_text.split("\n")
    code_lines = []
    for line in lines:
        if (
            line.strip()
            and not line.strip().startswith("I've made")
            and not line.strip().startswith("Please ensure")
        ):
            code_lines.append(line)
    return "\n".join(code_lines).strip()


def process_file(file_path: str, llm: Llama) -> bool:
    """Runs the full ruff->llm->fix process on a single file with reinforcement learning."""
    print(f"\n--- Processing: {file_path} ---")

    if check_for_syntax_errors(file_path):
        return False

    ruff_output = run_ruff(file_path)
    if not ruff_output.strip():
        print("[+] No ruff errors found. Skipping.")
        return False

    errors = parse_ruff_output(ruff_output)
    if not errors:
        print("[+] Ruff ran, but no parsable errors were found.")
        return False

    print(f"[*] Found {len(errors)} errors to fix.")

    with open(file_path) as f:
        file_lines = f.readlines()

    original_file_content = "".join(file_lines)
    temp_file_lines = list(file_lines)

    for error in errors:
        line_num = error["line_number"]
        print(
            f"\n[*] Fixing Line {line_num}: [{error['error_code']}] {error['message']}",
        )

        # --- NEW LOGIC TO CHOOSE THE RIGHT CONTEXT EXTRACTOR ---
        if error["error_code"].startswith("D"):  # All docstring-related errors
            # D100, D200, D404 are module-level, others are function-level
            if error["error_code"] in ["D100", "D200", "D404"]:
                print(
                    f"    -> Special handling for module-level docstring error ({error['error_code']}). Extracting file header.",
                )
                original_snippet, start_idx, end_idx = extract_code_snippet(
                    temp_file_lines,
                    line_num,
                    10,
                )
            else:
                print(
                    f"    -> Special handling for docstring error ({error['error_code']}). Extracting full function.",
                )
                original_snippet, start_idx, end_idx = (
                    extract_full_function_source(file_path, line_num)
                )
            if not original_snippet:
                print(
                    f"    [!] Could not extract code for {error['error_code']} at line {line_num}. Skipping.",
                )
                continue
        elif error["error_code"] in ["RET504", "RET505", "RET506"]:
            print(
                f"    -> Special handling for return optimization ({error['error_code']}). Extracting full function.",
            )
            original_snippet, start_idx, end_idx = (
                extract_full_function_source(file_path, line_num)
            )
            if not original_snippet:
                print(
                    f"    [!] Could not extract function body for {error['error_code']} at line {line_num}. Skipping.",
                )
                continue
        elif error["error_code"].startswith("UP"):
            # UP035 errors are import-level, not function-level
            if error["error_code"] == "UP035":
                print(
                    f"    -> Special handling for import-level pyupgrade error ({error['error_code']}). Extracting import section.",
                )
                original_snippet, start_idx, end_idx = extract_code_snippet(
                    temp_file_lines,
                    line_num,
                    10,
                )
            else:
                print(
                    f"    -> Special handling for pyupgrade error ({error['error_code']}). Extracting full function.",
                )
                original_snippet, start_idx, end_idx = (
                    extract_full_function_source(file_path, line_num)
                )
            if not original_snippet:
                print(
                    f"    [!] Could not extract code for {error['error_code']} at line {line_num}. Skipping.",
                )
                continue
        else:
            # Fallback to the original method for all other errors
            original_snippet, start_idx, end_idx = extract_code_snippet(
                temp_file_lines,
                line_num,
                CONTEXT_LINES,
            )

        # --- ENHANCED PROMPT WITH LEARNING FEEDBACK ---
        prompt = create_enhanced_llm_prompt(error, original_snippet)
        fixed_snippet_str = get_llm_fix(llm, prompt)

        if not fixed_snippet_str.strip():
            print(
                "[!] Warning: LLM returned an empty fix. Skipping this error.",
            )
            continue

        print("    --- LLM's Suggested Fix ---")
        # To avoid printing a giant function, let's just show a diff-like summary
        diff = unified_diff(
            original_snippet.splitlines(keepends=True),
            fixed_snippet_str.splitlines(keepends=True),
            fromfile="original",
            tofile="fixed",
        )
        print("".join(diff))
        print("    ---------------------------")

        # --- ENHANCED VERIFICATION LOGIC WITH REINFORCEMENT LEARNING ---

        # 1. Create a fresh proposal for this specific change
        proposed_lines = list(temp_file_lines)
        fixed_lines = [line + "\n" for line in fixed_snippet_str.split("\n")]

        # Ensure the last line doesn't have an extra newline if the snippet didn't
        if fixed_snippet_str and not fixed_snippet_str.endswith("\n"):
            fixed_lines[-1] = fixed_lines[-1].rstrip("\n")

        proposed_lines[start_idx:end_idx] = fixed_lines

        # 2. Enhanced verification with quality assessment
        is_valid = False
        temp_file_path = ""
        failure_reason = None
        
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                delete=False,
                suffix=".py",
                encoding="utf-8",
            ) as temp_f:
                temp_f.writelines(proposed_lines)
                temp_file_path = temp_f.name

            # 3. Check for syntax errors using ast.parse
            with open(temp_file_path, encoding="utf-8") as f_to_check:
                ast.parse(f_to_check.read())

            # 4. Enhanced quality verification
            success, reward, failure_reason = verify_fix_quality(
                original_snippet, fixed_snippet_str, fixed_snippet_str
            )
            
            if success:
                is_valid = True
                print(f"[+] LLM fix passed all checks. Reward: {reward:.2f}")
            else:
                print(f"[!] LLM fix failed quality check: {failure_reason}. Reward: {reward:.2f}")
                is_valid = False

        except SyntaxError as e:
            failure_reason = f"syntax_error: {str(e)}"
            print(
                f"[!] Critical: LLM fix introduced a syntax error: {e}. Rejecting change.",
            )
            is_valid = False
        except Exception as e:
            failure_reason = f"unexpected_error: {str(e)}"
            print(f"[!] An unexpected error occurred during verification: {e}")
            is_valid = False
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)

        # 5. Record the experience for reinforcement learning
        experience = FixExperience(
            timestamp=datetime.now().isoformat(),
            error_code=error["error_code"],
            error_message=error["message"],
            original_code=original_snippet,
            llm_response=fixed_snippet_str,
            fixed_code=fixed_snippet_str,
            success=is_valid,
            reward=reward if 'reward' in locals() else (RL_CONFIG["reward_success"] if is_valid else RL_CONFIG["penalty_syntax_error"]),
            failure_reason=failure_reason
        )
        
        rl_manager.record_experience(experience)
        
        # 6. Provide feedback to the user
        if is_valid:
            print(f"    [*] ✅ Applying validated fix. Reward: {experience.reward:.2f}")
            temp_file_lines = proposed_lines
        else:
            print(f"    [*] ❌ Skipping fix due to validation failure. Penalty: {experience.reward:.2f}")
            continue
        # --- END ENHANCED VERIFICATION LOGIC ---

    # Only write to the original file if the final version is different
    if original_file_content != "".join(temp_file_lines):
        print(f"\n[*] Changes detected. Writing updates to {file_path}...")
        with open(file_path, "w") as f:
            f.writelines(temp_file_lines)
        print("[+] File saved.")
        return True
    print("\n[*] No changes made after LLM review. File remains untouched.")
    return False


def test_ruff_detection():
    """Test mode that only checks for Ruff errors without using the LLM."""
    print("--- Ruff Detection Test Mode ---")

    python_files = glob.glob("*.py")
    script_name = os.path.basename(__file__)
    if script_name in python_files:
        python_files.remove(script_name)

    if not python_files:
        print("No Python files to process in this directory.")
        return

    print(
        f"Found {len(python_files)} Python file(s) to test: {', '.join(python_files)}",
    )

    for file_path in python_files:
        print(f"\n--- Testing: {file_path} ---")

        if check_for_syntax_errors(file_path):
            continue

        ruff_output = run_ruff(file_path)
        if not ruff_output.strip():
            print("[+] No ruff errors found.")
            continue

        errors = parse_ruff_output(ruff_output)
        if not errors:
            print("[+] Ruff ran, but no parsable errors were found.")
            continue

        print(f"[*] Found {len(errors)} errors:")
        for error in errors:
            print(
                f"  - Line {error['line_number']}: [{error['error_code']}] {error['message']}",
            )

    print("\n--- Test Complete ---")


def main():
    """Main driver to find and process all Python files in the current directory with reinforcement learning."""
    import sys

    # Check if test mode is requested
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_ruff_detection()
        return
    
    # Check if performance report is requested
    if len(sys.argv) > 1 and sys.argv[1] == "--report":
        print("--- LLM Learning Performance Report ---")
        summary = rl_manager.get_performance_summary()
        print(f"Total Experiences: {summary['total_experiences']}")
        print(f"Overall Success Rate: {summary['overall_success_rate']:.2%}")
        if 'recent_success_rate' in summary:
            print(f"Recent Success Rate: {summary['recent_success_rate']:.2%}")
        if 'average_reward' in summary:
            print(f"Average Reward: {summary['average_reward']:.2f}")
        print("\nError Code Performance:")
        for error_code, success_rate in summary['error_code_performance'].items():
            print(f"  {error_code}: {success_rate:.2%}")
        if summary['last_training']:
            print(f"\nLast Training: {summary['last_training']}")
        return
    
    # Check if training is requested
    if len(sys.argv) > 1 and sys.argv[1] == "--train":
        print("--- Training Reinforcement Learning Model ---")
        rl_manager.train_model()
        return

    print("--- LLM Bulk Ruff Fixer with Reinforcement Learning ---")
    
    # Show current performance
    summary = rl_manager.get_performance_summary()
    if summary['total_experiences'] > 0:
        print(f"Current Success Rate: {summary['overall_success_rate']:.2%}")
        print(f"Total Learning Experiences: {summary['total_experiences']}")

    python_files = glob.glob("*.py")

    script_name = os.path.basename(__file__)
    if script_name in python_files:
        python_files.remove(script_name)

    if not python_files:
        print("No Python files to process in this directory.")
        return

    print(
        f"Found {len(python_files)} Python file(s) to process: {', '.join(python_files)}",
    )

    print(f"\n[*] Loading LLM model from: {LLM_MODEL_PATH}")
    try:
        # Intel Mac optimized configuration
        llm = Llama(model_path=LLM_MODEL_PATH, **LLM_CONFIG)
    except Exception as e:
        print(f"[!] Critical Error: Failed to load LLM model: {e}")
        print(
            "[!] You can still test the Ruff detection without the LLM by running in test mode.",
        )
        print(
            "[!] Try adjusting n_threads or n_batch if you encounter memory issues.",
        )
        return

    files_modified = []
    for file_path in python_files:
        if process_file(file_path, llm):
            files_modified.append(file_path)

    # Train the model after processing
    if summary['total_experiences'] > 0:
        print("\n[*] Training reinforcement learning model...")
        rl_manager.train_model()

    print("\n--- Summary ---")
    print(f"Processed {len(python_files)} file(s).")
    if files_modified:
        print(f"Modified {len(files_modified)} file(s):")
        for f in files_modified:
            print(f"  - {f}")
    else:
        print("No files were modified.")
    
    # Show updated performance
    updated_summary = rl_manager.get_performance_summary()
    if updated_summary['total_experiences'] > summary['total_experiences']:
        new_experiences = updated_summary['total_experiences'] - summary['total_experiences']
        print(f"\n--- Learning Progress ---")
        print(f"New experiences recorded: {new_experiences}")
        print(f"Updated success rate: {updated_summary['overall_success_rate']:.2%}")
        if 'average_reward' in updated_summary:
            print(f"Average reward: {updated_summary['average_reward']:.2f}")
    
    print("--- Done ---")
    print("\nUsage:")
    print("  python llm_ruff_fixer.py --report  # View learning performance")
    print("  python llm_ruff_fixer.py --train   # Train the model")
    print("  python llm_ruff_fixer.py --test    # Test mode without LLM")


if __name__ == "__main__":
    main()
