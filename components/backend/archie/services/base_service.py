from abc import ABC, abstractmethod


class BaseService(ABC):
    @property
    @abstractmethod
    def service_name(self):
        pass

    # cli
    @abstractmethod
    def get_account_url_from_id(self, id) -> str:
        pass

    @abstractmethod
    def get_account_id_from_url(self, link: str) -> str:
        pass

    @abstractmethod
    def run(self, config):
        pass

    # api
    class ApiAccountInfo:
        name: str

    @abstractmethod
    def get_account_info(self, id) -> ApiAccountInfo:
        pass
