from fooocus_client import FooocusClient


class ModelService:

    def __init__(self, client: FooocusClient):
        self.client = client

    def get_config(self) -> dict:
        return self.client.client.config
    
    def get_components(self):
        return self.client.client.config["components"]
    
    def get_dropdowns(self):
        return [
            c for c in self.get_components()
            if c.get("type") == "dropdown"
        ]
    
    def get_base_models(self) -> list[str]:
        return self._get_dropdown_choices("Base Model (SDXL only)")

    def get_refiners(self) -> list[str]:
        return self._get_dropdown_choices("Refiner (SDXL or SD 1.5)")

    def get_samplers(self) -> list[str]:
        return self._get_dropdown_choices("Sampler")

    def _get_dropdown_choices(self, label: str) -> list[str]:

        for dropdown in self.get_dropdowns():

            props = dropdown.get("props", {})

            if props.get("label") == label:
                return props.get("choices", [])

        return []
    
    def get_refiners(self) -> list[str]:
        return self._get_dropdown_choices("Refiner (SDXL or SD 1.5)")

    def get_schedulers(self) -> list[str]:
        return self._get_dropdown_choices("Scheduler")

    def get_vaes(self) -> list[str]:
        return self._get_dropdown_choices("VAE")
