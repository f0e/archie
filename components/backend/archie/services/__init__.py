from .base_service import BaseService
from .soundcloud import SoundCloudService
from .youtube import YouTubeService

# idk
service_list: list[BaseService] = [
    YouTubeService(),
    SoundCloudService(),
]

services = {}
for service in service_list:
    services[service.service_name.lower()] = service
