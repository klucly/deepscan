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

pygame.init()

WIDTH = 1280
HEIGHT = 920

ARC_WIDTH = 40
ARC_X_SPACING = 0.05
ARC_Y_SPACING = 0.3
STARTING_RADIUS = 50
RESOLUTION = 1000
MAX_DEPTH = 20

TEXT_COLOR = (255, 255, 255)

def convert_mouse_coordinates(mouse_pos):
    mouse_x = mouse_pos[0]-WIDTH//2
    mouse_y = mouse_pos[1]-HEIGHT//2
    angle_coef = (-arctan2(mouse_x, mouse_y)/2/pi + 0.25) % 1.
    raw_distance = sqrt(mouse_x * mouse_x + mouse_y * mouse_y)
    distance = (raw_distance-STARTING_RADIUS)/ARC_WIDTH

    if distance >= 0: level = int(distance)
    else: level = -1

    return angle_coef, level

def recalculate(arc_buffer, scanned_system):
    for level_id, level in enumerate(scanned_system):
        arc_buffer.append([])
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
    recalculate(arc_buffer, scanned_system)

    print(f"Done in {perf_counter()-starting_time:0.2f} seconds")

    connection.send(arc_buffer)

class Main:
    def __init__(self) -> None:
        self.display = pygame.display.set_mode((WIDTH, HEIGHT))
        
        self.mouse_pos = (0, 0)
        self.scanned_system = []
        self.arc_buffer = []
        self.clock = pygame.time.Clock()
        self.tick = 0
        self.is_terminated = False
        self.calculating = False

        self.is_main_highlighted = False
        self.highlighted_pos = (0, 0)
        self.highlighted_obj = None
        self.font = pygame.font.Font('freesansbold.ttf', 16)
        self.foldername_text = self.font.render("", True, TEXT_COLOR)
        self.text_rect = self.foldername_text.get_rect()
        self.worker_connection, con_for_worker = mp.Pipe()
        self.working_handler = Thread(target = self._worker_handling, args = (con_for_worker,))
        self.working_handler.start()

        self.open_folder_text = self.font.render("open", True, TEXT_COLOR)

        while not self.is_terminated:
            self.mainloop()

    def scan_folder(self, folder) -> None:
        self.worker_connection.send(folder)

    def _worker_handling(self, main_connection):
        while True:
            folder = main_connection.recv()

            connection, worker_connection = mp.Pipe()
            worker_process = Process(target = _scan_folder, args = (folder, worker_connection))
            worker_process.start()

            self.calculating = True

            self.scanned_system = connection.recv()
            self.arc_buffer = connection.recv()

            self.calculating = False

    def ask_folder(self):
        return filedialog.askdirectory()

    def handle_events(self, events) -> None:
        for event in events:
            if event.type == pygame.QUIT:
                self.is_terminated = True

            elif event.type == pygame.MOUSEMOTION:
                if self.highlighted_obj:
                    self.foldername_text = self.font.render(self.highlighted_obj.title, True, TEXT_COLOR)

                self.mouse_pos = event.pos

            elif event.type == pygame.MOUSEBUTTONUP and not self.calculating:
                if self.highlighted_obj and not self.is_main_highlighted:
                    subprocess.Popen(f'explorer "{self.highlighted_obj.path}"')

                elif self.is_main_highlighted:
                    folder_path = self.ask_folder()
                    if folder_path:
                        self.scan_folder(folder_path)

    def handle_mouse_input(self) -> None:
        angle_coef, distance = convert_mouse_coordinates(self.mouse_pos)

        if distance >= 0 and distance < len(self.scanned_system):
            layer = self.scanned_system[distance]

            for folder_i, folder in enumerate(layer):
                if folder.offset + folder.relative_weight > angle_coef > folder.offset:
                    break
                
            folder = layer[folder_i]

            self.is_main_highlighted = False
            self.highlighted_pos = (distance, folder_i)
            self.highlighted_obj = folder
        elif distance == -1:
            self.is_main_highlighted = True

    def mainloop(self):
        self.handle_events(pygame.event.get())
        self.tick += 1

        self.handle_mouse_input()

        self.render()

        pygame.display.flip()

        if self.tick % 60 == 0:
            pygame.display.set_caption(f"Fps: {self.clock.get_fps():.2f}")

        self.clock.tick(60)

    def render(self):
        self.display.fill((20, 20, 20))

        if self.is_main_highlighted and not self.calculating:
            circle_color = (160, 160, 160)
        else:
            circle_color = (80, 80, 80)
        pygame.draw.circle(self.display, circle_color, (WIDTH//2, HEIGHT//2), STARTING_RADIUS)

        for level_i, level in enumerate(self.arc_buffer):
            for arc_id, arc in level:
                if (level_i, arc_id) == self.highlighted_pos and not self.is_main_highlighted:
                    color = (40, 150, 150)
                else:
                    color = (40, 40, 40)

                draw_arc(self.display, color, arc)

        rect = self.open_folder_text.get_rect()
        rect.center = WIDTH // 2, HEIGHT // 2
        self.display.blit(self.open_folder_text, rect)

        if not self.is_main_highlighted:
            self.text_rect.topleft = self.mouse_pos[0]+10, self.mouse_pos[1]
            self.display.blit(self.foldername_text, self.text_rect)
                

if __name__ == "__main__":
    Main()
