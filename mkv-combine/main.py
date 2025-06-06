from __future__ import annotations

import argparse
from pathlib import Path
from typing import Generator, Iterator, Optional

import mkv
from send2trash import send2trash


def input_path(input_str: str):
    path = Path(input_str).expanduser().resolve()

    # checks
    if not path.exists():
        raise FileNotFoundError(f"Path {path} does not exist")

    return path


def get_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tool for combining files for usage with entertainment hub (Plex/TheTVDB)")

    io_args = parser.add_argument_group("IO")
    io_args.add_argument("-i", "--input", nargs="+", help="Input folder/file", type=input_path, required=True)

    options_args = parser.add_argument_group("Options")
    options_args.add_argument("-n", "--dry_run", action="store_true", help="Show commands to be executed")
    options_args.add_argument("-v", "--verbose", action="count", default=0, help="Print executions")
    # TODO Overwrite
    # options_args.add_argument("-o", "--overwrite", action='store_true', default=0, help="Print executions")

    args = parser.parse_args()
    return args


def glob_for_subs(path: Path):
    return path.rglob("**/Subs/")


def subs_from_paths(paths: Iterator[Path]):
    subs = []
    for possible_sub_path in paths:
        if not possible_sub_path.is_file():
            continue
        try:
            sub = mkv.MKVFile(possible_sub_path)
            if len(sub.tracks) != 1:
                continue
            if not sub.contains_subtitles():
                continue
            subs.append(sub)
        except mkv.FileNotSupportedError:
            continue
    return subs


def videos_from_paths(paths: Iterator[Path]):
    videos = []
    for possible_video_path in paths:
        if not possible_video_path.is_file():
            continue
        try:
            video = mkv.MKVFile(possible_video_path)
            if not video.contains_video:
                continue
            videos.append(video)
        except mkv.FileNotSupportedError:
            continue
    return videos


def match_subs_to_file(path: Path) -> Generator[tuple[mkv.MKVFile, list[mkv.MKVFile]], None, None]:
    sub_paths = list(path.glob("*"))
    if len(sub_paths) == 0:
        raise FileNotFoundError(f"Found nothing in Subs directory {path}")
    if all(path.is_file() for path in sub_paths):
        subs = subs_from_paths(path.glob("*"))
        if len(subs) == 0:
            raise FileNotFoundError(f"Found no possible subtitles files in {path}")
        videos = videos_from_paths(path.parent.glob("*"))
        if len(videos) == 0:
            raise FileNotFoundError(f"Found no possible video files in {path}")
        if len(videos) > 1:
            raise ValueError(f"Found multiple possible video files: {videos}")

        yield (videos[0], subs)
    elif all(path.is_dir() for path in sub_paths):
        for sub_path in sub_paths:
            subs = subs_from_paths(sub_path.glob("*"))
            if len(subs) == 0:
                raise FileNotFoundError(f"Found no possible subtitles files in {path}")
            videos = videos_from_paths(path.parent.glob(f"{sub_path.stem}.*"))
            if len(videos) == 0:
                raise FileNotFoundError(f"Found no possible video files in {path}")
            if len(videos) > 1:
                raise ValueError(f"Found multiple possible video files: {videos}")

            yield (videos[0], subs)
    else:
        raise NotImplementedError("Currently does not support mix of dirs and files")


def main(args):
    subs_paths = [subs_path for path in args.input for subs_path in glob_for_subs(path)]
    for subs_path in subs_paths:
        for video, subs in match_subs_to_file(subs_path):
            output_path = video.file_path.with_suffix(".mkv")
            for sub in subs:
                # TODO Improve this check, this is error prone if non contain english or dutch
                # Maybe move this check to mkv.py?
                if sub.tracks[0].language is None:
                    if "english" in sub.file_path.stem.lower():
                        sub.tracks[0].language = "eng"  # set language to english
                    elif "dutch" in sub.file_path.stem.lower():
                        sub.tracks[0].language = "dut"  # set language to dutch
                    else:
                        continue
                video.add_file(sub)
            if args.verbose > 0:
                print(f"Video:\n\t{video.file_path}")
            if args.verbose > 1:
                print(f"Subtitles:")
                for sub in subs:
                    print(f"\t{sub.file_path}")
                print(f"Output:\n\t{output_path}\n")
            if args.verbose > 2:
                print(f"Command:\n\t{' '.join(video.command(output_path))}")
            if args.dry_run:
                continue
            silent = False if args.verbose > 2 else True
            # IDEA Use atomic save for overwrite, but then don't send2trash
            video.mux(output_path, silent)
            send2trash(video.file_path)
        if args.dry_run:
            continue
        send2trash(subs_path)


if __name__ == "__main__":
    args = get_arguments()
    main(args)
