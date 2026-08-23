"""The game expressed as an MDP with states, actions, rewards, and an env adapter.

This package contains what a Reinforcement Learning method needs. The LLM
experiment reads the raw observation and imports none of these modules, which is
why the package is called `env` rather than `common`.

    encoding.py     observation -> hashable state key, action -> stable key
    rewards.py      five reward functions, selectable by name
    environment.py  TrainingEnv: reset/step in those terms
"""

from . import rewards
from .encoding import ENCODING_VERSION, action_key, state_key
from .environment import TrainingEnv

__all__ = ["TrainingEnv", "state_key", "action_key", "rewards", "ENCODING_VERSION"]
