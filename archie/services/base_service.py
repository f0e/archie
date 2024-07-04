from abc import ABC, abstractmethod

import archie.config as cfg


class BaseService(ABC):
    @property
    @abstractmethod
    def get_service_name(self):
        pass

    @property
    @abstractmethod
    def get_api(self):  # TODO: this probably shouldnt be public? add methods here?
        pass

    @abstractmethod
    def run(self, config: cfg.Config):
        pass
