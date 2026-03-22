import bpy
from bpy.props import StringProperty, CollectionProperty, BoolProperty
from bpy.types import PropertyGroup, Panel, Operator, AddonPreferences

# ─────────────────────────────────────────────
#  Internal state
# ─────────────────────────────────────────────

_last_action = None


# ─────────────────────────────────────────────
#  Property Group – one entry per target mesh
# ─────────────────────────────────────────────

class ActionSyncTarget(PropertyGroup):
    obj_name: StringProperty(name="Object", default="")


# ─────────────────────────────────────────────
#  Scene properties
# ─────────────────────────────────────────────

class ActionSyncSettings(PropertyGroup):
    enabled: BoolProperty(
        name="Auto Sync",
        description="Automatically sync the armature action to all target objects",
        default=False,
    )
    armature_name: StringProperty(
        name="Armature",
        description="Name of the armature whose active action is the source",
        default="",
    )
    targets: CollectionProperty(type=ActionSyncTarget)
    active_target_index: bpy.props.IntProperty(default=0)


# ─────────────────────────────────────────────
#  Operators
# ─────────────────────────────────────────────

class ACTIONSYNC_OT_add_target(Operator):
    bl_idname = "action_sync.add_target"
    bl_label = "Add Target"
    bl_description = "Add a new target object to sync"

    def execute(self, context):
        settings = context.scene.action_sync
        settings.targets.add()
        settings.active_target_index = len(settings.targets) - 1
        return {'FINISHED'}


class ACTIONSYNC_OT_remove_target(Operator):
    bl_idname = "action_sync.remove_target"
    bl_label = "Remove Target"
    bl_description = "Remove the selected target object"

    def execute(self, context):
        settings = context.scene.action_sync
        idx = settings.active_target_index
        if 0 <= idx < len(settings.targets):
            settings.targets.remove(idx)
            settings.active_target_index = max(0, idx - 1)
        return {'FINISHED'}


class ACTIONSYNC_OT_pick_armature(Operator):
    bl_idname = "action_sync.pick_armature"
    bl_label = "Use Selected as Armature"
    bl_description = "Set the currently selected armature as the sync source"

    def execute(self, context):
        obj = context.active_object
        if obj and obj.type == 'ARMATURE':
            context.scene.action_sync.armature_name = obj.name
            self.report({'INFO'}, f"Armature set to: {obj.name}")
        else:
            self.report({'WARNING'}, "Please select an Armature object first")
        return {'FINISHED'}


class ACTIONSYNC_OT_pick_target(Operator):
    bl_idname = "action_sync.pick_target"
    bl_label = "Add Selected as Target"
    bl_description = "Add the currently selected mesh object as a sync target"

    def execute(self, context):
        obj = context.active_object
        if obj and obj.type == 'MESH':
            settings = context.scene.action_sync
            # Avoid duplicates
            existing = [t.obj_name for t in settings.targets]
            if obj.name not in existing:
                new_target = settings.targets.add()
                new_target.obj_name = obj.name
                settings.active_target_index = len(settings.targets) - 1
                self.report({'INFO'}, f"Added target: {obj.name}")
            else:
                self.report({'WARNING'}, f"{obj.name} is already in the list")
        else:
            self.report({'WARNING'}, "Please select a Mesh object first")
        return {'FINISHED'}


class ACTIONSYNC_OT_sync_now(Operator):
    bl_idname = "action_sync.sync_now"
    bl_label = "Sync Now"
    bl_description = "Manually trigger a sync of the current armature action to all targets"

    def execute(self, context):
        result = do_sync(context.scene, force=True)
        if result:
            self.report({'INFO'}, f"Synced to: {result}")
        else:
            self.report({'WARNING'}, "Nothing to sync – check your settings")
        return {'FINISHED'}


# ─────────────────────────────────────────────
#  UI Panel
# ─────────────────────────────────────────────

class ACTIONSYNC_PT_panel(Panel):
    bl_label = "Action Sync"
    bl_idname = "ACTIONSYNC_PT_panel"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        settings = context.scene.action_sync
        self.layout.prop(settings, "enabled", text="")

    def draw(self, context):
        layout = self.layout
        settings = context.scene.action_sync

        layout.enabled = settings.enabled

        # ── Armature source ──
        box = layout.box()
        box.label(text="Source Armature", icon='ARMATURE_DATA')
        row = box.row(align=True)
        row.prop_search(settings, "armature_name", bpy.data, "objects", text="")
        row.operator("action_sync.pick_armature", text="", icon='EYEDROPPER')

        # Show current action
        armature = bpy.data.objects.get(settings.armature_name)
        if armature and armature.animation_data and armature.animation_data.action:
            box.label(text=f"Active Action: {armature.animation_data.action.name}", icon='ACTION')
        elif armature:
            box.label(text="No active action", icon='ERROR')

        layout.separator()

        # ── Target objects ──
        box = layout.box()
        box.label(text="Target Objects", icon='MESH_DATA')

        row = box.row()
        row.operator("action_sync.pick_target", text="Add Selected", icon='ADD')
        row.operator("action_sync.remove_target", text="Remove", icon='REMOVE')

        for i, target in enumerate(settings.targets):
            row = box.row(align=True)
            icon = 'OBJECT_DATA'
            obj = bpy.data.objects.get(target.obj_name)
            if obj:
                icon = 'MESH_DATA' if obj.type == 'MESH' else 'OBJECT_DATA'
            row.prop_search(target, "obj_name", bpy.data, "objects", text="")

        layout.separator()

        # ── Manual sync button ──
        layout.operator("action_sync.sync_now", icon='FILE_REFRESH')


# ─────────────────────────────────────────────
#  Core sync logic
# ─────────────────────────────────────────────

def do_sync(scene, force=False):
    global _last_action

    settings = scene.action_sync
    if not settings.enabled:
        return None

    armature = bpy.data.objects.get(settings.armature_name)
    if not armature or not armature.animation_data:
        return None

    current_action = armature.animation_data.action
    if not force and current_action == _last_action:
        return None

    _last_action = current_action
    action_name = current_action.name if current_action else "None"
    print(f"[ActionSync] Armature action changed → {action_name}")

    for target in settings.targets:
        obj = bpy.data.objects.get(target.obj_name)
        if not obj:
            print(f"[ActionSync] Object not found: {target.obj_name}")
            continue

        # Object level (transforms)
        if not obj.animation_data:
            obj.animation_data_create()
        obj.animation_data.action = current_action
        print(f"[ActionSync] {obj.name} (Object) → {action_name}")

        # Object Data level (mesh data)
        if obj.data:
            if not obj.data.animation_data:
                obj.data.animation_data_create()
            obj.data.animation_data.action = current_action
            print(f"[ActionSync] {obj.name} (Data) → {action_name}")

        # Shape Keys level
        if obj.data and hasattr(obj.data, 'shape_keys') and obj.data.shape_keys:
            sk = obj.data.shape_keys
            if not sk.animation_data:
                sk.animation_data_create()
            sk.animation_data.action = current_action
            print(f"[ActionSync] {obj.name} (ShapeKeys) → {action_name}")

    return action_name


def sync_handler(scene):
    do_sync(scene)


# ─────────────────────────────────────────────
#  Registration
# ─────────────────────────────────────────────

classes = [
    ActionSyncTarget,
    ActionSyncSettings,
    ACTIONSYNC_OT_add_target,
    ACTIONSYNC_OT_remove_target,
    ACTIONSYNC_OT_pick_armature,
    ACTIONSYNC_OT_pick_target,
    ACTIONSYNC_OT_sync_now,
    ACTIONSYNC_PT_panel,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.action_sync = bpy.props.PointerProperty(type=ActionSyncSettings)

    if sync_handler not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(sync_handler)

    print("[ActionSync] Addon registered")


def unregister():
    if sync_handler in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(sync_handler)

    del bpy.types.Scene.action_sync

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    print("[ActionSync] Addon unregistered")
