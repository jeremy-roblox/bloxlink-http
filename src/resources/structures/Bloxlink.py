import snowfin
import traceback
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient as MongoClient
from importlib import import_module
from os import environ as env
from resources.secrets import MONGO_URL

loaded_modules = {}
loop = asyncio.get_event_loop()

class Bloxlink(snowfin.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.mongo = MongoClient(env.get("MONGO_URL", MONGO_URL))

    @staticmethod
    def log(*args):
        print(args) # FIXME
        pass

    @staticmethod
    def error(*args, **kwargs):
        print(args, kwargs) # FIXME
        pass

    @staticmethod
    def module(module):
        new_module = module()

        module_name = module.__name__.lower()
        module_dir  = module.__module__.lower()

        if hasattr(new_module, "__setup__"):
            loop.create_task(new_module.__setup__())

        Bloxlink.log(f"Loaded {module_name}")

        if hasattr(new_module, "__loaded__"):
            loop.create_task(new_module.__loaded__())

        if loaded_modules.get(module_dir):
            loaded_modules[module_dir][module_name] = new_module
        else:
            loaded_modules[module_dir] = {module_name: new_module}

        return new_module

    @staticmethod
    def command(command_class):
        command_obj = command_class()
        snowfin.slash_command(name=str(command_obj))(command_obj.__execute__)

        return command_class

    @staticmethod
    def get_module(dir_name, *, name_override=None, name_override_pattern="", path="resources.modules", attrs=None):
        save_as  = f"{name_override_pattern.lower()}{(dir_name).lower()}"
        modules  = loaded_modules.get(save_as)
        name_obj = (name_override or dir_name).lower()

        class_obj = None
        module    = None

        if not modules:
            import_name = f"{path}.{dir_name}".replace("src/", "").replace("/",".").replace(".py","")

            try:
                module = import_module(import_name)
            except (ModuleNotFoundError, ImportError) as e:
                Bloxlink.log(f"ERROR | {e}")
                traceback_text = traceback.format_exc()
                traceback_text = len(traceback_text) < 500 and traceback_text or f"...{traceback_text[len(traceback_text)-500:]}"
                Bloxlink.error(traceback_text, title=f"{dir_name}.py")

            except Exception as e:
                Bloxlink.log(f"ERROR | Module {dir_name} failed to load: {e}")
                traceback_text = traceback.format_exc()
                traceback_text = len(traceback_text) < 500 and traceback_text or f"...{traceback_text[len(traceback_text)-500:]}"
                Bloxlink.error(traceback_text, title=f"{dir_name}.py")
            else:
                for attr_name in dir(module):
                    if attr_name.lower() == name_obj:
                        class_obj = getattr(module, attr_name)
                        break

        if not attrs:
            return module or class_obj

        if class_obj is None and module:
            for attr_name in dir(module):
                if attr_name.lower() == name_obj:
                    class_obj = getattr(module, attr_name)

                    break

        if class_obj is not None:
            if attrs:
                attrs_list = list()

                if not isinstance(attrs, list):
                    attrs = [attrs]

                for attr in attrs:
                    if hasattr(class_obj, attr):
                        attrs_list.append(getattr(class_obj, attr))

                if len(attrs_list) == 1:
                    return attrs_list[0]
                else:
                    if not attrs_list:
                        return None

                    return (*attrs_list,)
            else:
                return class_obj

        raise ModuleNotFoundError(f"Unable to find module {name_obj} from {dir_name}")

    class Module:
        pass

# class Module:
#     client = Bloxlink
#     r = r
#     session = aiohttp.ClientSession(loop=loop, timeout=aiohttp.ClientTimeout(total=20))
#     loop = loop
#     redis = redis
#     cache = redis_cache
#     conn = Bloxlink.conn

# Bloxlink.Module = Module