import json
import re
import subprocess
from pathlib import Path
import methodtools
from typing import Optional
import iso639

# Global variables
default_mkv_path: Path = Path(__file__).parents[1].joinpath("resources/mkvmerge.exe")

def format_path(path: str):
    return Path(path).expanduser().resolve()

# Language check
def is_ISO639_2(language):
  try:
    iso639.languages.get(part2b=language)
    return True
  except KeyError:
    return False

class ExternalInstallError(OSError):
    """
    Raised when an externally installed program errors when checking if it is installed
    """
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(args)
        self.program_name = kwargs.get('program_name')
        
class MKV():
    def __init__(self,
                 file_path,
                 mkvmerge_path = None
                 ) -> None:
        self._mkvmerge_path: Optional[Path] = None
        self.mkvmerge_path = mkvmerge_path
        
        self._file_path: Optional[Path] = None
        self.file_path = file_path
        
    @property
    def file_path(self):
        if not isinstance(self._file_path, Path):
            raise TypeError(f"File path needs to be set as Path, currently {type(self._file_path)}")
        return self._file_path

    @file_path.setter
    def file_path(self, file_path):
        if file_path is None:
            return
        file_path = format_path(file_path)
        self.verify_supported(file_path=file_path)
        self._file_path = file_path
    
    @property
    def mkvmerge_path(self):
        if self._mkvmerge_path is None:
            self._mkvmerge_path = default_mkv_path
        if not isinstance(self._mkvmerge_path, Path):
            raise TypeError(f"MKV path needs to be set as Path, currently {type(self._file_path)}")
        return self._mkvmerge_path
    
    @mkvmerge_path.setter
    def mkvmerge_path(self, mkvmerge_path):
        if mkvmerge_path is None:
            return
        mkvmerge_path = format_path(mkvmerge_path)
        self.verify_mkvmerge(mkvmerge_path=mkvmerge_path)
        self._mkvmerge_path = mkvmerge_path
    
    def verify_mkvmerge(self, mkvmerge_path=None):
        # Overwrite check for adding other mkvmerge versions
        if mkvmerge_path is not None:
            _mkvmerge_path = format_path(mkvmerge_path)
        else:
            _mkvmerge_path = self.mkvmerge_path
            
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
    
    @methodtools.lru_cache(maxsize=1)
    def info_json(self, file_path=None):
        # Overwrite check for adding other file paths
        if file_path is not None:
            _file_path = format_path(file_path)
        else:
            _file_path = self.file_path
        
        # Stop if file not found in filesystem
        if not _file_path.is_file():
            raise FileNotFoundError(f"File {_file_path} not found")
        
        # Verify install of MKVMerge
        self.verify_mkvmerge()
        
        # Get info json
        try:
            output = subprocess.check_output([self.mkvmerge_path, '-J', _file_path]).decode()
            info_json = json.loads(output)
            return info_json
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise ValueError(f"File path at {_file_path} has not returned an info json")
        
    def verify_supported(self, file_path=None):
        info_json = self.info_json(file_path=file_path)
        
        # Check if file recognized by mkvmerge
        if not info_json['container']['supported']:
            raise ValueError(f"File path at {file_path} has not passed the supported verification")
            
        
class MKVTrack(MKV):
    def __init__(self, file_path, mkvmerge_path=None, track_id=0, track_name=None, language=None, default_track=False, forced_track=False):
        super().__init__(file_path, mkvmerge_path)
        
        # track info
        self._track_codec = None
        self._track_type = None

        # base
        self._track_id = None
        self.track_id = track_id

        # flags
        self.track_name = track_name
        self._language = None
        self.language = language
        self._tags = None
        self.default_track = default_track
        self.forced_track = forced_track

        # exclusions
        self.no_chapters = False
        self.no_global_tags = False
        self.no_track_tags = False
        self.no_attachments = False

    def __repr__(self):
        return repr(self.__dict__)

    @property
    def track_id(self):
        return self._track_id

    @track_id.setter
    def track_id(self, track_id):
        info_json = self.info_json()
        if not 0 <= track_id < len(info_json['tracks']):
            raise IndexError('track index out of range')
        self._track_id = track_id
        self._track_codec = info_json['tracks'][track_id]['codec']
        self._track_type = info_json['tracks'][track_id]['type']

    @property
    def language(self):
        return self._language

    @language.setter
    def language(self, language):
        if language is None or is_ISO639_2(language):
            self._language = language
        else:
            raise ValueError('not an ISO639-2 language code')

    @property
    def tags(self):
        return self._tags

    @tags.setter
    def tags(self, path):
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f"File {path} not found")
        self._tags = path

    @property
    def track_codec(self):
        return self._track_codec

    @property
    def track_type(self):
        return self._track_type
    
    @classmethod
    def from_file(cls, file_path, track_id=0):
        pass
    #TODO Load based on track_id
    
class MKVFile(MKV):
    def __init__(self, file_path, mkvmerge_path=None) -> None:
        super().__init__(file_path, mkvmerge_path)
     
        
if __name__ == "__main__":
    MKVFile(file_path="~/Documents/shared/American.History.X.1998.1080p.BluRay.x265-RARBG/American.History.X.1998.1080p.BluRay.x265-RARBG.mp4")