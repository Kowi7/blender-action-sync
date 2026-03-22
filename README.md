# Action Sync – Blender Addon

Automatically syncs the active Action from an Armature to all target Mesh objects, including Shape Keys. Fixes a common Blender 5 workflow issue where switching animations on an Armature does not update linked Meshes.

---

## The Problem

Blender 5 introduced a new Action Slot system that allows a single Action to animate multiple objects at once. However, switching the active Action on an Armature does not automatically update the Action on linked Mesh objects — meaning Shape Keys and other mesh-level animations stay stuck on the wrong Action.

This becomes especially frustrating when working with character rigs where an Armature and its Mesh children need to stay in sync.

---

## The Solution

Action Sync runs a lightweight background handler that detects when the Armature's active Action changes and immediately mirrors it to all target objects — covering Object, Object Data, and Shape Key animation data.

---

## Installation

1. Download `action_sync.zip`
2. In Blender: **Edit → Preferences → Extensions → Install from Disk**
3. Select the ZIP file
4. The addon is now active

---

## Usage

1. Open **Properties → Scene → Action Sync**
2. Enable the addon by checking **Auto Sync**
3. Set your **Source Armature** via the dropdown or select it in the viewport and click the eyedropper
4. Select each Mesh object in the viewport and click **Add Selected** to add it as a sync target
5. Done — switching Actions on the Armature now automatically updates all target objects

You can also trigger a manual sync at any time using the **Sync Now** button.

---

## Compatibility

- Blender 4.4 or higher (developed and tested on Blender 5.0.1)

---

## License

GPL-2.0-or-later

---

## About

Made by [Junglegreen Studios](https://junglegreenstudios.com) while animating a four-legged horror monster for Between Walls – A Backrooms Game.

Contributions and feedback welcome via GitHub Issues.
