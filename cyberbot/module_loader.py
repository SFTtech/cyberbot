import importlib.util
import logging
from pathlib import Path
from types import ModuleType

from .modules import DEFAULT_MODULES

logger = logging.getLogger(__name__)


def load_modules(extra_module_locations: list[str]) -> dict[str, ModuleType]:
    loaded_modules: dict[str, ModuleType] = dict()

    # load in-tree modules
    for module_name in DEFAULT_MODULES:
        module = importlib.import_module(f"cyberbot.modules.{module_name}")
        loaded_modules[module_name] = module

    # load external modules
    for module_location in extra_module_locations:
        module_path = Path(module_location)
        if not module_path.exists():
            raise ValueError(f"failed to load extra module from {module_location!r}")

        module_name = module_path.stem
        mod_package_name = f"cyberbot.modules.{module_name}"
        if module_path.is_dir():
            # it's a module directory.
            module_path = module_path / '__init__.py'

        loader = importlib.machinery.SourceFileLoader(mod_package_name, str(module_path))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        if spec is None:
            raise Exception("failed to create spec from loader")
        module = importlib.util.module_from_spec(spec)

        try:
            loader.exec_module(module)
            loaded_modules[module_name] = module

        except Exception:
            logger.exception(f'failed to import module {module_name!r}')

    return loaded_modules
