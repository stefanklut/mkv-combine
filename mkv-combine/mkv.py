from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Optional
import iso639

# Global variables
default_mkv_path: Path = Path(__file__).parents[1].joinpath("resources/mkvmerge.exe")

def format_path(path: str|Path):
    if not isinstance(path, str|Path):
        raise TypeError(f"Path needs to be set as Path or str, currently {type(path)}")
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
        
class FileNotSupportedError(OSError):
    pass
        
class MKV():
    def __init__(self,
                 file_path,
                 mkvmerge_path = None
                 ) -> None:
        # MKVMerge
        self._mkvmerge_path: Optional[Path] = None
        self.mkvmerge_path = mkvmerge_path
        
        # Info json (mkmerge -J path)
        self._info_json_hash = None
        self._info_json = None
        
        # Current file
        self._file_path: Optional[Path] = None
        self.file_path = file_path
    
    def __repr__(self):
        attribs = {k: i for k, i in self.__dict__.items() if not k.startswith('_')}
        for name in dir(self.__class__):
            if name.startswith("_"):
                continue  
            obj = getattr(self.__class__, name)
            if isinstance(obj, property):
                val = obj.__get__(self, self.__class__)
                attribs.update({name: val})
        return f"{self.__class__}({repr(attribs)})"
        
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
            
    def info_json(self, file_path=None):
        # Overwrite check for adding other file paths
        if file_path is not None:
            _file_path = format_path(file_path)
        else:
            _file_path = self.file_path
        
        # Return if result is precomputed
        if self._info_json is not None and _file_path == self._info_json_hash:
            return self._info_json
        
        # Stop if file not found in filesystem
        if not _file_path.is_file():
            raise FileNotFoundError(f"File {_file_path} not found")
        
        # Verify install of MKVMerge
        self.verify_mkvmerge()
        
        # Get info json
        try:
            output = subprocess.check_output([self.mkvmerge_path, '-J', _file_path]).decode()
            info_json = json.loads(output)
            
            # Save to instance
            self._info_json_hash = _file_path
            self._info_json = info_json
            
            return info_json
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise ValueError(f"File path at {_file_path} has not returned an info json")
        
    def verify_supported(self, file_path=None):
        info_json = self.info_json(file_path=file_path)
        
        # Check if file recognized by mkvmerge
        if not info_json['container']['supported']:
            raise FileNotSupportedError(f"File path at {file_path} has not passed the supported verification")         
        
class MKVTrack(MKV):
    def __init__(self, 
                 file_path, 
                 mkvmerge_path=None, 
                 track_id=0, 
                 track_name=None, 
                 language=None, 
                 default_track=False, 
                 forced_track=False
                 ) -> None:
        super().__init__(file_path, mkvmerge_path)
        
        # track info
        self._track_codec = None
        self._track_type = None

        # base
        self._track_id = None
        self.track_id = track_id

        # flags
        self._language = None
        self._tags = None
        
        self.set_defaults_from_info_json()
                
        # overwrite tracks
        self.track_name = track_name
        self.language = language
        self.default_track = default_track
        self.forced_track = forced_track

        # exclusions
        self.no_chapters = False
        self.no_global_tags = False
        self.no_track_tags = False
        self.no_attachments = False
    
    @property
    def track_id(self):
        return self._track_id

    @track_id.setter
    def track_id(self, track_id):
        info_json = self.info_json()
        if not 0 <= track_id < len(info_json['tracks']):
            raise IndexError("track index out of range")
        self._track_id = track_id
        self._track_codec = info_json['tracks'][track_id]['codec']
        self._track_type = info_json['tracks'][track_id]['type']
    
    def track_from_track_id(self):
        info_json = self.info_json()
        
        if self.track_id is None:
            return None
        
        tracks = info_json.get("tracks")
        if tracks is None:
            raise IndexError(f"{self.file_path} does not contain tracks")
        
        for track in tracks:
            if track.get("id") == self.track_id:
                return track
            
        return None
    
    def set_defaults_from_info_json(self):
        track = self.track_from_track_id()
        
        if track is None:
            raise IndexError(f"track with index {self.track_id} out of range")
        
        if 'track_name' in track['properties']:
            self.track_name = track['properties']['track_name']
        if 'language' in track['properties']:
            self.language = track['properties']['language']
        if 'default_track' in track['properties']:
            self.default_track = track['properties']['default_track']
        if 'forced_track' in track['properties']:
            self.forced_track = track['properties']['forced_track']

    @property
    def language(self):
        return self._language

    @language.setter
    def language(self, language):
        if language is None or is_ISO639_2(language):
            self._language = language
        else:
            raise ValueError("not an ISO639-2 language code")

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
    
class MKVFile(MKV):
    def __init__(self, 
                 file_path, 
                 mkvmerge_path=None, 
                 title: Optional[str]=None) -> None:
        super().__init__(file_path, mkvmerge_path)
        
        self.title = title
        
        info_json = self.info_json()
        
        self.tracks: list[MKVTrack] = []
        for track in info_json["tracks"]:
            self.tracks.append(MKVTrack(self.file_path, track_id=track["id"]))
            
    def contains_video(self):
        for track in self.tracks:
            if track.track_type == "video":
                return True
        return False
    
    def contains_subtitles(self):
        for track in self.tracks:
            if track.track_type == "subtitles":
                return True
        return False
            
    def command(self, output_path: str|Path):
        output_path = format_path(output_path)
        if output_path.suffix != ".mkv":
            raise ValueError(f"Output file should have suffix .mkv, currently {output_path.suffix}")
        command = [f"{self.mkvmerge_path}", "-o", f"{output_path}"]
        if self.title is not None:
            command.extend(["--title", self.title])
        
        for track in self.tracks:
            if track.track_name is not None:
                command.extend(["--track-name", f"{track.track_id}:{track.track_name}"])
                
            if track.language is not None:
                command.extend(["--language", f"{track.track_id}:{track.language}"])
                
            if track.tags is not None:
                command.extend(["--tags", f"{track.track_id}:{track.tags}"])
                
            if track.default_track:
                command.extend(["--default-track", f"{track.track_id}:1"])
            else:
                command.extend(["--default-track", f"{track.track_id}:0"])
                
            if track.forced_track:
                command.extend(["--forced-track", f"{track.track_id}:1"])
            else:
                command.extend(["--forced-track", f"{track.track_id}:0"])

            # remove extra tracks
            if track.track_type != 'video':
                command.append("-D")
            else:
                command.extend(["-d", f"{track.track_id}"])
            if track.track_type != 'audio':
                command.append("-A")
            else:
                command.extend(["-a", f"{track.track_id}"])
            if track.track_type != 'subtitles':
                command.append("-S")
            else:
                command.extend(["-s", f"{track.track_id}"])

            # exclusions
            if track.no_chapters:
                command.append("--no-chapters")
            if track.no_global_tags:
                command.append("--no-global-tags")
            if track.no_track_tags:
                command.append("--no-track-tags")
            if track.no_attachments:
                command.append("--no-attachments")

            # add path
            command.append(f"{track.file_path}")

        #TODO add attachments, chapters, splits
        return command
    
    def mux(self, output_path: str|Path, silent: bool=True):
        command = self.command(output_path)
        if silent:
            result = subprocess.run(command, check=False, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL)
        else:
            result = subprocess.run(command, check=False, capture_output=True)
        if result.returncode == 2:
            raise subprocess.SubprocessError(result)

    def add_track(self, track: str|Path|MKVTrack):
        if isinstance(track, str|Path):
            self.tracks.append(MKVTrack(track))
        elif isinstance(track, MKVTrack):
            self.tracks.append(track)
        else:
            raise TypeError(f"track {track} is not str, Path or MKVTrack")
    
    def add_file(self, file: str|Path|MKVFile):
        if isinstance(file, str|Path):
            self.tracks = self.tracks + MKVFile(file).tracks
        elif isinstance(file, MKVFile):
            self.tracks = self.tracks + file.tracks
        else:
            raise TypeError(f"File {file} is not str or MKVFile")
        
    def ignore_chapters(self, ignore: bool=True):
        for track in self.tracks:
            track.no_chapters = ignore

    def ignore_global_tags(self, ignore: bool=True):
        for track in self.tracks:
            track.no_global_tags = ignore

    def ignore_track_tags(self, ignore: bool=True):
        for track in self.tracks:
            track.no_track_tags = ignore

    def ignore_attachments(self, ignore: bool=True):
        for track in self.tracks:
            track.no_attachments = ignore
        
if __name__ == "__main__":
    mkv_file = MKVFile(r"~/Documents/shared/American.History.X.1998.1080p.BluRay.x265-RARBG/American.History.X.1998.1080p.BluRay.x265-RARBG.mp4")
    mkv_file.add_track(r"C:\Users\stefa\Documents\shared\American.History.X.1998.1080p.BluRay.x265-RARBG\Subs\2_English.srt")
    mkv_file.mux("video.mkv", silent=False)