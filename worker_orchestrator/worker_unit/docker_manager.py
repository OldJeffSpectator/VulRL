"""Docker environment manager (demo - mocked operations)."""

from typing import Dict, Any
import asyncio


class DockerManager:
    """Manage Docker environments for rollouts.
    
    NOTE: This is a DEMO implementation with mocked Docker operations.
    Real implementation would use docker-py to manage actual containers.
    """
    
    def __init__(self):
        """Initialize Docker manager."""
        pass
    
    async def setup_environment(self, vulhub_path: str, cve_id: str) -> Dict[str, Any]:
        """Setup Docker environment.
        
        Args:
            vulhub_path: Path to vulhub directory
            cve_id: CVE identifier
            
        Returns:
            Docker context dict
        """
        # Mock: simulate docker-compose up
        await asyncio.sleep(0.5)
        
        return {
            "network_id": f"vulrl_{cve_id}_net",
            "containers": ["target_container_id", "attacker_container_id"],
            "target_ip": "172.17.0.2",
            "target_port": 8080,
            "compose_project": cve_id,
        }
    
    async def execute_action(
        self,
        action: str,
        docker_context: Dict[str, Any],
        timeout: int = 60,
    ) -> str:
        """Execute action in Docker container.
        
        Args:
            action: Command to execute
            docker_context: Docker context from setup_environment
            timeout: Timeout in seconds
            
        Returns:
            Command output (observation)
        """
        # Mock: simulate command execution
        await asyncio.sleep(0.2)
        
        # Generate mock observation based on action
        if "nmap" in action.lower():
            return f"PORT     STATE SERVICE\n8080/tcp open  http-proxy"
        elif "curl" in action.lower() or "http" in action.lower():
            return "HTTP/1.1 200 OK\nConnection established"
        elif "exploit" in action.lower():
            return "Exploit sent. Checking for shell..."
        else:
            return f"Executed: {action}\nOutput: Command completed"
    
    async def cleanup_environment(self, docker_context: Dict[str, Any]):
        """Cleanup Docker environment.
        
        Args:
            docker_context: Docker context from setup_environment
        """
        # Mock: simulate docker-compose down
        await asyncio.sleep(0.3)
