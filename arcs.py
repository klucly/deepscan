import pygame
from typing import Tuple
import numpy as np


def _angle_to_coords(theta: float, radius: float) -> complex:
    return np.e**(theta*1j)*radius

def _generate_outer_line(coords, width: float):
    return coords / np.absolute(coords) * width + coords

def _decomplex_coord(coord):
    return coord.real, coord.imag

def calculate_arc(center: Tuple[float, float], radius: float, width: float, start_angle: float, end_angle: float, resolution: int):
    to_coords = np.vectorize(_angle_to_coords)
    decomplex_coords = np.vectorize(_decomplex_coord)

    theta = np.arange(start_angle, end_angle, 2*np.pi/resolution)
    theta = np.append(theta, (end_angle,))

    inner_line = to_coords(theta, radius-width)
    outer_line = _generate_outer_line(inner_line, width)

    complex_center = center[0]+center[1]*1j
    
    inner_line += complex_center
    outer_line += complex_center

    complex_coords = np.concatenate((inner_line, outer_line[::-1]), 0)

    xs, ys = decomplex_coords(complex_coords)
    xs = np.reshape(xs, (*xs.shape,1))
    ys = np.reshape(ys, (*ys.shape,1))

    coords = np.concatenate((xs, ys), 1)

    return coords

def draw_arc(display: pygame.display, color: Tuple[int, int, int], coords):
    pygame.draw.polygon(display, color, coords)
