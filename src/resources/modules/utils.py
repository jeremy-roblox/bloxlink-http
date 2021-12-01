from os import listdir
from ..structures import Bloxlink # pylint: disable=import-error, no-name-in-module, no-name-in-module


@Bloxlink.module
class Utils(Bloxlink.Module):

    @staticmethod
    def get_files(directory):
        return [name for name in listdir(directory) if name[:1] != "." and name[:2] != "__" and name != "_DS_Store"]
