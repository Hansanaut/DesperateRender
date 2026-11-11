"""Read-only inspection of a running Fooocus Gradio application."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


class RuntimeInspectionError(RuntimeError):
    """Raised when the Fooocus generate chain cannot be validated safely."""


@dataclass(frozen=True)
class FooocusInputSpec:
    """A single ordered input of the Fooocus task-creation dependency."""

    payload_index: int
    component_id: int
    component_type: str
    label: str | None
    default_value: Any
    elem_id: str | None
    component_props: dict[str, Any]
    choices: tuple[Any, ...] | None
    serializer: str | None
    api_info: dict[str, Any] | None


@dataclass(frozen=True)
class FooocusRuntimeSpec:
    """Validated, read-only description of Fooocus' generate task endpoint."""

    generate_button_id: int
    seed_refresh_fn_index: int
    task_creation_fn_index: int
    generation_fn_index: int
    current_task_component_id: int
    inputs: tuple[FooocusInputSpec, ...]
    gradio_version: str | None

    @property
    def input_count(self) -> int:
        return len(self.inputs)


class FooocusRuntimeInspector:
    """Discover and validate the generate chain exposed by Fooocus' ``/config``.

    The inspector only performs ``GET /config``. It never invokes a Gradio
    dependency and does not modify the Fooocus instance or its configuration.
    """

    def __init__(
        self,
        url: str = "http://127.0.0.1:7865",
        *,
        timeout: float = 10.0,
        expected_input_count: int = 153,
    ) -> None:
        self.url = url.rstrip("/")
        self.timeout = timeout
        self.expected_input_count = expected_input_count

    def inspect(self) -> FooocusRuntimeSpec:
        """Load ``/config`` and return the validated task-creation specification."""

        config = self._load_config()
        components = self._components_by_id(config)
        dependencies = self._dependencies(config)

        generate_button_id = self._find_generate_button_id(components)
        click_index = self._find_generate_click_dependency(
            dependencies,
            generate_button_id,
        )
        task_index, generation_index = self._find_task_and_generation_dependencies(
            dependencies,
            components,
            click_index,
        )

        task_dependency = dependencies[task_index]
        generation_dependency = dependencies[generation_index]
        current_task_component_id = task_dependency["outputs"][0]
        input_ids = task_dependency["inputs"]

        self._validate_generate_chain(
            dependencies=dependencies,
            click_index=click_index,
            task_index=task_index,
            generation_index=generation_index,
            current_task_component_id=current_task_component_id,
            task_inputs=input_ids,
            generation_inputs=generation_dependency.get("inputs", []),
        )

        inputs = tuple(
            self._to_input_spec(index, component_id, components[component_id])
            for index, component_id in enumerate(input_ids)
        )

        return FooocusRuntimeSpec(
            generate_button_id=generate_button_id,
            seed_refresh_fn_index=task_dependency["trigger_after"],
            task_creation_fn_index=task_index,
            generation_fn_index=generation_index,
            current_task_component_id=current_task_component_id,
            inputs=inputs,
            gradio_version=config.get("version"),
        )

    def _load_config(self) -> dict[str, Any]:
        try:
            response = requests.get(f"{self.url}/config", timeout=self.timeout)
            response.raise_for_status()
            config = response.json()
        except requests.RequestException as error:
            raise RuntimeInspectionError(
                f"Could not read Fooocus Gradio config at {self.url}/config."
            ) from error

        if not isinstance(config, dict):
            raise RuntimeInspectionError("Fooocus /config did not return a JSON object.")

        return config

    @staticmethod
    def _components_by_id(config: dict[str, Any]) -> dict[int, dict[str, Any]]:
        components = config.get("components")
        if not isinstance(components, list):
            raise RuntimeInspectionError("Fooocus config has no component list.")

        result = {
            component["id"]: component
            for component in components
            if isinstance(component, dict) and isinstance(component.get("id"), int)
        }
        if not result:
            raise RuntimeInspectionError("Fooocus config contains no valid components.")

        return result

    @staticmethod
    def _dependencies(config: dict[str, Any]) -> list[dict[str, Any]]:
        dependencies = config.get("dependencies")
        if not isinstance(dependencies, list):
            raise RuntimeInspectionError("Fooocus config has no dependency list.")
        if not all(isinstance(dependency, dict) for dependency in dependencies):
            raise RuntimeInspectionError("Fooocus config contains an invalid dependency.")
        return dependencies

    @staticmethod
    def _find_generate_button_id(components: dict[int, dict[str, Any]]) -> int:
        matches = []
        for component_id, component in components.items():
            props = component.get("props", {})
            if component.get("type") != "button" or not isinstance(props, dict):
                continue
            if props.get("elem_id") == "generate_button":
                matches.append(component_id)

        if len(matches) != 1:
            raise RuntimeInspectionError(
                "Could not identify exactly one Fooocus generate button."
            )
        return matches[0]

    @staticmethod
    def _find_generate_click_dependency(
        dependencies: list[dict[str, Any]],
        generate_button_id: int,
    ) -> int:
        matches = [
            index
            for index, dependency in enumerate(dependencies)
            if dependency.get("trigger") == "click"
            and generate_button_id in FooocusRuntimeInspector._target_ids(dependency)
            and dependency.get("trigger_after") is None
        ]
        if len(matches) != 1:
            raise RuntimeInspectionError(
                "Could not identify exactly one initial generate-button dependency."
            )
        return matches[0]

    def _find_task_and_generation_dependencies(
        self,
        dependencies: list[dict[str, Any]],
        components: dict[int, dict[str, Any]],
        click_index: int,
    ) -> tuple[int, int]:
        candidates: list[tuple[int, int]] = []
        for task_index, task_dependency in enumerate(dependencies):
            output_ids = task_dependency.get("outputs", [])
            input_ids = task_dependency.get("inputs", [])
            current_task_id = output_ids[0] if len(output_ids) == 1 else None

            if (
                task_dependency.get("trigger") != "then"
                or not isinstance(current_task_id, int)
                or len(input_ids) < 2
                or input_ids[0] != current_task_id
                or components.get(current_task_id, {}).get("type") != "state"
                or not self._descends_from(dependencies, task_index, click_index)
            ):
                continue

            for generation_index, generation_dependency in enumerate(dependencies):
                if (
                    generation_dependency.get("trigger_after") == task_index
                    and generation_dependency.get("trigger") == "then"
                    and generation_dependency.get("inputs") == [current_task_id]
                    and generation_dependency.get("outputs")
                ):
                    candidates.append((task_index, generation_index))

        if len(candidates) != 1:
            raise RuntimeInspectionError(
                "Could not identify exactly one task-creation/generation dependency pair."
            )
        return candidates[0]

    def _validate_generate_chain(
        self,
        *,
        dependencies: list[dict[str, Any]],
        click_index: int,
        task_index: int,
        generation_index: int,
        current_task_component_id: int,
        task_inputs: list[Any],
        generation_inputs: list[Any],
    ) -> None:
        seed_refresh_index = dependencies[task_index].get("trigger_after")
        if not isinstance(seed_refresh_index, int):
            raise RuntimeInspectionError("Task creation has no preceding seed-refresh dependency.")
        if not self._descends_from(dependencies, seed_refresh_index, click_index):
            raise RuntimeInspectionError("Seed refresh is not part of the generate-button chain.")
        if dependencies[generation_index].get("trigger_after") != task_index:
            raise RuntimeInspectionError("Generation does not directly follow task creation.")
        if not task_inputs or task_inputs[0] != current_task_component_id:
            raise RuntimeInspectionError("Task creation does not use currentTask at input index 0.")
        if generation_inputs != [current_task_component_id]:
            raise RuntimeInspectionError("Generation does not use currentTask as its sole input.")
        if len(task_inputs) != self.expected_input_count:
            raise RuntimeInspectionError(
                "Unexpected Fooocus task input count: "
                f"expected {self.expected_input_count}, got {len(task_inputs)}."
            )

    @staticmethod
    def _descends_from(
        dependencies: list[dict[str, Any]],
        index: int,
        ancestor_index: int,
    ) -> bool:
        seen: set[int] = set()
        current_index: int | None = index
        while current_index is not None and current_index not in seen:
            if current_index == ancestor_index:
                return True
            seen.add(current_index)
            trigger_after = dependencies[current_index].get("trigger_after")
            current_index = trigger_after if isinstance(trigger_after, int) else None
        return False

    @staticmethod
    def _target_ids(dependency: dict[str, Any]) -> set[int]:
        targets = dependency.get("targets", [])
        result: set[int] = set()
        for target in targets:
            if isinstance(target, int):
                result.add(target)
            elif isinstance(target, (list, tuple)) and target and isinstance(target[0], int):
                result.add(target[0])
        return result

    @staticmethod
    def _to_input_spec(
        payload_index: int,
        component_id: int,
        component: dict[str, Any],
    ) -> FooocusInputSpec:
        props = component.get("props", {})
        if not isinstance(props, dict):
            props = {}
        choices = props.get("choices")
        if not isinstance(choices, (list, tuple)):
            choices = None
        api_info = component.get("api_info")
        if not isinstance(api_info, dict):
            api_info = None

        return FooocusInputSpec(
            payload_index=payload_index,
            component_id=component_id,
            component_type=str(component.get("type", "unknown")),
            label=props.get("label") if isinstance(props.get("label"), str) else None,
            default_value=props.get("value"),
            elem_id=props.get("elem_id")
            if isinstance(props.get("elem_id"), str)
            else None,
            component_props=dict(props),
            choices=tuple(choices) if choices is not None else None,
            serializer=component.get("serializer")
            if isinstance(component.get("serializer"), str)
            else None,
            api_info=api_info,
        )
