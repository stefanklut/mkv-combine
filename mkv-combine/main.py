import argparse
from pathlib import Path
from typing import Optional

def get_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tool for renaming files for usage with entertainment hub (Plex/TheTVDB)")
    
    io_args = parser.add_argument_group("IO")
    io_args.add_argument("-i", "--input", nargs="+", help="Input folder/file", type=str, required=True)
    
    args = parser.parse_args()
    return args
    
def main(args):
    pass
    

if __name__ == "__main__":
    args = get_arguments()
    main(args)