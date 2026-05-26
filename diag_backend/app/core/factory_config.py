"""
厂区配置读取 — 从 YAML 配置文件中读取厂区列表
独立同步脚本和后端共享此配置源
"""
import os
from typing import Optional

from .config import get_settings

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "configs")
DEFAULT_YAML_PATH = os.path.join(CONFIG_DIR, "factories.yaml")


def load_factories_from_yaml(path: Optional[str] = None) -> list[dict]:
    """从 YAML 文件读取厂区列表"""
    filepath = path or (get_settings().factories_yaml_path or DEFAULT_YAML_PATH)
    if yaml is None:
        raise RuntimeError("PyYAML is required to load factory config: pip install pyyaml")
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"厂区配置文件不存在: {filepath}")
    with open(filepath, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("factories", [])


def get_factory_by_id(factory_id: str, path: Optional[str] = None) -> Optional[dict]:
    """根据 factory_id 查找厂区"""
    factories = load_factories_from_yaml(path)
    for f in factories:
        if f.get("factory_id") == factory_id:
            return f
    return None
