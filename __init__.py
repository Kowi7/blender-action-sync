import bpy
from bpy.props import StringProperty, CollectionProperty, BoolProperty, IntProperty
from bpy.types import PropertyGroup, Panel, Operator

# ─────────────────────────────────────────────
#  Internal state – per group last action
# ─────────────────────────────────────────────

_last_actions = {}  # group index → last action


# ─────────────────────────────────────────────
#  Property Groups
# ─────────────────────────────────────────────

class ActionSyncTarget(PropertyGroup):
    obj_name: StringProperty(name="Object", default="")


class ActionSyncGroup(PropertyGroup):
    name: StringProperty(name="Group Name", default="Sync Group")
    enabled: BoolProperty(
        name="Enabled",
        description="Enable or disable this sync group",
        default=True,
    )
    armature_name: StringProperty(
        name="Armature",
        description="Source armature for this group",
        default="",
    )
    targets: CollectionProperty(type=ActionSyncTarget)
    active_target_index: IntProperty(default=0)
    expanded: BoolProperty(default=True)


class ActionSyncSettings(PropertyGroup):
    enabled: BoolProperty(
        name="Auto Sync",
        description="Automatically sync actions across all groups",
        default=False,
    )
    groups: CollectionProperty(type=ActionSyncGroup)
    active_group_index: IntProperty(default=0)


# ─────────────────────────────────────────────
#  Operators – Groups
# ─────────────────────────────────────────────

class ACTIONSYNC_OT_add_group(Operator):
    bl_idname = "action_sync.add_group"
    bl_label = "Add Sync Group"
    bl_description = "Add a new sync group"

    def execute(self, context):
        settings = context.scene.action_sync
        group = settings.groups.add()
        group.name = f"Sync Group {len(settings.groups)}"
        settings.active_group_index = len(settings.groups) - 1
        return {'FINISHED'}


class ACTIONSYNC_OT_remove_group(Operator):
    bl_idname = "action_sync.remove_group"
    bl_label = "Remove Sync Group"
    bl_description = "Remove this sync group"

    group_index: IntProperty()

    def execute(self, context):
        settings = context.scene.action_sync
        idx = self.group_index
        if 0 <= idx < len(settings.groups):
            settings.groups.remove(idx)
            settings.active_group_index = max(0, idx - 1)
            if idx in _last_actions:
                del _last_actions[idx]
        return {'FINISHED'}


# ─────────────────────────────────────────────
#  Operators – Armature
# ─────────────────────────────────────────────

class ACTIONSYNC_OT_pick_armature(Operator):
    bl_idname = "action_sync.pick_armature"
    bl_label = "Use Selected as Armature"
    bl_description = "Set the currently selected armature as the source for this group"

    group_index: IntProperty()

    def execute(self, context):
        obj = context.active_object
        if obj and obj.type == 'ARMATURE':
            context.scene.action_sync.groups[self.group_index].armature_name = obj.name
            self.report({'INFO'}, f"Armature set to: {obj.name}")
        else:
            self.report({'WARNING'}, "Please select an Armature object first")
        return {'FINISHED'}


# ─────────────────────────────────────────────
#  Operators – Targets
# ─────────────────────────────────────────────

class ACTIONSYNC_OT_pick_target(Operator):
    bl_idname = "action_sync.pick_target"
    bl_label = "Add Selected as Target"
    bl_description = "Add the currently selected mesh as a sync target"

    group_index: IntProperty()

    def execute(self, context):
        obj = context.active_object
        if obj and obj.type == 'MESH':
            group = context.scene.action_sync.groups[self.group_index]
            existing = [t.obj_name for t in group.targets]
            if obj.name not in existing:
                new_target = group.targets.add()
                new_target.obj_name = obj.name
                group.active_target_index = len(group.targets) - 1
                self.report({'INFO'}, f"Added target: {obj.name}")
            else:
                self.report({'WARNING'}, f"{obj.name} is already in this group")
        else:
            self.report({'WARNING'}, "Please select a Mesh object first")
        return {'FINISHED'}


class ACTIONSYNC_OT_remove_target(Operator):
    bl_idname = "action_sync.remove_target"
    bl_label = "Remove Target"
    bl_description = "Remove this target from the group"

    group_index: IntProperty()
    target_index: IntProperty()

    def execute(self, context):
        group = context.scene.action_sync.groups[self.group_index]
        idx = self.target_index
        if 0 <= idx < len(group.targets):
            group.targets.remove(idx)
            group.active_target_index = max(0, idx - 1)
        return {'FINISHED'}


# ─────────────────────────────────────────────
#  Operators – Manual sync
# ─────────────────────────────────────────────

class ACTIONSYNC_OT_sync_now(Operator):
    bl_idname = "action_sync.sync_now"
    bl_label = "Sync All Now"
    bl_description = "Manually trigger a sync for all enabled groups"

    def execute(self, context):
        count = do_sync_all(context.scene, force=True)
        self.report({'INFO'}, f"Synced {count} group(s)")
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
        self.layout.prop(context.scene.action_sync, "enabled", text="")

    def draw(self, context):
        layout = self.layout
        settings = context.scene.action_sync

        layout.enabled = settings.enabled

        row = layout.row()
        row.operator("action_sync.add_group", icon='ADD', text="Add Sync Group")
        row.operator("action_sync.sync_now", icon='FILE_REFRESH', text="Sync All")

        layout.separator()

        for g_idx, group in enumerate(settings.groups):
            box = layout.box()

            # ── Group header ──
            header = box.row(align=True)
            header.prop(group, "expanded", text="",
                        icon='TRIA_DOWN' if group.expanded else 'TRIA_RIGHT',
                        emboss=False)
            header.prop(group, "name", text="")
            header.prop(group, "enabled", text="")
            rm_group = header.operator("action_sync.remove_group", text="", icon='X')
            rm_group.group_index = g_idx

            if not group.expanded:
                continue

            col = box.column()
            col.enabled = group.enabled

            # ── Armature ──
            arm_box = col.box()
            arm_box.label(text="Source Armature", icon='ARMATURE_DATA')
            arm_row = arm_box.row(align=True)
            arm_row.prop_search(group, "armature_name", bpy.data, "objects", text="")
            pick_arm = arm_row.operator("action_sync.pick_armature", text="", icon='EYEDROPPER')
            pick_arm.group_index = g_idx

            armature = bpy.data.objects.get(group.armature_name)
            if armature and armature.animation_data and armature.animation_data.action:
                arm_box.label(text=f"Active: {armature.animation_data.action.name}", icon='ACTION')
            elif armature:
                arm_box.label(text="No active action", icon='ERROR')

            col.separator()

            # ── Targets ──
            tgt_box = col.box()
            tgt_box.label(text="Target Objects", icon='MESH_DATA')
            pick_tgt = tgt_box.operator("action_sync.pick_target", text="Add Selected", icon='ADD')
            pick_tgt.group_index = g_idx

            for t_idx, target in enumerate(group.targets):
                t_row = tgt_box.row(align=True)
                t_row.prop_search(target, "obj_name", bpy.data, "objects", text="")
                rm_tgt = t_row.operator("action_sync.remove_target", text="", icon='X')
                rm_tgt.group_index = g_idx
                rm_tgt.target_index = t_idx


# ─────────────────────────────────────────────
#  Core sync logic
# ─────────────────────────────────────────────

def sync_group(group, g_idx, force=False):
    armature = bpy.data.objects.get(group.armature_name)
    if not armature or not armature.animation_data:
        return False

    current_action = armature.animation_data.action
    if not force and current_action == _last_actions.get(g_idx):
        return False

    _last_actions[g_idx] = current_action
    action_name = current_action.name if current_action else "None"
    print(f"[ActionSync] Group '{group.name}' → {action_name}")

    for target in group.targets:
        obj = bpy.data.objects.get(target.obj_name)
        if not obj:
            print(f"[ActionSync]   Not found: {target.obj_name}")
            continue

        # Object level
        if not obj.animation_data:
            obj.animation_data_create()
        obj.animation_data.action = current_action

        # Object Data level
        if obj.data:
            if not obj.data.animation_data:
                obj.data.animation_data_create()
            obj.data.animation_data.action = current_action

        # Shape Keys level
        if obj.data and hasattr(obj.data, 'shape_keys') and obj.data.shape_keys:
            sk = obj.data.shape_keys
            if not sk.animation_data:
                sk.animation_data_create()
            sk.animation_data.action = current_action

        print(f"[ActionSync]   {obj.name} → {action_name}")

    return True


def do_sync_all(scene, force=False):
    settings = scene.action_sync
    if not settings.enabled:
        return 0
    count = 0
    for g_idx, group in enumerate(settings.groups):
        if group.enabled:
            if sync_group(group, g_idx, force=force):
                count += 1
    return count


def sync_handler(scene):
    do_sync_all(scene)


# ─────────────────────────────────────────────
#  Registration
# ─────────────────────────────────────────────

classes = [
    ActionSyncTarget,
    ActionSyncGroup,
    ActionSyncSettings,
    ACTIONSYNC_OT_add_group,
    ACTIONSYNC_OT_remove_group,
    ACTIONSYNC_OT_pick_armature,
    ACTIONSYNC_OT_pick_target,
    ACTIONSYNC_OT_remove_target,
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
