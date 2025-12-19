from abc import ABC, abstractmethod

class InteractionMode(ABC):
    def __init__(self, canvas):
        self.canvas = canvas
        self.name   = None

        self._delta_horizontal = 5 # int(canvas.width / 8)
        self._delta_vertical   = 5 # int(canvas.height / 8)

    def _move_commands(self, key):
        """RETURNS: True, if a 'move key' has been pressed.
                    False, else.
        """
        if   key == 'a': self.canvas._add_horizontal_offset(- self._delta_horizontal); return True
        elif key == 'd': self.canvas._add_horizontal_offset(self._delta_horizontal);   return True
        elif key == 'w': self.canvas._add_vertical_offset(- self._delta_vertical);     return True
        elif key == 's': self.canvas._add_vertical_offset(self._delta_vertical);       return True
        else:            return False

    def _exit(self, key):
        """RETURNS: True, if 'exit' key has been pressed.
                    False, else.
        """
        return key == 'q'

    @abstractmethod
    def do(self, key): pass

