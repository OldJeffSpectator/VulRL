"""
VulRL PPO Training Entry Point for SkyRL

This module provides the main entry point for training VulRL models using SkyRL.
It follows the same pattern as mini_swe_agent, but uses the Worker Router architecture
instead of local environment execution.

Usage:
    uv run -m vulrl_inside_skyrl_v2.main_vulrl_skyrl \
        data.train_data="['/path/to/train.parquet']" \
        generator.worker_router_url="http://localhost:5000" \
        generator.http_endpoint_host="localhost" \
        generator.http_endpoint_port=8001
"""

import hydra
from omegaconf import DictConfig, OmegaConf
from skyrl_train.entrypoints.main_base import BasePPOExp, config_dir, validate_cfg
from skyrl_train.utils import initialize_ray
import ray

from .ez_vulrl_generator import EzVulRLGenerator


class VulrlPPOExp(BasePPOExp):
    """
    VulRL PPO Experiment class.
    
    Inherits from BasePPOExp and overrides get_generator() to use EzVulRLGenerator
    instead of the default SkyRLGymGenerator.
    """
    
    def get_generator(self, cfg, tokenizer, inference_engine_client):
        """
        Create and return the VulRL generator.
        
        This generator delegates rollout execution to Worker Router via HTTP,
        instead of running environments locally.
        
        Args:
            cfg: Hydra configuration object
            tokenizer: Tokenizer for the model
            inference_engine_client: InferenceEngineClient (will be ignored by VulRL generator)
            
        Returns:
            EzVulRLGenerator instance
        """
        # Extract configuration
        worker_router_url = cfg.generator.get("worker_router_url", "http://localhost:5000")
        llm_endpoint_host = cfg.generator.get("http_endpoint_host", "localhost")
        llm_endpoint_port = cfg.generator.get("http_endpoint_port", 8001)
        llm_endpoint = f"http://{llm_endpoint_host}:{llm_endpoint_port}"
        
        # Extract model name from path (last part)
        model_path = self.cfg.trainer.policy.model.path
        model_name = model_path.split("/")[-1] if "/" in model_path else model_path
        
        # Polling configuration
        polling_config = {
            "timeout": cfg.generator.get("rollout_timeout", 600.0),      # 10 minutes default
            "poll_interval": cfg.generator.get("poll_interval", 10.0),    # 10 seconds default
            "verbose": cfg.generator.get("polling_verbose", True),
        }
        
        print("=" * 80)
        print("VulRL Generator Configuration")
        print("=" * 80)
        print(f"  Worker Router URL: {worker_router_url}")
        print(f"  LLM Endpoint: {llm_endpoint}")
        print(f"  Model Name: {model_name}")
        print(f"  Polling Timeout: {polling_config['timeout']}s")
        print(f"  Poll Interval: {polling_config['poll_interval']}s")
        print("=" * 80)
        
        generator = EzVulRLGenerator(
            generator_cfg=cfg.generator,
            skyrl_gym_cfg=OmegaConf.create({"max_env_workers": 0}),  # No local workers needed
            inference_engine_client=inference_engine_client,  # Will be ignored
            tokenizer=tokenizer,
            model_name=model_name,
            worker_router_url=worker_router_url,
            llm_endpoint=llm_endpoint,
            llm_model_name=model_name,
            polling_config=polling_config,
        )
        
        return generator


@ray.remote(num_cpus=1)
def skyrl_entrypoint(cfg: DictConfig):
    """
    Ray remote function to run the training loop.
    
    This ensures that the training loop is not run on the head node.
    """
    exp = VulrlPPOExp(cfg)
    exp.run()


@hydra.main(config_path=config_dir, config_name="ppo_base_config", version_base=None)
def main(cfg: DictConfig) -> None:
    """
    Main entry point for VulRL training.
    
    This function:
    1. Validates the configuration
    2. Initializes Ray
    3. Launches the training loop as a Ray remote task
    """
    # Validate the arguments
    validate_cfg(cfg)
    
    # Initialize Ray
    initialize_ray(cfg)
    
    # Run training loop
    ray.get(skyrl_entrypoint.remote(cfg))


if __name__ == "__main__":
    main()
