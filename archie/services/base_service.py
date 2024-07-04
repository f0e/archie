from abc import ABC, abstractmethod

import archie.config as cfg


class BaseService(ABC):
    @property
    @abstractmethod
    def get_service_name(self):
        pass

    @abstractmethod
    def get_account_url_from_id(self, id: str):
        pass

    @abstractmethod
    def get_account_id_from_url(self, link: str):
        pass

    @abstractmethod
    def run(self, config: cfg.Config):
        pass
