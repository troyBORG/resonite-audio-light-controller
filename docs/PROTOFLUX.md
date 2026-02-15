# ProtoFlux Creation via ResoniteLink (Exploratory)

This document captures research on creating ProtoFlux nodes from external tools via ResoniteLink.

## Current Status

**We do not create ProtoFlux.** Our program drives lights by sending `updateComponent` for Color/Intensity and `updateSlot` for rotation every frame over WebSocket. No in-world logic is required.

## Why ProtoFlux Might Be Useful

- **Offload updates**: ProtoFlux could read from DynamicVariables (e.g. Resonance's FFT bands) and drive lights without our program running.
- **Hybrid setup**: Our program writes to DynamicVariables; ProtoFlux reads them and drives lights.
- **In-world logic**: Rotation, smoothing, or pattern logic could run inside Resonite.

## How HeadlessUserCulling Creates ProtoFlux

The [HeadlessUserCulling](https://github.com/...) mod (C# inside Resonite) does:

```csharp
var ProtofluxSlot = parent.AddSlot("protoflu(x)", false);
var ElementSource = ProtofluxSlot.AttachComponent(ProtoFluxHelper.GetSourceNode(typeof(Slot)));
var GetSlotActiveSelf = ProtofluxSlot.AttachComponent<GetSlotActiveSelf>();
GetSlotActiveSelf.TryConnectInput(GetSlotActiveSelf.GetInput(0), ElementSource.GetOutput(0), false, false);
// ... more nodes and connections
```

Key points:
- ProtoFlux nodes are components attached to slots.
- Connections use `TryConnectInput(outputNode, inputNode)` - references between components.
- ResoniteLink uses `addComponent` with `members` for fields; references use `{"$type": "reference", "targetId": "..."}`.

## ResoniteLink Feasibility

| Task | Feasible? | Notes |
|------|-----------|-------|
| Add ProtoFlux node component | Maybe | Component type e.g. `[FrooxEngine]FrooxEngine.ProtoFlux.Runtimes.Execution.Nodes.ValueInput<float>` |
| Set node member values | Maybe | Depends on member names in schema |
| Wire output → input | Unknown | Requires knowing how connections are stored (likely Reference members) |
| Full graph creation | Hard | ProtoFlux graphs have many node types and connection patterns |

## Component Types (from intro-world.json)

- `FrooxEngine.ProtoFlux.Runtimes.Execution.Nodes.ValueInput<float>`
- `FrooxEngine.FrooxEngine.ProtoFlux.CoreNodes.ValueFieldDrive<float>`
- `FrooxEngine.ProtoFlux.Runtimes.Execution.Nodes.FrooxEngine.Variables.DynamicVariableValueInput<float>`
- etc.

## Next Steps for ProtoFlux Support

1. Use ResoniteLink's reflection API (if available) to discover ProtoFlux node members.
2. Create a single ValueInput + ValueFieldDrive graph, verify it works.
3. Map DynamicVariable read → drive flow.
4. Integrate as optional "create ProtoFlux drivers" mode.

For now, direct `updateComponent` / `updateSlot` remains the recommended approach.
