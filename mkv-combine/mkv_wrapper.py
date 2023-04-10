import re
import subprocess
from pathlib import Path
import os
from typing import Optional

class ExternalInstallError(OSError):
    """
    Raised when an externally installed program errors when checking if it is installed
    """
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(args)
        self.program_name = kwargs.get('program_name')
    

class MKV():
    default_mkv_path: Path = Path(__file__).parents[2].joinpath("resources/mkvmerge.exe").resolve()
    
    def __init__(self,
                 file_path,
                 mkvmerge_path = None
                 ) -> None:
        self._mkvmerge_path: Optional[Path] = None
        self.mkvmerge_path = mkvmerge_path
        
    
    @property
    def mkvmerge_path(self):
        if self._mkvmerge_path is None:
            self._mkvmerge_path = MKV.default_mkv_path
        return self._mkvmerge_path
    
    @mkvmerge_path.setter
    def mkvmerge_path(self, path):
        if path is None:
            return
        self.verify_mkvmerge(mkvmerge_path=path)
        self._mkvmerge_path = Path(path)
    
    def verify_mkvmerge(self, mkvmerge_path=None):
        # Overwrite check for adding other mkvmerge versions
        _mkvmerge_path = self.mkvmerge_path
        if mkvmerge_path is not None:
            _mkvmerge_path = Path(mkvmerge_path)
            
        # Check if installed
        try:
            output = subprocess.check_output([_mkvmerge_path, '-V']).decode()
            if not re.match(r"mkvmerge.*", output):
                raise ValueError(f"Output should return version of MKVmerge, got \"{output}\"")
        except (subprocess.CalledProcessError, FileNotFoundError, ValueError) as e:
            raise ExternalInstallError(
                f"MKVMerge installed at {_mkvmerge_path} has not passed the install verification", 
                program_name=_mkvmerge_path
            )
        
        
        
        
if __name__ == "__main__":
    MKV(file_path="../../../shared/American.History.X.1998.1080p.BluRay.x265-RARBG/American.History.X.1998.1080p.BluRay.x265-RARBG.mp4",
        mkvmerge_path="./resources/mkvmerge.exe")