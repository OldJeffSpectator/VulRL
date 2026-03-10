"""Reward calculation for exploitation actions."""

from typing import Tuple


class RewardCalculator:
    """Calculate rewards based on observations."""
    
    def __init__(self):
        """Initialize reward calculator."""
        # Success patterns (1.0 reward, done=True)
        self.success_patterns = [
            "shell obtained",
            "root@",
            "# whoami",
            "flag{",
            "privilege escalation successful",
            "exploit successful",
        ]
        
        # Progress patterns (0.1-0.5 reward, done=False)
        self.progress_patterns = {
            0.5: ["connection established", "vulnerability confirmed", "exploit succeeded"],
            0.3: ["service detected", "authentication bypassed", "access granted"],
            0.1: ["port open", "service running", "target reachable"],
        }
        
        # Error patterns (-0.1 reward, done=False)
        self.error_patterns = [
            "error",
            "failed",
            "connection refused",
            "timeout",
            "permission denied",
        ]
    
    def compute_reward(self, observation: str, action: str, step: int) -> Tuple[float, bool]:
        """Compute reward based on observation.
        
        Args:
            observation: Action output/observation
            action: Action taken
            step: Current step number
            
        Returns:
            Tuple of (reward, done)
        """
        obs_lower = observation.lower()
        
        # Check success patterns
        for pattern in self.success_patterns:
            if pattern in obs_lower:
                return 1.0, True
        
        # Check progress patterns
        for reward, patterns in self.progress_patterns.items():
            for pattern in patterns:
                if pattern in obs_lower:
                    return reward, False
        
        # Check error patterns
        for pattern in self.error_patterns:
            if pattern in obs_lower:
                return -0.1, False
        
        # Default: no progress
        return 0.0, False
