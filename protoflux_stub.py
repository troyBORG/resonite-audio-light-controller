"""
ProtoFlux creation via ResoniteLink - EXPERIMENTAL STUB.

This module is a placeholder for future ProtoFlux support.
Creating ProtoFlux nodes from external tools requires mapping
the internal node/connection model to ResoniteLink's addComponent/updateComponent.

See docs/PROTOFLUX.md for research notes.

Current approach: we drive lights directly via updateComponent/updateSlot.
"""

# Component types observed in Resonite worlds (for reference)
VALUE_INPUT_FLOAT = "[FrooxEngine]FrooxEngine.ProtoFlux.Runtimes.Execution.Nodes.ValueInput<float>"
VALUE_FIELD_DRIVE_FLOAT = "[FrooxEngine]FrooxEngine.ProtoFlux.CoreNodes.ValueFieldDrive<float>"
DYNAMIC_VAR_INPUT_FLOAT = "[FrooxEngine]FrooxEngine.ProtoFlux.Runtimes.Execution.Nodes.FrooxEngine.Variables.DynamicVariableValueInput<float>"


async def create_protoflux_drivers(client, layout, space_name: str = "AudioLights") -> None:
    """
    Placeholder: would create ProtoFlux nodes to drive lights from DynamicVariables.
    Not implemented - would require reverse-engineering ProtoFlux connection schema.
    """
    raise NotImplementedError(
        "ProtoFlux creation via ResoniteLink is exploratory. "
        "Use direct updateComponent/updateSlot instead. See docs/PROTOFLUX.md."
    )
