from abc import ABC, abstractmethod

class BaseAgent(ABC):
    @abstractmethod
    def system_prompt(self): pass
    @abstractmethod
    def user_prompt(self, concept, transcript, interjection=None): pass
