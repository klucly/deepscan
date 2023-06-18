import os
from queue import Queue
from typing import List
from folder import FolderUI


def _add_subfolders(parent: FolderUI, queue: Queue) -> None:
    for entry in os.scandir(parent.path):
        # Skip the files
        if entry.is_file():
            continue
        
        # Add subfolder to a queue
        queue.put((parent, entry.path))
        

def generate_structure(start_path = 'C:\Program Files (x86)') -> List[List[FolderUI]]:
    build_array = []
    queue = Queue()
    prev_depth = -1

    start_path = start_path.replace("/", "\\")

    # Add a task to scan 
    # start_path to the queue
    queue.put((None, start_path))

    while not queue.empty():
        # Get task from queue
        parent, path = queue.get()
        title = path.split("\\")[-1]
        path: str
        parent: FolderUI
        
        # Creating new levels on depth change
        depth = path.count("\\")
        if depth != prev_depth:
            prev_depth = depth
            build_array.append([])

            print("Depth is now:", depth)

        # Initialize current folder
        current_directory = FolderUI(path, title, 0.0, 0.0, parent)
        build_array[-1].append(current_directory)

        # Scan the current folder
        # and add all subfolders to the queue
        try:
            _add_subfolders(current_directory, queue)

        # We DO NOT CARE about the exact size
        # down to a single byte, so we just skip
        # all of the folders we were unable to access
        except PermissionError:
            pass
        except FileNotFoundError:
            pass
        except NotADirectoryError:
            pass

    return build_array


def _get_size_of(path):
    size = 0

    # Update size depending on the size of each
    # of the files in the current folder
    for sub in os.scandir(path):
        if sub.is_file():
            size += sub.stat().st_size

    return size


def calculate_size(build_array: List[List[FolderUI]]) -> None:
    for level in build_array[::-1]:
        for folder in level:

            try:
                size = _get_size_of(folder.path)
            except PermissionError:
                continue
            except FileNotFoundError:
                continue
            except NotADirectoryError:
                continue
            
            # Update self size
            folder.weight += size

            # Update the size of a parent
            if folder.parent:
                folder.parent.weight += folder.weight


def calculate_offset(build_array: List[List[FolderUI]]) -> None:
    for layer in build_array:
        position = 0.
        previous_parent = None

        for folder in layer:
            if folder.parent != previous_parent:
                previous_parent = folder.parent
                position = 0.
            
            # Incase of folder being the main one,
            # we ignore further procedures
            if not folder.parent:
                folder.relative_weight = 1.
                continue

            if build_array[0][0].weight == 0:
                break
            
            # Update folder parameters
            folder.relative_weight = folder.weight / build_array[0][0].weight
            folder.offset = folder.parent.offset + position
            
            position += folder.relative_weight
