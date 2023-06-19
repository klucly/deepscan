import pygame
from arcs import calculate_arc, draw_arc
from math import pi
from backend import generate_structure, calculate_size, calculate_offset
from numpy import arctan2, sqrt
import subprocess
from tkinter import filedialog
from time import perf_counter
from multiprocessing import Process
import multiprocessing as mp
from threading import Thread
from typing import NoReturn, Optional, Tuple


pygame.init()

WIDTH = 1280
HEIGHT = 920

ARC_WIDTH = 40
ARC_X_SPACING = 0.01
ARC_Y_SPACING = 0.3
STARTING_RADIUS = 50
RESOLUTION = 1000
MAX_DEPTH = 20
FPS = 60

TEXT_COLOR = (255, 255, 255)

def convert_mouse_coordinates(mouse_pos) -> Tuple[float, int]:
    # Make the center of the screen a zero
    mouse_x = mouse_pos[0]-WIDTH//2
    mouse_y = mouse_pos[1]-HEIGHT//2

    # Get the resized angle of a mouse
    # relative to the center of a screen
    angle_coef = (-arctan2(mouse_x, mouse_y)/2/pi + 0.25) % 1.

    # Get the distance in levels of a mouse
    # relative to the center of a screen
    raw_distance = sqrt(mouse_x * mouse_x + mouse_y * mouse_y)
    distance = (raw_distance-STARTING_RADIUS)/ARC_WIDTH

    # Distance = -1 when the mouse is over
    # the main button
    if distance >= 0: level = int(distance)
    else: level = -1

    return angle_coef, level

def recalculate_arcs(arc_buffer, scanned_system) -> None:
    for level_id, level in enumerate(scanned_system):
        arc_buffer.append([])

        # Break in case we ran out of bounds
        if level_id > MAX_DEPTH: break

        for folder_id, folder in enumerate(level):
            
            start_angle = 2*pi*folder.offset
            end_angle = start_angle + 2*pi*folder.relative_weight

            if folder.relative_weight < ARC_X_SPACING / 2 / pi:
                continue

            arc = calculate_arc(
                (WIDTH/2, HEIGHT/2),
                (level_id + 1) * ARC_WIDTH + STARTING_RADIUS, ARC_WIDTH * (1 - ARC_Y_SPACING),
                start_angle, end_angle - ARC_X_SPACING, RESOLUTION
            )
            
            # NOTE: Sometimes arcs can be so small,
            # the end points and the starting points will
            # be the same, in which case there will only
            # be 2 points. In this case the arc cannot be
            # drawn since to draw a polygon you need at least
            # 3 points. Here we account for this scenario
            if len(arc) > 2:
                arc_buffer[-1].append((folder_id, arc))

def _scan_folder(folder, connection) -> None:
    starting_time = perf_counter()
    arc_buffer = []

    print("Generating structure...")
    scanned_system = generate_structure(folder)
    print("Calculating sizes...")
    calculate_size(scanned_system)
    print("Calculating offsets...")
    calculate_offset(scanned_system)

    connection.send(scanned_system)

    print("Generating output...")
    recalculate_arcs(arc_buffer, scanned_system)

    print(f"Done in {perf_counter()-starting_time:0.2f} seconds")

    connection.send(arc_buffer)

class Main:
    def __init__(self) -> None:
        # Initialize window
        self.display = pygame.display.set_mode((WIDTH, HEIGHT))
        
        # Folder structure.
        # - List of levels. Each level has own depth.
        # - Depth of a subfolder = depth of a folder + 1
        # - Each folder is connected to the parent folder
        # but the parent folder is not connected to its
        # subfolders.
        self.scanned_system = []

        # Buffer of arcs to render.
        # Inherits the overall structure of folders:
        # - Broken down to levels as self.scanned_system
        # - Id of an arc corresponds to the index of
        # the folder it represents on same level.
        self.arc_buffer = []

        # Easy way to handle fps
        self.clock = pygame.time.Clock()

        # Tick variable being incremented each cycle
        self.tick = 0

        # Should the program be closed
        self.is_terminated = False

        # Is program in a state of scanning a folder
        self.calculating = False

        # Last known position of a mouse
        self.mouse_pos = (0, 0)

        # Is the "open" button highlighted with a cursor
        self.is_main_highlighted = False

        # Coordinates in scanned_system space coordinates system
        # of a currently highlighted object.
        # If the "open" button is highlighted, will equal to the
        # last known position of a highlighted arc.
        self.highlighted_pos = (0, 0)

        # Highlighted folder.
        # If the "open" button is highlighted, will equal to the
        # last known highlighted folder.
        self.highlighted_obj = None

        # Overall font for all of the text rendered
        self.font = pygame.font.Font('freesansbold.ttf', 16)

        # Text which indicates the name of a currently
        # highlighted folder.
        self.foldername_text = self.font.render("", True, TEXT_COLOR)

        # The text on the main button
        self.open_folder_text = self.font.render("open", True, TEXT_COLOR)

        # The box in which self.foldername_text will be rendered
        self.text_rect = self.foldername_text.get_rect()

        # The box in which self.open_folder_text will be rendered
        self.open_text_rect = self.open_folder_text.get_rect()
        self.open_text_rect.center = WIDTH // 2, HEIGHT // 2

        # Setting up a thread which will communicate with
        # a process which will scan the folders.
        # Having the scan of folders in another process allows us
        # to not have any performance issues while the scanning
        # process is active. Communication to it through
        # a different thread allows it to wait for the response
        # and change the needed parameters in the Main without
        # the need of the main thread, therefore making least
        # performance issues we can have.
        self.worker_connection, con_for_worker = mp.Pipe()
        self.working_handler = Thread(target = self._worker_handling, args = (con_for_worker,))
        self.working_handler.start()

        # Running the main loop until we dont need to
        while not self.is_terminated:
            self.mainloop()

        self.worker_connection.close()

    def mainloop(self) -> NoReturn:
        # Handling all of the user input
        self.handle_events(pygame.event.get())
        self.tick += 1

        # Update currently highlighted object
        self.update_highlighted()

        # Render everything onto the screen
        self.render()

        # Update the screen
        pygame.display.flip()

        # Every second update the title of a window
        # according to fps
        if self.tick % FPS == 0:
            pygame.display.set_caption(f"DeepScan | fps: {self.clock.get_fps():.2f}")

        # Wait some time to control fps
        self.clock.tick(FPS)

    def scan_folder(self, folder) -> None:
        # Send a signal to worker connection thread
        self.worker_connection.send(folder)

    def _worker_handling(self, main_connection) -> NoReturn:
        while True:
            # Wait for the scan signal
            try:
                folder = main_connection.recv()

            # In case the program should be closed
            # the connection will be closed
            # In this case we just close the thread
            except EOFError:
                break
            
            # Run the worker process
            # NOTE: We could initialize the working process
            # at the beginning of the program and then just
            # communicate with it giving us negligible
            # scan runtime improvements, but its saver
            # to run the process every time in case it
            # dies for some reason
            connection, worker_connection = mp.Pipe()
            worker_process = Process(target = _scan_folder, args = (folder, worker_connection))
            worker_process.start()

            self.calculating = True

            # Wait for the worker process to calculate
            self.scanned_system = connection.recv()
            self.arc_buffer = connection.recv()

            self.calculating = False

    def ask_folder(self) -> Optional[str]:
        return filedialog.askdirectory()

    def handle_events(self, events) -> None:
        for event in events:

            # Incase we want to quit
            # send corresponding signal
            if event.type == pygame.QUIT:
                self.is_terminated = True

            # Update the position of the mouse and
            # the text of a highlighted folder
            # if mouse moves
            elif event.type == pygame.MOUSEMOTION:
                if self.highlighted_obj:
                    text = f"{self.highlighted_obj.title} ({self.highlighted_obj.weight/2**30:0.2f}gb)"
                    self.foldername_text = self.font.render(text, True, TEXT_COLOR)

                self.mouse_pos = event.pos

            # Handling mouse click
            elif event.type == pygame.MOUSEBUTTONUP and not self.calculating:

                # Open highlighted folder incase we have one
                if self.highlighted_obj and not self.is_main_highlighted:
                    subprocess.Popen(f'explorer "{self.highlighted_obj.path}"')

                # If main button is highlighted,
                # ask a folder to scan and
                # send the signal to scan it
                elif self.is_main_highlighted:
                    folder_path = self.ask_folder()
                    if folder_path:
                        self.scan_folder(folder_path)

    def update_highlighted(self) -> None:
        # Convert screen space coordinates of a mouse
        # into scan system space coordinates
        angle_coef, distance = convert_mouse_coordinates(self.mouse_pos)
        
        # Incase of out of bounds distance
        if distance < 0 or distance >= len(self.scanned_system):

            # If the main button is highlighted
            if distance == -1:
                self.is_main_highlighted = True

            return
            
        # Get the layer of a highlighted folder
        layer = self.scanned_system[distance]

        # Get the highlighted folder
        # NOTE: Binary search can be implemented
        # for unnoticeably higher performance.
        found = False
        for folder_i, folder in enumerate(layer):
            if folder.offset + folder.relative_weight > angle_coef > folder.offset:
                found = True
                break

        # Highlight main if none highlighted
        self.is_main_highlighted = not found
        if not found: return

        # In case we find an arc to highlight,
        # we update highlight
        self.highlighted_pos = (distance, folder_i)
        self.highlighted_obj = folder

    def render(self) -> None:
        # Background color
        self.display.fill((20, 20, 20))

        # Calculating the color of a main button
        if self.is_main_highlighted and not self.calculating:
            circle_color = (160, 160, 160)
        else: circle_color = (80, 80, 80)

        # Rendering the main button
        pygame.draw.circle(self.display, circle_color, (WIDTH//2, HEIGHT//2), STARTING_RADIUS)

        # Rendering the arcs
        for level_i, level in enumerate(self.arc_buffer):
            for arc_id, arc in level:

                if (level_i, arc_id) == self.highlighted_pos and not self.is_main_highlighted:
                    color = (40, 150, 150)
                else: color = (40, 40, 40)

                draw_arc(self.display, color, arc)

        # Rendering main button text
        self.display.blit(self.open_folder_text, self.open_text_rect)

        # Rendering folder name text
        if not self.is_main_highlighted:
            self.text_rect.topleft = self.mouse_pos[0]+10, self.mouse_pos[1]
            self.display.blit(self.foldername_text, self.text_rect)


if __name__ == "__main__":
    Main()
