DMX Lighting and Audio‑Driven Lighting Concepts

DMX512 overview. DMX512 (Digital Multiplex) is a standardized protocol for digital communication networks that is widely used to control stage and architectural lighting. Originally developed to unify incompatible dimmer protocols, it has become the primary method of linking lighting consoles to dimmers and effects devices such as fog machines and intelligent lights. In a typical DMX universe, a controller sends a stream of 8‑bit values over a differential RS‑485 bus; each of up to 512 channels corresponds to the brightness, color or other parameter of a lighting fixture. While DMX specifies a wired, daisy‑chained topology, modern implementations often bridge DMX data over network protocols or wireless links.

Audio‑driven lighting. To create dynamic lighting effects that respond to music, one can perform a real‑time fast Fourier transform (FFT) on an audio signal and map frequency bands (e.g., bass, midrange, treble) to lighting parameters. For example, low frequencies might drive the brightness of flood lights, while high frequencies control the hue of a spotlight. A Python script using libraries like numpy and websockets can read audio from a file or microphone, compute the FFT, and translate the results into DMX channel values or WebSocket messages. This forms the basis of the audio‑reactive lighting system described below.

ResoniteLink AI Asset Creator (Component‑Discovery Branch)

The vibe‑coding‑resonitelink repository (branch component‑discovery) is a natural‑language interface for building 3D scenes in Resonite VR using ResoniteLink’s WebSocket protocol. Key points from our exploration:

User‑friendly building: Users can type commands like “create a red spinning cube” or “build a campfire,” and the system generates the necessary JSON commands to create slots, attach components and assign materials. The application supports basic shapes, positioning, scaling, animations and lights (point, spot and directional).

Configuration and setup: To use the tool, you install Python dependencies (pip install anthropic websockets), copy resonite_builder.conf.example to resonite_builder.conf, add your Anthropic API key, and enable ResoniteLink in Resonite. The configuration file specifies settings like the WebSocket URL, AI model and timeouts.

Modular architecture: The project is organised into modules: resonite_builder.py (main entry point and user loop), vibe_config.py (configuration loader), vibe_logging.py (logging and JSON export), vibe_client.py (WebSocket client for ResoniteLink), vibe_executor.py (AI prompt processing and command execution), vibe_components.py (component registry and field definitions), vibe_types.py (helpers for data types), and vibe_templates.py (scene templates). This separation makes it easier to extend the system.

Data flow: User prompts are sent to an AI model, which returns a list of commands. vibe_executor.py parses these commands and calls methods in vibe_client.py to send addSlot, addComponent, updateComponent and getComponent messages over the WebSocket to Resonite. Resonite creates or updates objects accordingly.

Component definitions: The vibe_components.py file defines a mapping from human‑readable component names (e.g., light, spinner, material) to their full FrooxEngine identifiers and lists configurable fields. For lights, configurable fields include type, intensity, color, range and spot_angle. Enumeration types such as LightType, BlendMode and ShadowCastMode are also defined for easier AI‑driven selection.

Proposed Audio‑Reactive Lighting System

Building on the above findings, we developed a Python script (dmx_audio_websocket.py) that demonstrates how to drive lighting parameters based on audio input and send the results over a WebSocket. The main features of this implementation are:

Audio processing: The script reads audio frames from a file or real‑time source and applies an FFT to derive energy levels in low, mid and high frequency bands. These levels are scaled to produce values suitable for lighting control (e.g., intensities between 0 and 1 and RGB colours).

WebSocket integration: The processed data are packaged into JSON messages and transmitted over a WebSocket. When connected to ResoniteLink, the script can update Light components by sending updateComponent commands with new Color and Intensity values. Alternatively, the JSON data could be forwarded to a DMX controller via a separate library to drive physical lights.

Modularity: Functions are provided to map frequency energies to colour hues and to convert between numerical ranges. The script can be extended to support multiple lighting groups, user‑specified mappings or integration with other protocols (e.g., Art‑Net or sACN for DMX over IP).

Next Steps

The discovery process so far has produced a solid foundation for an audio‑reactive lighting system that can operate within Resonite VR or drive external DMX fixtures. The next steps will involve:

Repository setup: Creating a new GitHub repository to host the project’s code, documentation and future development. A clear repository name helps convey its purpose (see below).

Code integration: Refactoring the current script into a package structure, adding configuration options for WebSocket addresses and DMX universes, and integrating it with the Resonite AI asset builder where appropriate.

Testing and iteration: Running the system in a live Resonite environment and with physical DMX lights to refine the mappings between audio frequencies and lighting parameters.

Documentation: Providing step‑by‑step setup instructions, configuration examples and usage notes so that others can easily replicate the environment.

Should we make it a dotnet10 project?
