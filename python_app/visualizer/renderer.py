from __future__ import annotations

from dataclasses import dataclass

import pygame

@dataclass(frozen=True)
class RenderSize:
    width: int
    height: int

class Renderer:
    def __init__(self, size: RenderSize, background_path: str) -> None:
        pygame.init()
        self._size = size
        self._surface = pygame.Surface((size.width, size.height), flags=pygame.SRCALPHA)
        self._background = self._load_background(background_path)

    @property
    def surface(self) -> pygame.Surface:
        return self._surface

    def _load_background(self, background_path: str) -> pygame.Surface:
        bg = pygame.image.load(background_path)
        return pygame.transform.smoothscale(bg, (self._size.width, self._size.height))

    def render_frame(self, fft) -> pygame.Surface:
        self._surface.blit(self._background, (0, 0))
        return self._surface
