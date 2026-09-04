bl_info = {
    "name": "EaseIt",
    "author": "Andy Cuccaro",
    "version": (2, 0, 3),
    "blender": (2, 80, 0),
    "location": "Graph Editor > Sidebar > Easing",
    "description": "Apply easing presets to selected keyframes",
    "category": "Animation",
}

import bpy
import bmesh
from mathutils import Vector
import os
import json
import uuid
import bpy.utils.previews
from bpy_extras import anim_utils

preview_collections = {}

def get_blender_version():
    """Returns Blender version as a tuple (major, minor, patch)"""
    return bpy.app.version

def is_blender_5_or_newer():
    """Check if running Blender 5.0 or newer"""
    return get_blender_version() >= (5, 0, 0)

def get_fcurves_from_animation_data(anim_data):
    """
    Get fcurves from animation data, compatible with both old and new API.
    """
    if not anim_data or not anim_data.action:
        return []
    
    action = anim_data.action
    fcurves = []
    
    if is_blender_5_or_newer():
        # Blender 5.0+: Must use channelbag API
        # Get the active slot
        action_slot = anim_data.action_slot
        if not action_slot:
            return []
        
        # Use the helper function from bpy_extras.anim_utils
        channelbag = anim_utils.action_get_channelbag_for_slot(action, action_slot)
        if channelbag:
            fcurves.extend(channelbag.fcurves)
    else:
        # Blender 4.4 and older: use legacy API
        if hasattr(action, 'fcurves'):
            fcurves.extend(action.fcurves)
    
    return fcurves

# Helper – returns True if the Graph Editor has any selectable animation data
def graph_has_anim_data(context):
    # The built‑in poll logic is roughly:
    #   - area.type == 'GRAPH_EDITOR'
    #   - space_data has a valid fcurve or keyframe selected
    # We can reuse the same test that the operator uses:
    return context.area.type == 'GRAPH_EDITOR' and (
        getattr(context, "selected_visible_fcurves", None) or
        getattr(context, "active_editable_fcurve", None)
    )

def get_single_target_fcurve(context):
    """
    Returns the one F-Curve a "Save as custom preset" action should
    capture from: the active editable F-Curve if there is one, otherwise
    (fallback) the single F-Curve that actually has a keyframe selected
    among the selected/visible ones. This covers the common case of a
    Box Select in the Graph Editor, which selects keyframes across
    curves without making any of them "active". If more than one curve
    has a selection, there's no way to know which one the user means,
    so this returns None (keeping the Save button disabled) rather than
    guessing.
    """
    fcurve = getattr(context, "active_editable_fcurve", None)
    if fcurve is not None:
        return fcurve

    fcurves = getattr(context, "selected_visible_fcurves", None) or []
    candidates = [
        fc for fc in fcurves
        if any(kf.select_control_point for kf in fc.keyframe_points)
    ]
    if len(candidates) == 1:
        return candidates[0]
    return None

# Handle types that Blender recalculates automatically instead of respecting
# a position we set by hand. Copying a "type" from one of these onto a handle
# whose position we carefully computed from spatial_data would let Blender
# silently move it, so we never copy these — see is_cotangent usage below.
AUTO_RECALC_HANDLE_TYPES = {'AUTO', 'AUTO_CLAMPED', 'VECTOR'}

def is_cotangent(keyframe, tolerance=0.001):

    """
    Returns True if a keyframe's left and right handles lie on the same
    straight line through the keyframe (i.e. the curve has no visual "kink"
    at this point).
    """
    left_vec = keyframe.handle_left - keyframe.co
    right_vec = keyframe.handle_right - keyframe.co

    # 2D cross product: ~0 means the two vectors are parallel (same line)
    cross = left_vec.x * right_vec.y - left_vec.y * right_vec.x
    # Dot product: negative means they point in opposite directions
    # (positive would mean one handle is overlapping/collapsed onto the other)
    dot = left_vec.x * right_vec.x + left_vec.y * right_vec.y

    return abs(cross) < tolerance and dot < 0

def load_icons():
    pcoll = bpy.utils.previews.new()

    # Path to THIS file ( __init__.py )
    addon_dir = os.path.dirname(__file__)

    # Path to icons folder (relative)
    icons_dir = os.path.join(addon_dir, "icons")

    pcoll.load(
        "DEFAULT",
        os.path.join(icons_dir, "01_icon.png"),
        'IMAGE'
    )
    pcoll.load(
        "JUST_FINE",
        os.path.join(icons_dir, "02_icon.png"),
        'IMAGE'
    )
    pcoll.load(
        "CUBIC",
        os.path.join(icons_dir, "03_icon.png"),
        'IMAGE'
    )
    pcoll.load(
        "EXPONENTIAL",
        os.path.join(icons_dir, "04_icon.png"),
        'IMAGE'
    )
    pcoll.load(
        "EXTREME",
        os.path.join(icons_dir, "05_icon.png"),
        'IMAGE'
    )
    pcoll.load(
        "LINEAR",
        os.path.join(icons_dir, "06_icon.png"),
        'IMAGE'
    )
    pcoll.load(
        "MAX",
        os.path.join(icons_dir, "07_icon.png"),
        'IMAGE'
    )
    pcoll.load(
        "SMOOTH",
        os.path.join(icons_dir, "08_icon.png"),
        'IMAGE'
    )
    pcoll.load(
        "EASY",
        os.path.join(icons_dir, "09_icon.png"),
        'IMAGE'
    )
    pcoll.load(
        "SUPER_SMOOTH",
        os.path.join(icons_dir, "10_icon.png"),
        'IMAGE'
    )
    pcoll.load(
        "SMOOTH_OUT",
        os.path.join(icons_dir, "11_icon.png"),
        'IMAGE'
    )
    pcoll.load(
        "EASY_OUT",
        os.path.join(icons_dir, "12_icon.png"),
        'IMAGE'
    )
    pcoll.load(
        "SUPER_SMOOTH_OUT",
        os.path.join(icons_dir, "13_icon.png"),
        'IMAGE'
    )
    pcoll.load(
        "EASY_IN",
        os.path.join(icons_dir, "14_icon.png"),
        'IMAGE'
    )
    pcoll.load(
        "EASE_OUT",
        os.path.join(icons_dir, "15_icon.png"),
        'IMAGE'
    )
    pcoll.load(
        "EXPLOSIVE",
        os.path.join(icons_dir, "16_icon.png"),
        'IMAGE'
    )
    pcoll.load(
        "SPRINGY",
        os.path.join(icons_dir, "17_icon.png"),
        'IMAGE'
    )
    pcoll.load(
        "OVERSHOOT_01",
        os.path.join(icons_dir, "18_icon.png"),
        'IMAGE'
    )
    pcoll.load(
        "OVERSHOOT_02",
        os.path.join(icons_dir, "19_icon.png"),
        'IMAGE'
    )
    pcoll.load(
        "ANTICIPATION_01",
        os.path.join(icons_dir, "20_icon.png"),
        'IMAGE'
    )
    pcoll.load(
        "ANTICIPATION_02",
        os.path.join(icons_dir, "21_icon.png"),
        'IMAGE'
    )
    pcoll.load(
        "ANTICIPATION_03",
        os.path.join(icons_dir, "22_icon.png"),
        'IMAGE'
    )
    pcoll.load(
        "EASY_GOING",
        os.path.join(icons_dir, "23_icon.png"),
        'IMAGE'
    )
    pcoll.load(
        "ANTICIPATION_OVERSHOOT",
        os.path.join(icons_dir, "24_icon.png"),
        'IMAGE'
    )
    pcoll.load(
        "AGITATED",
        os.path.join(icons_dir, "25_icon.png"),
        'IMAGE'
    )
    pcoll.load(
        "VERY_LATE_STOP",
        os.path.join(icons_dir, "26_icon.png"),
        'IMAGE'
    )
    pcoll.load(
        "OVERSHOOT_X3",
        os.path.join(icons_dir, "27_icon.png"),
        'IMAGE'
    )
    pcoll.load(
        "SPRING_BACK",
        os.path.join(icons_dir, "28_icon.png"),
        'IMAGE'
    )
    pcoll.load(
        "BOUNCY",
        os.path.join(icons_dir, "29_icon.png"),
        'IMAGE'
    )
    pcoll.load(
        "WEIRD",
        os.path.join(icons_dir, "30_icon.png"),
        'IMAGE'
    )

    preview_collections["main"] = pcoll
    
def unload_icons():
    for pcoll in preview_collections.values():
        bpy.utils.previews.remove(pcoll)
    preview_collections.clear()

# ============================================================================
# CUSTOM PRESETS: STORAGE
# ============================================================================
# Each custom preset is stored as its own JSON file, named by an internal
# UUID (not by the display name), under Blender's standard user presets
# folder — the same conceptual location Blender's own preset system uses.
# Using a UUID as the filename means renaming a preset never involves
# renaming a file on disk: we just rewrite the "name" field inside it.

CUSTOM_PRESETS_SUBDIR = os.path.join("presets", "easeit")

# In-memory cache, refreshed at register() and after any add/delete/rename.
# Keeping a cache (instead of re-reading disk on every panel redraw) avoids
# hitting the filesystem on every UI refresh, which can happen very often.
custom_presets_cache = {"simple": [], "advanced": []}

def get_custom_presets_dir():
    path = bpy.utils.user_resource('SCRIPTS', path=CUSTOM_PRESETS_SUBDIR, create=True)
    return path

def reload_custom_presets_cache():
    """Scan the presets folder and rebuild the in-memory cache."""
    custom_presets_cache["simple"] = []
    custom_presets_cache["advanced"] = []

    presets_dir = get_custom_presets_dir()
    if not os.path.isdir(presets_dir):
        return

    for filename in os.listdir(presets_dir):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(presets_dir, filename)
        try:
            with open(filepath, 'r') as f:
                preset = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"[Easeit] Error loading custom preset '{filename}': {e}")
            continue

        preset_type = preset.get("type")
        if preset_type not in ("simple", "advanced"):
            continue
        if "id" not in preset or "name" not in preset or "data" not in preset:
            continue

        custom_presets_cache[preset_type].append(preset)

    # Keep a stable, predictable order in the UI
    custom_presets_cache["simple"].sort(key=lambda p: p["name"].lower())
    custom_presets_cache["advanced"].sort(key=lambda p: p["name"].lower())

def get_custom_preset(preset_type, preset_id):
    for preset in custom_presets_cache.get(preset_type, []):
        if preset["id"] == preset_id:
            return preset
    return None

def get_unique_preset_name(base_name, preset_type, exclude_id=None):
    """
    Returns base_name unchanged if it's free; otherwise appends " (2)",
    " (3)", etc. until a free name is found. exclude_id lets a rename
    ignore the preset's own current name (renaming to itself is a no-op,
    not a collision).
    """
    existing_names = {
        p["name"] for p in custom_presets_cache.get(preset_type, [])
        if p["id"] != exclude_id
    }
    if base_name not in existing_names:
        return base_name

    suffix = 2
    while f"{base_name} ({suffix})" in existing_names:
        suffix += 1
    return f"{base_name} ({suffix})"

def save_new_custom_preset(preset_type, name, data):
    """Writes a new custom preset to disk and refreshes the cache."""
    preset_id = uuid.uuid4().hex
    final_name = get_unique_preset_name(name, preset_type)

    preset = {
        "id": preset_id,
        "type": preset_type,
        "name": final_name,
        "data": data,
    }

    filepath = os.path.join(get_custom_presets_dir(), f"{preset_id}.json")
    try:
        with open(filepath, 'w') as f:
            json.dump(preset, f, indent=2)
    except IOError as e:
        print(f"[Easeit] Error saving custom preset: {e}")
        return None

    reload_custom_presets_cache()
    return final_name

def rename_custom_preset(preset_type, preset_id, new_name):
    preset = get_custom_preset(preset_type, preset_id)
    if preset is None:
        return None

    final_name = get_unique_preset_name(new_name, preset_type, exclude_id=preset_id)
    preset["name"] = final_name

    filepath = os.path.join(get_custom_presets_dir(), f"{preset_id}.json")
    try:
        with open(filepath, 'w') as f:
            json.dump(preset, f, indent=2)
    except IOError as e:
        print(f"[Easeit] Error renaming custom preset: {e}")
        return None

    reload_custom_presets_cache()
    return final_name

def delete_custom_preset(preset_type, preset_id):
    filepath = os.path.join(get_custom_presets_dir(), f"{preset_id}.json")
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
    except IOError as e:
        print(f"[Easeit] Error deleting custom preset: {e}")
        return False

    reload_custom_presets_cache()
    return True

# ============================================================================
# CUSTOM PRESETS: CAPTURE / APPLY DATA MODEL
# ============================================================================

def extract_simple_preset_data(kf1, kf2):
    """
    Captures the exact handle configuration of two keyframes (kf1 followed
    by kf2) as a Simple custom preset. Unlike the built-in Simple presets
    (which only store a single horizontal-length ratio, always flat),
    this stores the handle's full normalized position — including any
    vertical/slope component — plus the original handle type, so applying
    it later reproduces the captured shape exactly, not just its timing.
    """
    x_span = kf2.co.x - kf1.co.x
    y_span = kf2.co.y - kf1.co.y

    if abs(x_span) < 0.001:
        return None

    kf1_handle_right_x = (kf1.handle_right.x - kf1.co.x) / x_span
    kf1_handle_right_y = (kf1.handle_right.y - kf1.co.y) / y_span if y_span != 0 else 0

    kf2_handle_left_x = (kf2.handle_left.x - kf2.co.x) / x_span
    kf2_handle_left_y = (kf2.handle_left.y - kf2.co.y) / y_span if y_span != 0 else 0

    return {
        "kf1_handle_right_type": kf1.handle_right_type,
        "kf2_handle_left_type": kf2.handle_left_type,
        "kf1_handle_right": [kf1_handle_right_x, kf1_handle_right_y],
        "kf2_handle_left": [kf2_handle_left_x, kf2_handle_left_y],
    }

def apply_simple_preset_data(kf1, kf2, preset_data):
    """Applies a captured Simple custom preset to a pair of keyframes."""
    x_span = kf2.co.x - kf1.co.x
    y_span = kf2.co.y - kf1.co.y

    kf1.handle_right_type = preset_data["kf1_handle_right_type"]
    kf2.handle_left_type = preset_data["kf2_handle_left_type"]

    kf1_x, kf1_y = preset_data["kf1_handle_right"]
    kf2_x, kf2_y = preset_data["kf2_handle_left"]

    kf1.handle_right = (kf1.co.x + kf1_x * x_span, kf1.co.y + kf1_y * y_span)
    kf2.handle_left = (kf2.co.x + kf2_x * x_span, kf2.co.y + kf2_y * y_span)

def extract_advanced_preset_data(keyframes):
    """
    Captures 3+ selected keyframes as an Advanced custom preset, in the
    same spatial_data format used by the built-in Advanced presets
    (6 values per point — see GRAPH_OT_apply_advanced_easing_base). This
    inverts the exact same formulas that base class uses to apply a
    preset, so a captured preset re-applies consistently.
    """
    if len(keyframes) < 3:
        return None

    sorted_kfs = sorted(keyframes, key=lambda kf: kf.co.x)
    first_kf = sorted_kfs[0]
    last_kf = sorted_kfs[-1]

    frame_distance = last_kf.co.x - first_kf.co.x
    value_distance = last_kf.co.y - first_kf.co.y

    if abs(frame_distance) < 0.001:
        return None

    spatial_data = []
    for i, kf in enumerate(sorted_kfs):
        x_pos = (kf.co.x - first_kf.co.x) / frame_distance
        y_pos = (kf.co.y - first_kf.co.y) / value_distance if value_distance != 0 else 0

        # Same left/right distance fallback logic as the apply formula
        if i > 0:
            left_distance = kf.co.x - sorted_kfs[i - 1].co.x
        else:
            left_distance = (sorted_kfs[i + 1].co.x - kf.co.x) if len(sorted_kfs) > 1 else frame_distance

        if i < len(sorted_kfs) - 1:
            right_distance = sorted_kfs[i + 1].co.x - kf.co.x
        else:
            right_distance = (kf.co.x - sorted_kfs[i - 1].co.x) if i > 0 else frame_distance

        handle_left_offset_x = kf.co.x - kf.handle_left.x
        handle_left_offset_y = kf.co.y - kf.handle_left.y
        handle_right_offset_x = kf.handle_right.x - kf.co.x
        handle_right_offset_y = kf.handle_right.y - kf.co.y

        ease_left_x = (handle_left_offset_x / left_distance * 100.0) if left_distance != 0 else 0
        ease_right_x = (handle_right_offset_x / right_distance * 100.0) if right_distance != 0 else 0

        if handle_left_offset_x != 0 and value_distance != 0:
            slope_left = (handle_left_offset_y / handle_left_offset_x) * (frame_distance / value_distance)
        else:
            slope_left = 0

        if handle_right_offset_x != 0 and value_distance != 0:
            slope_right = (handle_right_offset_y / handle_right_offset_x) * (frame_distance / value_distance)
        else:
            slope_right = 0

        spatial_data.append([x_pos, y_pos, slope_left, ease_left_x, slope_right, ease_right_x])

    return spatial_data

# Base class for all easing presets
class GRAPH_OT_apply_easing_base(bpy.types.Operator):
    """Base class for easing preset operators"""
    bl_idname = "graph.apply_easing_base"
    bl_label = "Apply Easing Base"
    bl_options = {'REGISTER', 'UNDO'}
    
    # Override these in subclasses
    ease_in_ratio = 0.33
    ease_out_ratio = 0.33
    preset_name = "Default"

    def execute(self, context):
        """
        Main execution routine for the easing operator.
        """

        # Abort if the Graph Editor has no selected keyframes/f‑curves
        # The Graph Editor exposes these attributes only when something is
        # selected there. If both are empty we treat the situation as “nothing
        # selected” and return a warning.
        has_graph_selection = (
            getattr(context, "selected_visible_fcurves", None) or
            getattr(context, "active_editable_fcurve", None)
        )
        if not has_graph_selection:
            self.report({'WARNING'}, "Select at least 2 keyframes in the Graph Editor")
            return {'CANCELLED'}

        # Continue with the existing logic (still able to pull f‑curves
        # from the Dope Sheet for the selected keyframes)
        fcurves = []

        # Try to get fcurves from Graph Editor context first
        if hasattr(context, 'selected_visible_fcurves') and context.selected_visible_fcurves:
            fcurves = context.selected_visible_fcurves
        elif hasattr(context, 'active_editable_fcurve') and context.active_editable_fcurve:
            fcurves = [context.active_editable_fcurve]
        else:
            # Fallback for Dope Sheet and other editors
            if context.selected_objects:
                for obj in context.selected_objects:
                    fcurves.extend(get_fcurves_from_animation_data(obj.animation_data))

            # Also try to get from scene animation data
            fcurves.extend(get_fcurves_from_animation_data(context.scene.animation_data))

        if not fcurves:
            self.report({'ERROR'}, "No F‑Curves found")
            return {'CANCELLED'}
        
        processed_curves = 0
        total_keyframes_processed = 0
        
        # Process each fcurve
        for fcurve in fcurves:
            # Get selected keyframes for this curve
            selected_keyframes = []
            for i, keyframe in enumerate(fcurve.keyframe_points):
                if keyframe.select_control_point:
                    selected_keyframes.append((i, keyframe))
            
            # Skip curves that don't have at least 2 selected keyframes
            if len(selected_keyframes) < 2:
                continue
            
            # Sort keyframes by frame position
            selected_keyframes.sort(key=lambda x: x[1].co.x)
            
            # Store original interpolation types and handle types for all selected keyframes
            original_data = {}
            for idx, kf in selected_keyframes:
                original_data[idx] = {
                    'interpolation': kf.interpolation,
                    'handle_left_type': kf.handle_left_type,
                    'handle_right_type': kf.handle_right_type,
                    'handle_left_pos': kf.handle_left.copy(),
                    'handle_right_pos': kf.handle_right.copy()
                }
            
            # Step 1: Set all handles to FREE
            for idx, kf in selected_keyframes:
                kf.handle_left_type = 'FREE'
                kf.handle_right_type = 'FREE'
            
            # Step 2: Convert all selected keyframes to BEZIER
            for idx, kf in selected_keyframes:
                kf.interpolation = 'BEZIER'
            
            # Apply easing between each consecutive pair of selected keyframes
            for i in range(len(selected_keyframes) - 1):
                kf1_idx, kf1 = selected_keyframes[i]
                kf2_idx, kf2 = selected_keyframes[i + 1]
                
                # Calculate frame distance for this pair
                frame_distance = kf2.co.x - kf1.co.x
                
                # Skip if keyframes are too close
                if frame_distance < 0.001:
                    continue
                
                # Calculate handle extensions using the preset ratios
                handle_extension_in = frame_distance * self.ease_in_ratio
                handle_extension_out = frame_distance * self.ease_out_ratio
                
                # Identify outer handles that should be preserved
                is_first_keyframe = (i == 0)
                is_last_keyframe = (i == len(selected_keyframes) - 2)
                
                # Step 3: Apply easing - set inner handles to ALIGNED
                # Apply to first keyframe (ease out) - always set right handle
                kf1.handle_right_type = 'ALIGNED'
                kf1.handle_right = (kf1.co.x + handle_extension_out, kf1.co.y)
                
                # Apply to second keyframe (ease in) - always set left handle
                kf2.handle_left_type = 'ALIGNED'
                kf2.handle_left = (kf2.co.x - handle_extension_in, kf2.co.y)
                
                # Step 4: Restore outer handle types to original.
                # VECTOR/AUTO/AUTO_CLAMPED recompute their own position from
                # whatever curve structure exists NOW (which isn't the
                # original one anymore), so restoring that exact type would
                # silently ignore the position we captured and produce a
                # wrong direction. For those, we restore as FREE instead —
                # same visual position, just a type Blender won't override.
                if is_first_keyframe:
                    outer_type = original_data[kf1_idx]['handle_left_type']
                    kf1.handle_left_type = 'FREE' if outer_type in AUTO_RECALC_HANDLE_TYPES else outer_type
                    kf1.handle_left = original_data[kf1_idx]['handle_left_pos']
                
                if is_last_keyframe:
                    outer_type = original_data[kf2_idx]['handle_right_type']
                    kf2.handle_right_type = 'FREE' if outer_type in AUTO_RECALC_HANDLE_TYPES else outer_type
                    kf2.handle_right = original_data[kf2_idx]['handle_right_pos']
            
            # Step 5: Restore interpolation type of the last selected keyframe
            last_kf_idx, last_kf = selected_keyframes[-1]
            last_kf.interpolation = original_data[last_kf_idx]['interpolation']
            
            # Update the fcurve
            fcurve.update()
            
            processed_curves += 1
            total_keyframes_processed += len(selected_keyframes)
        
        # Refresh the Graph Editor
        context.area.tag_redraw()
        
        if processed_curves == 0:
            self.report({'WARNING'}, "No curves with at least 2 selected keyframes found")
            return {'CANCELLED'}
        
        self.report({'INFO'}, f"Applied {self.preset_name} easing to {processed_curves} curve(s), {total_keyframes_processed} keyframes processed")
        return {'FINISHED'}

# Advanced base class for complex presets with intermediate keyframes
class GRAPH_OT_apply_advanced_easing_base(bpy.types.Operator):
    """Base class for advanced easing preset operators with intermediate keyframes"""
    bl_idname = "graph.apply_advanced_easing_base"
    bl_label = "Apply Advanced Easing Base"
    bl_options = {'REGISTER', 'UNDO'}
    
    # Override these in subclasses - spatial data format:
    # [x_pos, y_pos, slope_left, ease_left_x, slope_right, ease_right_x]
    spatial_data = []
    preset_name = "Advanced Default"

    def execute(self, context):
        """
        Main execution routine for the easing operator.
        """

        # Abort if the Graph Editor has no selected keyframes/f‑curves
        # The Graph Editor exposes these attributes only when something is
        # selected there. If both are empty we treat the situation as “nothing
        # selected” and return a warning.
        has_graph_selection = (
            getattr(context, "selected_visible_fcurves", None) or
            getattr(context, "active_editable_fcurve", None)
        )
        if not has_graph_selection:
            self.report({'WARNING'}, "Select at least 2 keyframes in the Graph Editor")
            return {'CANCELLED'}

        # Continue with the existing logic (still able to pull f‑curves
        # from the Dope Sheet for the selected keyframes)
        fcurves = []

        # Try to get fcurves from Graph Editor context first
        if hasattr(context, 'selected_visible_fcurves') and context.selected_visible_fcurves:
            fcurves = context.selected_visible_fcurves
        elif hasattr(context, 'active_editable_fcurve') and context.active_editable_fcurve:
            fcurves = [context.active_editable_fcurve]
        else:
            # Fallback for Dope Sheet and other editors
            if context.selected_objects:
                for obj in context.selected_objects:
                    fcurves.extend(get_fcurves_from_animation_data(obj.animation_data))

            # Also try to get from scene animation data
            fcurves.extend(get_fcurves_from_animation_data(context.scene.animation_data))

        if not fcurves:
            self.report({'ERROR'}, "No F‑Curves found")
            return {'CANCELLED'}
        
        processed_curves = 0
        total_keyframes_processed = 0
        
        # Process each fcurve
        for fcurve in fcurves:
            # Get selected keyframes for this curve
            selected_keyframes = []
            for i, keyframe in enumerate(fcurve.keyframe_points):
                if keyframe.select_control_point:
                    selected_keyframes.append((i, keyframe))
            
            # Skip curves that don't have at least 2 selected keyframes
            if len(selected_keyframes) < 2:
                continue

            # Sort keyframes by frame position
            selected_keyframes.sort(key=lambda x: x[1].co.x)
            
            # Store the interpolation type of the last selected keyframe
            # This will be restored to preserve animation after the selection
            last_kf_original_interpolation = selected_keyframes[-1][1].interpolation
            
            # Get the first and last selected keyframes
            first_kf = selected_keyframes[0][1]
            last_kf = selected_keyframes[-1][1]

            # Find the real neighbors OUTSIDE the selection (A before first_kf,
            # D after last_kf) and capture their relevant handle — A's right
            # handle, D's left handle — before touching anything. Blender's
            # insert() recalculates the whole curve as a side effect, which
            # can shrink these neighbors' handle length even when their type
            # is FREE (confirmed via debugging). We restore them afterward,
            # the same way we already restore the selection's own outer
            # handles below.
            neighbor_prev_kf = None
            neighbor_next_kf = None
            for kf_scan in fcurve.keyframe_points:
                if kf_scan.co.x < first_kf.co.x:
                    if neighbor_prev_kf is None or kf_scan.co.x > neighbor_prev_kf.co.x:
                        neighbor_prev_kf = kf_scan
                if kf_scan.co.x > last_kf.co.x:
                    if neighbor_next_kf is None or kf_scan.co.x < neighbor_next_kf.co.x:
                        neighbor_next_kf = kf_scan

            neighbor_prev_frame = neighbor_prev_kf.co.x if neighbor_prev_kf else None
            neighbor_next_frame = neighbor_next_kf.co.x if neighbor_next_kf else None

            neighbor_prev_handle_right_type = neighbor_prev_kf.handle_right_type if neighbor_prev_kf else None
            neighbor_prev_handle_right_pos = neighbor_prev_kf.handle_right.copy() if neighbor_prev_kf else None

            neighbor_next_handle_left_type = neighbor_next_kf.handle_left_type if neighbor_next_kf else None
            neighbor_next_handle_left_pos = neighbor_next_kf.handle_left.copy() if neighbor_next_kf else None

            # Store the OUTER handles (the ones facing away from the selection,
            # into the rest of the curve) before we delete these keyframes.
            # first_kf.handle_left  = outer handle of the first keyframe
            # last_kf.handle_right  = outer handle of the last keyframe
            first_kf_outer_type = first_kf.handle_left_type
            first_kf_outer_pos = first_kf.handle_left.copy()

            last_kf_outer_type = last_kf.handle_right_type
            last_kf_outer_pos = last_kf.handle_right.copy()
            
            # Store original keyframe values
            start_frame = first_kf.co.x
            end_frame = last_kf.co.x
            start_value = first_kf.co.y
            end_value = last_kf.co.y
            
            frame_distance = end_frame - start_frame
            value_distance = end_value - start_value
            
            # Skip if keyframes are too close
            if frame_distance < 0.001:
                continue
            
            # Clear selection on all keyframes
            for keyframe in fcurve.keyframe_points:
                keyframe.select_control_point = False
            
            # Remove all intermediate keyframes between first and last
            # We need to collect indices first, then remove in reverse order
            keyframes_to_remove = []
            for i, keyframe in enumerate(fcurve.keyframe_points):
                if start_frame < keyframe.co.x < end_frame:
                    keyframes_to_remove.append(i)
            
            # Remove intermediate keyframes in reverse order to maintain indices
            for idx in reversed(keyframes_to_remove):
                fcurve.keyframe_points.remove(fcurve.keyframe_points[idx])
            
            # Find the first and last keyframes again after removal
            first_kf_new = None
            last_kf_new = None
            first_idx = -1
            last_idx = -1
            
            for i, keyframe in enumerate(fcurve.keyframe_points):
                if abs(keyframe.co.x - start_frame) < 0.001:
                    first_kf_new = keyframe
                    first_idx = i
                elif abs(keyframe.co.x - end_frame) < 0.001:
                    last_kf_new = keyframe
                    last_idx = i
            
            # Remove the original first and last keyframes
            if last_idx > first_idx and last_idx != -1:
                fcurve.keyframe_points.remove(fcurve.keyframe_points[last_idx])
            if first_idx != -1:
                fcurve.keyframe_points.remove(fcurve.keyframe_points[first_idx])
            
            # Add all keyframes from spatial data
            created_keyframes = []
            # Snapshot of the handle type/position we WANT each point to end
            # up with, captured the instant we compute it (before any later
            # insert() in this same loop has a chance to corrupt it — see
            # CHECKPOINT 1 vs CHECKPOINT 2 in prior debugging). Re-applied
            # in a second pass once every point has been inserted.
            intended_handle_data = []
            for i, data_point in enumerate(self.spatial_data):
                x_pos, y_pos, slope_left, ease_left_x, slope_right, ease_right_x = data_point
                
                # Calculate actual frame and value positions
                actual_frame = start_frame + (x_pos * frame_distance)
                actual_value = start_value + (y_pos * value_distance)
                
                # Create keyframe
                kf = fcurve.keyframe_points.insert(actual_frame, actual_value)
                kf.interpolation = 'BEZIER'
                
                # Check if left and right slopes are the same for handle alignment
                if abs(slope_left - slope_right) < 0.001:  # Use small tolerance for floating point comparison
                    kf.handle_left_type = 'ALIGNED'
                    kf.handle_right_type = 'ALIGNED'
                else:
                    kf.handle_left_type = 'FREE'
                    kf.handle_right_type = 'FREE'
                
                # Calculate distances to adjacent keyframes
                # Left handle: distance to previous keyframe
                if i > 0:
                    prev_x_pos = self.spatial_data[i - 1][0]
                    prev_frame = start_frame + (prev_x_pos * frame_distance)
                    left_distance = actual_frame - prev_frame
                else:
                    # First keyframe: use distance to next keyframe as fallback
                    if len(self.spatial_data) > 1:
                        next_x_pos = self.spatial_data[i + 1][0]
                        next_frame = start_frame + (next_x_pos * frame_distance)
                        left_distance = next_frame - actual_frame
                    else:
                        left_distance = frame_distance
                
                # Right handle: distance to next keyframe
                if i < len(self.spatial_data) - 1:
                    next_x_pos = self.spatial_data[i + 1][0]
                    next_frame = start_frame + (next_x_pos * frame_distance)
                    right_distance = next_frame - actual_frame
                else:
                    # Last keyframe: use distance to previous keyframe as fallback
                    if i > 0:
                        prev_x_pos = self.spatial_data[i - 1][0]
                        prev_frame = start_frame + (prev_x_pos * frame_distance)
                        right_distance = actual_frame - prev_frame
                    else:
                        right_distance = frame_distance
                
                # Calculate handle positions using adjacent keyframe distances
                handle_left_x = actual_frame - (ease_left_x * left_distance / 100.0)
                handle_right_x = actual_frame + (ease_right_x * right_distance / 100.0)
                
                # Normalize slopes based on the animation's value and frame range
                # This makes slopes proportional to the curve's steepness
                if frame_distance != 0:
                    normalized_slope_left = slope_left * (value_distance / frame_distance)
                    normalized_slope_right = slope_right * (value_distance / frame_distance)
                else:
                    normalized_slope_left = 0
                    normalized_slope_right = 0

                handle_left_y = actual_value - (normalized_slope_left * (ease_left_x * left_distance / 100.0))
                handle_right_y = actual_value + (normalized_slope_right * (ease_right_x * right_distance / 100.0))

                
                # Set handle positions
                kf.handle_left = (handle_left_x, handle_left_y)
                kf.handle_right = (handle_right_x, handle_right_y)

                intended_handle_data.append((
                    kf.handle_left_type, kf.handle_left.copy(),
                    kf.handle_right_type, kf.handle_right.copy(),
                ))
                
                created_keyframes.append(kf)

            # Re-fetch fresh keyframe references by frame position.
            # WHY: every fcurve.keyframe_points.insert() call in the loop
            # above can invalidate Python references obtained from EARLIER
            # insert() calls in this same loop (Blender may reallocate the
            # underlying keyframe array on each insert). This is the exact
            # same reason first_kf_new/last_kf_new were re-found by frame
            # position after the remove() calls earlier in this function —
            # remove() has the identical invalidation effect. Without this
            # step, created_keyframes[0] (the first one inserted, and
            # therefore the one "buried under" the most subsequent inserts)
            # is often a stale reference, and edits made through it below
            # get silently lost.
            fresh_keyframes = []
            for data_point in self.spatial_data:
                target_frame = start_frame + (data_point[0] * frame_distance)
                for kf_candidate in fcurve.keyframe_points:
                    if abs(kf_candidate.co.x - target_frame) < 0.001:
                        fresh_keyframes.append(kf_candidate)
                        break
            if len(fresh_keyframes) == len(created_keyframes):
                created_keyframes = fresh_keyframes

            # Re-apply the intended handle type/position to EVERY point,
            # now that all insert() calls for this selection are finished.
            # WHY: Blender recalculates ALIGNED (and other auto-managed)
            # handles as a side effect of inserting a LATER keyframe into
            # the same curve — confirmed by debugging: a point's handle was
            # already wrong by the time the very next point got inserted,
            # even though it was correct the instant it was created. Once
            # every insert() has already happened, writing the value again
            # sticks (also confirmed by debugging) — no further insert()
            # remains to silently recalculate it out from under us.
            if len(created_keyframes) == len(intended_handle_data):
                for reapply_kf, (l_type, l_pos, r_type, r_pos) in zip(created_keyframes, intended_handle_data):
                    reapply_kf.handle_left_type = l_type
                    reapply_kf.handle_right_type = r_type
                    reapply_kf.handle_left = l_pos
                    reapply_kf.handle_right = r_pos

            # Restore the neighbors OUTSIDE the selection too (A's right
            # handle, D's left handle) — confirmed by debugging that
            # insert() shrinks these as a side effect even when FREE, and
            # confirmed that re-writing them here (after every insert() is
            # done) sticks, same as for the points above.
            if neighbor_prev_frame is not None:
                for kf_scan in fcurve.keyframe_points:
                    if abs(kf_scan.co.x - neighbor_prev_frame) < 0.001:
                        kf_scan.handle_right_type = neighbor_prev_handle_right_type
                        kf_scan.handle_right = neighbor_prev_handle_right_pos
                        break

            if neighbor_next_frame is not None:
                for kf_scan in fcurve.keyframe_points:
                    if abs(kf_scan.co.x - neighbor_next_frame) < 0.001:
                        kf_scan.handle_left_type = neighbor_next_handle_left_type
                        kf_scan.handle_left = neighbor_next_handle_left_pos
                        break

            # Select the first and last keyframes to match original selection
            if created_keyframes:
                created_keyframes[0].select_control_point = True
                created_keyframes[-1].select_control_point = True
                
            # Restore the interpolation type of the last keyframe to preserve animation after it
            created_keyframes[-1].interpolation = last_kf_original_interpolation

            if created_keyframes:
                new_first_kf = created_keyframes[0]
                new_last_kf = created_keyframes[-1]

                # Step: restore the OUTER handles (the ones facing the rest of
                # the curve, outside the selection) to what they were before
                # we deleted the original first/last keyframes. Without this,
                # the outer handle would stay at whatever value spatial_data
                # calculated for it, even though the user never asked to
                # change the curve outside the selection.
                #
                # VECTOR/AUTO/AUTO_CLAMPED recompute their own position from
                # whatever curve structure exists NOW (the just-rebuilt
                # selection, not the original neighbors), so restoring that
                # exact type would silently ignore the position we captured
                # and produce a wrong direction. For those, we restore as
                # FREE instead — same visual position, just a type Blender
                # won't override.
                first_kf_restore_type = 'FREE' if first_kf_outer_type in AUTO_RECALC_HANDLE_TYPES else first_kf_outer_type
                last_kf_restore_type = 'FREE' if last_kf_outer_type in AUTO_RECALC_HANDLE_TYPES else last_kf_outer_type

                new_first_kf.handle_left_type = first_kf_restore_type
                new_first_kf.handle_left = first_kf_outer_pos

                new_last_kf.handle_right_type = last_kf_restore_type
                new_last_kf.handle_right = last_kf_outer_pos

                # Step: if the INNER handle (facing into the selection) ended
                # up cotangent with the restored OUTER handle, copy the outer
                # handle's (now-restored) type onto the inner one.
                if is_cotangent(new_first_kf):
                    new_first_kf.handle_right_type = first_kf_restore_type

                if is_cotangent(new_last_kf):
                    new_last_kf.handle_left_type = last_kf_restore_type

            # Update the fcurve
            fcurve.update()
            
            processed_curves += 1
            total_keyframes_processed += len(created_keyframes)
        
        # Refresh the Graph Editor
        context.area.tag_redraw()
        
        if processed_curves == 0:
            self.report({'WARNING'}, "No curves with at least 2 selected keyframes found")
            return {'CANCELLED'}
        
        self.report({'INFO'}, f"Applied {self.preset_name} easing to {processed_curves} curve(s), {total_keyframes_processed} keyframes created")
        return {'FINISHED'}

# Individual preset classes (Basic presets)
class GRAPH_OT_apply_default_easing(GRAPH_OT_apply_easing_base):
    """Apply Default easing preset to selected keyframes"""
    bl_idname = "graph.apply_default_easing"
    bl_label = "Apply Default Easing"
    ease_in_ratio = 0.33
    ease_out_ratio = 0.33
    preset_name = "Default"

class GRAPH_OT_apply_just_fine_easing(GRAPH_OT_apply_easing_base):
    """Apply Just Fine easing preset to selected keyframes"""
    bl_idname = "graph.apply_just_fine_easing"
    bl_label = "Apply Just Fine Easing"
    ease_in_ratio = 0.45
    ease_out_ratio = 0.45
    preset_name = "Just Fine"

class GRAPH_OT_apply_cubic_easing(GRAPH_OT_apply_easing_base):
    """Apply Cubic easing preset to selected keyframes"""
    bl_idname = "graph.apply_cubic_easing"
    bl_label = "Apply Cubic Easing"
    ease_in_ratio = 0.65
    ease_out_ratio = 0.65
    preset_name = "Cubic"

class GRAPH_OT_apply_exponential_easing(GRAPH_OT_apply_easing_base):
    """Apply Exponential easing preset to selected keyframes"""
    bl_idname = "graph.apply_exponential_easing"
    bl_label = "Apply Exponential Easing"
    ease_in_ratio = 0.87
    ease_out_ratio = 0.87
    preset_name = "Exponential"

class GRAPH_OT_apply_extreme_easing(GRAPH_OT_apply_easing_base):
    """Apply Extreme easing preset to selected keyframes"""
    bl_idname = "graph.apply_extreme_easing"
    bl_label = "Apply Extreme Easing"
    ease_in_ratio = 0.95
    ease_out_ratio = 0.95
    preset_name = "Extreme"

class GRAPH_OT_apply_smooth_easing(GRAPH_OT_apply_easing_base):
    """Apply Smooth easing preset to selected keyframes"""
    bl_idname = "graph.apply_smooth_easing"
    bl_label = "Apply Smooth Easing"
    ease_in_ratio = 0.60
    ease_out_ratio = 0.40
    preset_name = "Smooth"

class GRAPH_OT_apply_easy_easing(GRAPH_OT_apply_easing_base):
    """Apply Easy easing preset to selected keyframes"""
    bl_idname = "graph.apply_easy_easing"
    bl_label = "Apply Easy Easing"
    ease_in_ratio = 0.90
    ease_out_ratio = 0.30
    preset_name = "Easy"

class GRAPH_OT_apply_super_smooth_easing(GRAPH_OT_apply_easing_base):
    """Apply Super Smooth easing preset to selected keyframes"""
    bl_idname = "graph.apply_super_smooth_easing"
    bl_label = "Apply Super Smooth Easing"
    ease_in_ratio = 0.95
    ease_out_ratio = 0.50
    preset_name = "Super Smooth"

class GRAPH_OT_apply_ease_in_only_easing(GRAPH_OT_apply_easing_base):
    """Apply Ease In Only easing preset to selected keyframes"""
    bl_idname = "graph.apply_ease_in_only_easing"
    bl_label = "Apply Ease In Only Easing"
    ease_in_ratio = 0.90
    ease_out_ratio = 0.001
    preset_name = "Ease In Only"

class GRAPH_OT_apply_ease_out_only_easing(GRAPH_OT_apply_easing_base):
    """Apply Ease Out Only easing preset to selected keyframes"""
    bl_idname = "graph.apply_ease_out_only_easing"
    bl_label = "Apply Ease Out Only Easing"
    ease_in_ratio = 0.001
    ease_out_ratio = 0.90
    preset_name = "Ease Out Only"

class GRAPH_OT_apply_smooth_out_easing(GRAPH_OT_apply_easing_base):
    """Apply Smooth Out easing preset to selected keyframes"""
    bl_idname = "graph.apply_smooth_out_easing"
    bl_label = "Apply Smooth Out Easing"
    ease_in_ratio = 0.40
    ease_out_ratio = 0.60
    preset_name = "Smooth Out"

class GRAPH_OT_apply_easy_out_easing(GRAPH_OT_apply_easing_base):
    """Apply Easy Out easing preset to selected keyframes"""
    bl_idname = "graph.apply_easy_out_easing"
    bl_label = "Apply Easy Out Easing"
    ease_in_ratio = 0.30
    ease_out_ratio = 0.90
    preset_name = "Easy Out"

class GRAPH_OT_apply_super_smooth_out_easing(GRAPH_OT_apply_easing_base):
    """Apply Super Smooth Out easing preset to selected keyframes"""
    bl_idname = "graph.apply_super_smooth_out_easing"
    bl_label = "Apply Super Smooth Out Easing"
    ease_in_ratio = 0.50
    ease_out_ratio = 0.95
    preset_name = "Super Smooth Out"

class GRAPH_OT_apply_linear_easing(GRAPH_OT_apply_easing_base):
    """Apply Linear easing preset to selected keyframes"""
    bl_idname = "graph.apply_linear_easing"
    bl_label = "Apply Linear Easing"
    ease_in_ratio = 0.001
    ease_out_ratio = 0.001
    preset_name = "Linear"

class GRAPH_OT_apply_max_easing(GRAPH_OT_apply_easing_base):
    """Apply Max easing preset to selected keyframes"""
    bl_idname = "graph.apply_max_easing"
    bl_label = "Apply Max Easing"
    ease_in_ratio = 1.0
    ease_out_ratio = 1.0
    preset_name = "Max"

# Advanced presets with intermediate keyframes
class GRAPH_OT_apply_explosive_easing(GRAPH_OT_apply_advanced_easing_base):
    """Apply Explosive easing preset to selected keyframes"""
    bl_idname = "graph.apply_explosive_easing"
    bl_label = "Apply Explosive Easing"
    preset_name = "Explosive"
    spatial_data = [
        [0, 0, 0, 65, 0, 0.1],
        [0.321, 1.189, 0, 81.207, 0, 19.154],
        [1, 1, 0, 65, 0, 0.1]
    ]

class GRAPH_OT_apply_overshoot1_easing(GRAPH_OT_apply_advanced_easing_base):
    """Apply Overshoot 1 easing preset to selected keyframes"""
    bl_idname = "graph.apply_overshoot1_easing"
    bl_label = "Apply Overshoot 1 Easing"
    preset_name = "Overshoot 1"
    spatial_data = [
        [0, 0, 0, 72.124, 0, 45],
        [0.412, 1.148, 0, 56.011, 0, 17.461],
        [1, 1, 0, 72.124, 0, 45]
    ]

class GRAPH_OT_apply_overshoot2_easing(GRAPH_OT_apply_advanced_easing_base):
    """Apply Overshoot 2 easing preset to selected keyframes"""
    bl_idname = "graph.apply_overshoot2_easing"
    bl_label = "Apply Overshoot 2 Easing"
    preset_name = "Overshoot 2"
    spatial_data = [
        [0, 0, 0, 57.711, 0, 89.414],
        [0.5, 1.176, 0, 50, 0, 36.321],
        [1, 1, 0, 57.711, 0, 89.414]
    ]

class GRAPH_OT_apply_easy_going_easing(GRAPH_OT_apply_advanced_easing_base):
    """Apply Easy Going easing preset to selected keyframes"""
    bl_idname = "graph.apply_easy_going_easing"
    bl_label = "Apply Easy Going Easing"
    preset_name = "Easy Going"
    spatial_data = [
        [0, 0, 0, 62.286, 0, 33],
        [0.182, -0.077, 0, 33, 0, 40],
        [0.649, 1.07, 0, 60, 0, 29.209],
        [1, 1, 0, 62.286, 0, 33]
    ]

class GRAPH_OT_apply_anticipation_overshoot_easing(GRAPH_OT_apply_advanced_easing_base):
    """Apply Anticipation + Overshoot easing preset to selected keyframes"""
    bl_idname = "graph.apply_anticipation_overshoot_easing"
    bl_label = "Apply Anticipation + Overshoot Easing"
    preset_name = "Anticipation + Overshoot"
    spatial_data = [
        [0, 0, 0, 62.286, 0, 33],
        [0.276, -0.097, 0, 41.892, 0, 45],
        [0.567, 1.084, 0, 85, 0, 29.209],
        [1, 1, 0, 62.286, 0, 33]
    ]

class GRAPH_OT_apply_anticipation1_easing(GRAPH_OT_apply_advanced_easing_base):
    """Apply Anticipation 1 easing preset to selected keyframes"""
    bl_idname = "graph.apply_anticipation1_easing"
    bl_label = "Apply Anticipation 1 Easing"
    preset_name = "Anticipation 1"
    spatial_data = [
        [0, 0, 0, 85, 0, 55.742],
        [0.235, -0.067, 0, 33, 0, 31.545],
        [1, 1, 0, 85, 0, 55.742]
    ]

class GRAPH_OT_apply_anticipation2_easing(GRAPH_OT_apply_advanced_easing_base):
    """Apply Anticipation 2 easing preset to selected keyframes"""
    bl_idname = "graph.apply_anticipation2_easing"
    bl_label = "Apply Anticipation 2 Easing"
    preset_name = "Anticipation 2"
    spatial_data = [
        [0, 0, 0, 85, 0, 45],
        [0.317, -0.116, 0, 60, 0, 45],
        [1, 1, 0, 85, 0, 45]
    ]

class GRAPH_OT_apply_anticipation3_easing(GRAPH_OT_apply_advanced_easing_base):
    """Apply Anticipation 3 easing preset to selected keyframes"""
    bl_idname = "graph.apply_anticipation3_easing"
    bl_label = "Apply Anticipation 3 Easing"
    preset_name = "Anticipation 3"
    spatial_data = [
        [0, 0, 0, 95, 0, 55],
        [0.5, -0.116, 0, 33, 0, 60],
        [1, 1, 0, 95, 0, 55]
    ]

class GRAPH_OT_apply_agitated_easing(GRAPH_OT_apply_advanced_easing_base):
    """Apply Agitated easing preset to selected keyframes"""
    bl_idname = "graph.apply_agitated_easing"
    bl_label = "Apply Agitated Easing"
    preset_name = "Agitated"
    spatial_data = [
        [0, 0, 0, 50, 0, 50],
        [0.12, 0.029, 0, 27.877, 0, 35.111],
        [0.3, -0.115, 0, 35.041, 0, 40.258],
        [0.68, 1.083, 0, 84, 0, 33],
        [1, 1, 0, 50, 0, 50]
    ]

class GRAPH_OT_apply_springy_easing(GRAPH_OT_apply_advanced_easing_base):
    """Apply Springy easing preset to selected keyframes"""
    bl_idname = "graph.apply_springy_easing"
    bl_label = "Apply Springy Easing"
    preset_name = "Springy"
    spatial_data = [
        [0, 0, 0, 39.907, 0, 33],
        [0.217, -0.312, 0, 57.248, 0, 67.792],
        [0.529, 1.312, 0, 46.008, 0, 35.041],
        [0.773, 0.928, 0, 39.907, 0, 28.093],
        [1, 1, 0, 39.907, 0, 33]
    ]

class GRAPH_OT_apply_very_late_stop_easing(GRAPH_OT_apply_advanced_easing_base):
    """Apply Very Late Stop easing preset to selected keyframes"""
    bl_idname = "graph.apply_very_late_stop_easing"
    bl_label = "Apply Very Late Stop Easing"
    preset_name = "Very Late Stop"
    spatial_data = [
        [0, 0, 0, 57.711, 0, 45],
        [0.238, 0.863, 0.75, 80, 0.75, 16.84],
        [1, 1, 0, 57.711, 0, 45]
    ]

class GRAPH_OT_apply_weird_easing(GRAPH_OT_apply_advanced_easing_base):
    """Apply Weird easing preset to selected keyframes"""
    bl_idname = "graph.apply_weird_easing"
    bl_label = "Apply Weird Easing"
    preset_name = "Weird"
    spatial_data = [
        [0, 0, 0, 90, 0, 90],
        [0.289, -0.185, -2.55, 0.1, 2.55, 0.1],
        [1, 1, 0, 90, 0, 90]
    ]

class GRAPH_OT_apply_overshoot_x3_easing(GRAPH_OT_apply_advanced_easing_base):
    """Apply Overshoot x3 easing preset to selected keyframes"""
    bl_idname = "graph.apply_overshoot_x3_easing"
    bl_label = "Apply Overshoot x3 Easing"
    preset_name = "Overshoot x3"
    spatial_data = [
        [0, 0, 0, 70, 0, 90],
        [0.427, 1.3, 0, 23.423, 0, 35.041],
        [0.596, 0.85, 0, 39.907, 0, 28.093],
        [0.767, 1.05, 0, 39.907, 0, 21.693],
        [1, 1, 0, 70, 0, 90]
    ]

class GRAPH_OT_apply_spring_back_easing(GRAPH_OT_apply_advanced_easing_base):
    """Apply Spring Back easing preset to selected keyframes"""
    bl_idname = "graph.apply_spring_back_easing"
    bl_label = "Apply Spring Back Easing"
    preset_name = "Spring Back"
    spatial_data = [
        [0, 0, 0, 42.456, 0, 0.1],
        [0.147, 1.448, 0, 45, 0, 35],
        [0.318, 0.776, 0, 37.685, 0, 30.603],
        [0.49, 1.108, 0, 33.226, 0, 31.246],
        [0.655, 0.947, 0, 36.147, 0, 29.785],
        [0.827, 1.014, 0, 35.987, 0, 23.974],
        [1, 1, 0, 42.456, 0, 0.1]
    ]

class GRAPH_OT_apply_bouncy_easing(GRAPH_OT_apply_advanced_easing_base):
    """Apply Bouncy easing preset to selected keyframes"""
    bl_idname = "graph.apply_bouncy_easing"
    bl_label = "Apply Bouncy Easing"
    preset_name = "Bouncy"
    spatial_data = [
        [0, 0, 1.024, 23.549, 0, 86.165],
        [0.412, 1, 0, 0.1, -2.481, 26.738],
        [0.592, 0.829, 0, 36.181, 0, 39.572],
        [0.776, 1, 2.631, 21.96, -1.613, 31.677],
        [0.845, 0.951, 0, 33.135, 0, 39.94],
        [0.917, 1, 1.65, 23.219, -0.677, 32.684],
        [0.962, 0.986, 0, 32.082, 0, 40.356],
        [1, 1, 1.024, 23.549, 0, 86.165]
    ]

# ============================================================================
# CUSTOM PRESETS: OPERATORS
# ============================================================================

class GRAPH_OT_add_simple_custom_preset(bpy.types.Operator):
    """Save the 2 selected keyframes on a single F-Curve as a new Simple custom preset"""
    bl_idname = "graph.add_simple_custom_preset"
    bl_label = "Add Simple Preset"
    bl_options = {'REGISTER', 'UNDO'}

    preset_name: bpy.props.StringProperty(
        name="Preset Name",
        description="Name for the new preset",
        default="My Preset"
    )

    @classmethod
    def poll(cls, context):
        # Enabled with exactly 2 keyframes selected on the target F-Curve —
        # the active one if there is one, otherwise (e.g. after a Box
        # Select, which doesn't set an "active" curve) the single curve
        # that has a selection. A preset is a single named shape, so it
        # still needs one unambiguous source.
        fcurve = get_single_target_fcurve(context)
        if fcurve is None:
            return False
        selected_count = sum(1 for kf in fcurve.keyframe_points if kf.select_control_point)
        return selected_count == 2

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        if not self.preset_name.strip():
            self.report({'ERROR'}, "Preset name cannot be empty")
            return {'CANCELLED'}

        fcurve = get_single_target_fcurve(context)
        if fcurve is None:
            self.report({'ERROR'}, "Select exactly 2 keyframes on a single F-Curve")
            return {'CANCELLED'}
        selected_kfs = [kf for kf in fcurve.keyframe_points if kf.select_control_point]
        if len(selected_kfs) != 2:
            self.report({'ERROR'}, "Select exactly 2 keyframes on a single F-Curve")
            return {'CANCELLED'}

        kf1, kf2 = sorted(selected_kfs, key=lambda kf: kf.co.x)
        data = extract_simple_preset_data(kf1, kf2)
        if data is None:
            self.report({'ERROR'}, "Keyframes are too close together to capture")
            return {'CANCELLED'}

        final_name = save_new_custom_preset("simple", self.preset_name.strip(), data)
        if final_name is None:
            self.report({'ERROR'}, "Failed to save preset")
            return {'CANCELLED'}

        context.area.tag_redraw()
        self.report({'INFO'}, f"Saved Simple preset '{final_name}'")
        return {'FINISHED'}


class GRAPH_OT_add_advanced_custom_preset(bpy.types.Operator):
    """Save the selected keyframes (3+) on a single F-Curve as a new Advanced custom preset"""
    bl_idname = "graph.add_advanced_custom_preset"
    bl_label = "Add Advanced Preset"
    bl_options = {'REGISTER', 'UNDO'}

    preset_name: bpy.props.StringProperty(
        name="Preset Name",
        description="Name for the new preset",
        default="My Preset"
    )

    @classmethod
    def poll(cls, context):
        fcurve = get_single_target_fcurve(context)
        if fcurve is None:
            return False
        selected_count = sum(1 for kf in fcurve.keyframe_points if kf.select_control_point)
        return selected_count > 2

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        if not self.preset_name.strip():
            self.report({'ERROR'}, "Preset name cannot be empty")
            return {'CANCELLED'}

        fcurve = get_single_target_fcurve(context)
        if fcurve is None:
            self.report({'ERROR'}, "Select more than 2 keyframes on a single F-Curve")
            return {'CANCELLED'}
        selected_kfs = [kf for kf in fcurve.keyframe_points if kf.select_control_point]
        if len(selected_kfs) <= 2:
            self.report({'ERROR'}, "Select more than 2 keyframes on a single F-Curve")
            return {'CANCELLED'}

        spatial_data = extract_advanced_preset_data(selected_kfs)
        if spatial_data is None:
            self.report({'ERROR'}, "Keyframes are too close together to capture")
            return {'CANCELLED'}

        final_name = save_new_custom_preset("advanced", self.preset_name.strip(), {"spatial_data": spatial_data})
        if final_name is None:
            self.report({'ERROR'}, "Failed to save preset")
            return {'CANCELLED'}

        context.area.tag_redraw()
        self.report({'INFO'}, f"Saved Advanced preset '{final_name}'")
        return {'FINISHED'}


class GRAPH_OT_apply_custom_simple_preset(bpy.types.Operator):
    """Apply a custom Simple preset to selected keyframes"""
    bl_idname = "graph.apply_custom_simple_preset"
    bl_label = "Apply Custom Simple Preset"
    bl_options = {'REGISTER', 'UNDO'}

    preset_id: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context):
        return graph_has_anim_data(context)

    def execute(self, context):
        preset = get_custom_preset("simple", self.preset_id)
        if preset is None:
            self.report({'ERROR'}, "Preset not found (it may have been deleted)")
            return {'CANCELLED'}
        preset_data = preset["data"]

        # Same fcurve-gathering behavior as the built-in Simple presets:
        # applies to every selected curve, not just the active one — only
        # SAVING a preset is restricted to the active curve.
        fcurves = []
        if hasattr(context, 'selected_visible_fcurves') and context.selected_visible_fcurves:
            fcurves = context.selected_visible_fcurves
        elif hasattr(context, 'active_editable_fcurve') and context.active_editable_fcurve:
            fcurves = [context.active_editable_fcurve]

        processed_curves = 0
        for fcurve in fcurves:
            selected_keyframes = [kf for kf in fcurve.keyframe_points if kf.select_control_point]
            if len(selected_keyframes) < 2:
                continue
            selected_keyframes.sort(key=lambda kf: kf.co.x)

            for i in range(len(selected_keyframes) - 1):
                kf1 = selected_keyframes[i]
                kf2 = selected_keyframes[i + 1]
                kf1.interpolation = 'BEZIER'
                kf2.interpolation = 'BEZIER'
                apply_simple_preset_data(kf1, kf2, preset_data)

            fcurve.update()
            processed_curves += 1

        context.area.tag_redraw()

        if processed_curves == 0:
            self.report({'WARNING'}, "No curves with at least 2 selected keyframes found")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Applied preset '{preset['name']}' to {processed_curves} curve(s)")
        return {'FINISHED'}


class GRAPH_OT_apply_custom_advanced_preset(GRAPH_OT_apply_advanced_easing_base):
    """Apply a custom Advanced preset to selected keyframes"""
    bl_idname = "graph.apply_custom_advanced_preset"
    bl_label = "Apply Custom Advanced Preset"

    preset_id: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context):
        return graph_has_anim_data(context)

    def execute(self, context):
        preset = get_custom_preset("advanced", self.preset_id)
        if preset is None:
            self.report({'ERROR'}, "Preset not found (it may have been deleted)")
            return {'CANCELLED'}

        # Reuse the exact same (already-fixed) Advanced apply logic — just
        # feed it this preset's spatial_data instead of a hardcoded one.
        self.spatial_data = preset["data"]["spatial_data"]
        self.preset_name = preset["name"]
        return super().execute(context)


class GRAPH_OT_rename_custom_preset(bpy.types.Operator):
    """Rename a custom preset"""
    bl_idname = "graph.rename_custom_preset"
    bl_label = "Rename Custom Preset"
    bl_options = {'REGISTER', 'UNDO'}

    preset_type: bpy.props.StringProperty()
    preset_id: bpy.props.StringProperty()
    new_name: bpy.props.StringProperty(name="New Name")

    def invoke(self, context, event):
        preset = get_custom_preset(self.preset_type, self.preset_id)
        if preset is None:
            self.report({'ERROR'}, "Preset not found (it may have been deleted)")
            return {'CANCELLED'}
        self.new_name = preset["name"]
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        # Only show the name field — preset_type/preset_id are internal
        # arguments, not something the user should see or edit.
        self.layout.prop(self, "new_name")

    def execute(self, context):
        if not self.new_name.strip():
            self.report({'ERROR'}, "Preset name cannot be empty")
            return {'CANCELLED'}

        final_name = rename_custom_preset(self.preset_type, self.preset_id, self.new_name.strip())
        if final_name is None:
            self.report({'ERROR'}, "Preset not found (it may have been deleted)")
            return {'CANCELLED'}

        context.area.tag_redraw()
        self.report({'INFO'}, f"Renamed preset to '{final_name}'")
        return {'FINISHED'}


class GRAPH_OT_delete_custom_preset(bpy.types.Operator):
    """Delete a custom preset"""
    bl_idname = "graph.delete_custom_preset"
    bl_label = "Delete Custom Preset"
    bl_options = {'REGISTER', 'UNDO'}

    preset_type: bpy.props.StringProperty()
    preset_id: bpy.props.StringProperty()

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        preset = get_custom_preset(self.preset_type, self.preset_id)
        preset_name = preset["name"] if preset else "preset"

        if not delete_custom_preset(self.preset_type, self.preset_id):
            self.report({'ERROR'}, "Failed to delete preset")
            return {'CANCELLED'}

        context.area.tag_redraw()
        self.report({'INFO'}, f"Deleted preset '{preset_name}'")
        return {'FINISHED'}


class EASING_PT_presets_main:
    """Base class for easing presets panel"""
    bl_label = "Easing Presets"
    bl_region_type = 'UI'
    bl_category = "Easeit"
    bl_description = "Select 2+ keyframes per curve"
    
    def draw(self, context):
        layout = self.layout
    
# Simple Easing subpanel
class EASING_PT_simple_base:
    """Simple easing presets subpanel"""
    bl_label = "Simple Easing"
    bl_region_type = 'UI'
    bl_category = "Easeit"

    def draw(self, context):
        layout = self.layout
        pcoll = preview_collections["main"]
        
        # Symmetric easing presets
        layout.label(text="Symmetric Easing:")
        row = layout.row(align=True)
        row.operator("graph.apply_default_easing", text="33", icon_value=pcoll["DEFAULT"].icon_id)
        row.operator("graph.apply_just_fine_easing", text="45", icon_value=pcoll["JUST_FINE"].icon_id)
        
        row = layout.row(align=True)
        row.operator("graph.apply_cubic_easing", text="65", icon_value=pcoll["CUBIC"].icon_id)
        row.operator("graph.apply_exponential_easing", text="87", icon_value=pcoll["EXPONENTIAL"].icon_id)
        
        row = layout.row(align=True)
        row.operator("graph.apply_extreme_easing", text="95", icon_value=pcoll["EXTREME"].icon_id)
        row.operator("graph.apply_linear_easing", text="0", icon_value=pcoll["LINEAR"].icon_id)
        
        layout.operator("graph.apply_max_easing", text="100", icon_value=pcoll["MAX"].icon_id)
        
        # Asymmetric easing presets
        layout.label(text="Asymmetric Easing:")
        row = layout.row(align=True)
        row.operator("graph.apply_smooth_easing", text="40 60", icon_value=pcoll["SMOOTH"].icon_id)
        row.operator("graph.apply_easy_easing", text="30 90", icon_value=pcoll["EASY"].icon_id)
        
        row = layout.row(align=True)
        row.operator("graph.apply_super_smooth_easing", text="50 95", icon_value=pcoll["SUPER_SMOOTH"].icon_id)
        row.operator("graph.apply_smooth_out_easing", text="60 40", icon_value=pcoll["SMOOTH_OUT"].icon_id)
        
        row = layout.row(align=True)
        row.operator("graph.apply_easy_out_easing", text="90 30", icon_value=pcoll["EASY_OUT"].icon_id)
        row.operator("graph.apply_super_smooth_out_easing", text="95 50", icon_value=pcoll["SUPER_SMOOTH_OUT"].icon_id)
        
        # One-sided easing presets
        layout.label(text="One-Sided Easing:")
        row = layout.row(align=True)
        row.operator("graph.apply_ease_in_only_easing", text="0 90", icon_value=pcoll["EASY_IN"].icon_id)
        row.operator("graph.apply_ease_out_only_easing", text="90 0", icon_value=pcoll["EASE_OUT"].icon_id)

        # Custom presets
        layout.separator()
        layout.label(text="Custom presets:")
        if custom_presets_cache["simple"]:
            for preset in custom_presets_cache["simple"]:
                row = layout.row(align=True)
                op = row.operator("graph.apply_custom_simple_preset", text=preset["name"])
                op.preset_id = preset["id"]
                op_rename = row.operator("graph.rename_custom_preset", text="", icon='GREASEPENCIL')
                op_rename.preset_type = "simple"
                op_rename.preset_id = preset["id"]
                op_del = row.operator("graph.delete_custom_preset", text="", icon='X')
                op_del.preset_type = "simple"
                op_del.preset_id = preset["id"]
        else:
            layout.label(text="No custom presets", icon='INFO')
        layout.operator("graph.add_simple_custom_preset", text="+ Add from Selection", icon='ADD')

# Advanced Easing subpanel
class EASING_PT_advanced_base:
    """Advanced easing presets subpanel"""
    bl_label = "Advanced Easing"
    bl_region_type = 'UI'
    bl_category = "Easeit"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        pcoll = preview_collections["main"]
        
        # Advanced/Special easing presets
        row = layout.row(align=True)
        row.operator("graph.apply_explosive_easing", text="Explosive", icon_value=pcoll["EXPLOSIVE"].icon_id)
        row.operator("graph.apply_overshoot1_easing", text="Overshoot 1", icon_value=pcoll["OVERSHOOT_01"].icon_id)
        
        row = layout.row(align=True)
        row.operator("graph.apply_overshoot2_easing", text="Overshoot 2", icon_value=pcoll["OVERSHOOT_02"].icon_id)
        row.operator("graph.apply_easy_going_easing", text="Easy Going", icon_value=pcoll["EASY_GOING"].icon_id)
        
        row = layout.row(align=True)
        row.operator("graph.apply_anticipation1_easing", text="Anticipation 1", icon_value=pcoll["ANTICIPATION_01"].icon_id)
        row.operator("graph.apply_anticipation2_easing", text="Anticipation 2", icon_value=pcoll["ANTICIPATION_02"].icon_id)
        
        row = layout.row(align=True)
        row.operator("graph.apply_anticipation3_easing", text="Anticipation 3", icon_value=pcoll["ANTICIPATION_03"].icon_id)
        row.operator("graph.apply_anticipation_overshoot_easing", text="Antic + Over", icon_value=pcoll["ANTICIPATION_OVERSHOOT"].icon_id)
        
        row = layout.row(align=True)
        row.operator("graph.apply_agitated_easing", text="Agitated", icon_value=pcoll["AGITATED"].icon_id)
        row.operator("graph.apply_springy_easing", text="Springy", icon_value=pcoll["SPRINGY"].icon_id)
        
        row = layout.row(align=True)
        row.operator("graph.apply_very_late_stop_easing", text="Very Late Stop", icon_value=pcoll["VERY_LATE_STOP"].icon_id)
        row.operator("graph.apply_weird_easing", text="Weird", icon_value=pcoll["WEIRD"].icon_id)
        
        row = layout.row(align=True)
        row.operator("graph.apply_overshoot_x3_easing", text="Overshoot x3", icon_value=pcoll["OVERSHOOT_X3"].icon_id)
        row.operator("graph.apply_spring_back_easing", text="Spring Back", icon_value=pcoll["SPRING_BACK"].icon_id)

        layout.operator("graph.apply_bouncy_easing", text="Bouncy", icon_value=pcoll["BOUNCY"].icon_id)

        # Custom presets
        layout.separator()
        layout.label(text="Custom presets:")
        if custom_presets_cache["advanced"]:
            for preset in custom_presets_cache["advanced"]:
                row = layout.row(align=True)
                op = row.operator("graph.apply_custom_advanced_preset", text=preset["name"])
                op.preset_id = preset["id"]
                op_rename = row.operator("graph.rename_custom_preset", text="", icon='GREASEPENCIL')
                op_rename.preset_type = "advanced"
                op_rename.preset_id = preset["id"]
                op_del = row.operator("graph.delete_custom_preset", text="", icon='X')
                op_del.preset_type = "advanced"
                op_del.preset_id = preset["id"]
        else:
            layout.label(text="No custom presets", icon='INFO')
        layout.operator("graph.add_advanced_custom_preset", text="+ Add from Selection", icon='ADD')

# Panel for Graph Editor
    
class GRAPH_PT_easing_presets_main(EASING_PT_presets_main, bpy.types.Panel):
    bl_idname = "GRAPH_PT_easing_presets_main"
    bl_space_type = 'GRAPH_EDITOR'

class GRAPH_PT_easing_simple(EASING_PT_simple_base, bpy.types.Panel):
    bl_idname = "GRAPH_PT_easing_simple"
    bl_parent_id = "GRAPH_PT_easing_presets_main"
    bl_space_type = 'GRAPH_EDITOR'

class GRAPH_PT_easing_advanced(EASING_PT_advanced_base, bpy.types.Panel):
    bl_idname = "GRAPH_PT_easing_advanced"
    bl_parent_id = "GRAPH_PT_easing_presets_main"
    bl_space_type = 'GRAPH_EDITOR'

# Panel for Dope Sheet
class DOPESHEET_PT_easing_presets_main(EASING_PT_presets_main, bpy.types.Panel):
    bl_idname = "DOPESHEET_PT_easing_presets_main"
    bl_space_type = 'DOPESHEET_EDITOR'

class DOPESHEET_PT_easing_simple(EASING_PT_simple_base, bpy.types.Panel):
    bl_idname = "DOPESHEET_PT_easing_simple"
    bl_parent_id = "DOPESHEET_PT_easing_presets_main"
    bl_space_type = 'DOPESHEET_EDITOR'

class DOPESHEET_PT_easing_advanced(EASING_PT_advanced_base, bpy.types.Panel):
    bl_idname = "DOPESHEET_PT_easing_advanced"
    bl_parent_id = "DOPESHEET_PT_easing_presets_main"
    bl_space_type = 'DOPESHEET_EDITOR'

def register():
    load_icons()
    reload_custom_presets_cache()
    bpy.utils.register_class(GRAPH_OT_apply_easing_base)
    bpy.utils.register_class(GRAPH_OT_apply_advanced_easing_base)
    bpy.utils.register_class(GRAPH_OT_apply_default_easing)
    bpy.utils.register_class(GRAPH_OT_apply_just_fine_easing)
    bpy.utils.register_class(GRAPH_OT_apply_cubic_easing)
    bpy.utils.register_class(GRAPH_OT_apply_exponential_easing)
    bpy.utils.register_class(GRAPH_OT_apply_extreme_easing)
    bpy.utils.register_class(GRAPH_OT_apply_smooth_easing)
    bpy.utils.register_class(GRAPH_OT_apply_easy_easing)
    bpy.utils.register_class(GRAPH_OT_apply_super_smooth_easing)
    bpy.utils.register_class(GRAPH_OT_apply_ease_in_only_easing)
    bpy.utils.register_class(GRAPH_OT_apply_ease_out_only_easing)
    bpy.utils.register_class(GRAPH_OT_apply_smooth_out_easing)
    bpy.utils.register_class(GRAPH_OT_apply_easy_out_easing)
    bpy.utils.register_class(GRAPH_OT_apply_super_smooth_out_easing)
    bpy.utils.register_class(GRAPH_OT_apply_linear_easing)
    bpy.utils.register_class(GRAPH_OT_apply_max_easing)
    bpy.utils.register_class(GRAPH_OT_apply_explosive_easing)
    bpy.utils.register_class(GRAPH_OT_apply_overshoot1_easing)
    bpy.utils.register_class(GRAPH_OT_apply_overshoot2_easing)
    bpy.utils.register_class(GRAPH_OT_apply_easy_going_easing)
    bpy.utils.register_class(GRAPH_OT_apply_anticipation_overshoot_easing)
    bpy.utils.register_class(GRAPH_OT_apply_anticipation1_easing)
    bpy.utils.register_class(GRAPH_OT_apply_anticipation2_easing)
    bpy.utils.register_class(GRAPH_OT_apply_anticipation3_easing)
    bpy.utils.register_class(GRAPH_OT_apply_agitated_easing)
    bpy.utils.register_class(GRAPH_OT_apply_springy_easing)
    bpy.utils.register_class(GRAPH_OT_apply_very_late_stop_easing)
    bpy.utils.register_class(GRAPH_OT_apply_weird_easing)
    bpy.utils.register_class(GRAPH_OT_apply_overshoot_x3_easing)
    bpy.utils.register_class(GRAPH_OT_apply_spring_back_easing)
    bpy.utils.register_class(GRAPH_OT_apply_bouncy_easing)
    bpy.utils.register_class(GRAPH_OT_add_simple_custom_preset)
    bpy.utils.register_class(GRAPH_OT_add_advanced_custom_preset)
    bpy.utils.register_class(GRAPH_OT_apply_custom_simple_preset)
    bpy.utils.register_class(GRAPH_OT_apply_custom_advanced_preset)
    bpy.utils.register_class(GRAPH_OT_rename_custom_preset)
    bpy.utils.register_class(GRAPH_OT_delete_custom_preset)
    bpy.utils.register_class(GRAPH_PT_easing_presets_main)
    bpy.utils.register_class(GRAPH_PT_easing_simple)
    bpy.utils.register_class(GRAPH_PT_easing_advanced)
    bpy.utils.register_class(DOPESHEET_PT_easing_presets_main)
    bpy.utils.register_class(DOPESHEET_PT_easing_simple)
    bpy.utils.register_class(DOPESHEET_PT_easing_advanced)

def unregister():
    bpy.utils.unregister_class(GRAPH_OT_apply_easing_base)
    bpy.utils.unregister_class(GRAPH_OT_apply_advanced_easing_base)
    bpy.utils.unregister_class(GRAPH_OT_apply_default_easing)
    bpy.utils.unregister_class(GRAPH_OT_apply_just_fine_easing)
    bpy.utils.unregister_class(GRAPH_OT_apply_cubic_easing)
    bpy.utils.unregister_class(GRAPH_OT_apply_exponential_easing)
    bpy.utils.unregister_class(GRAPH_OT_apply_extreme_easing)
    bpy.utils.unregister_class(GRAPH_OT_apply_smooth_easing)
    bpy.utils.unregister_class(GRAPH_OT_apply_easy_easing)
    bpy.utils.unregister_class(GRAPH_OT_apply_super_smooth_easing)
    bpy.utils.unregister_class(GRAPH_OT_apply_ease_in_only_easing)
    bpy.utils.unregister_class(GRAPH_OT_apply_ease_out_only_easing)
    bpy.utils.unregister_class(GRAPH_OT_apply_smooth_out_easing)
    bpy.utils.unregister_class(GRAPH_OT_apply_easy_out_easing)
    bpy.utils.unregister_class(GRAPH_OT_apply_super_smooth_out_easing)
    bpy.utils.unregister_class(GRAPH_OT_apply_linear_easing)
    bpy.utils.unregister_class(GRAPH_OT_apply_max_easing)
    bpy.utils.unregister_class(GRAPH_OT_apply_explosive_easing)
    bpy.utils.unregister_class(GRAPH_OT_apply_overshoot1_easing)
    bpy.utils.unregister_class(GRAPH_OT_apply_overshoot2_easing)
    bpy.utils.unregister_class(GRAPH_OT_apply_easy_going_easing)
    bpy.utils.unregister_class(GRAPH_OT_apply_anticipation_overshoot_easing)
    bpy.utils.unregister_class(GRAPH_OT_apply_anticipation1_easing)
    bpy.utils.unregister_class(GRAPH_OT_apply_anticipation2_easing)
    bpy.utils.unregister_class(GRAPH_OT_apply_anticipation3_easing)
    bpy.utils.unregister_class(GRAPH_OT_apply_agitated_easing)
    bpy.utils.unregister_class(GRAPH_OT_apply_springy_easing)
    bpy.utils.unregister_class(GRAPH_OT_apply_very_late_stop_easing)
    bpy.utils.unregister_class(GRAPH_OT_apply_weird_easing)
    bpy.utils.unregister_class(GRAPH_OT_apply_overshoot_x3_easing)
    bpy.utils.unregister_class(GRAPH_OT_apply_spring_back_easing)
    bpy.utils.unregister_class(GRAPH_OT_apply_bouncy_easing)
    bpy.utils.unregister_class(GRAPH_OT_add_simple_custom_preset)
    bpy.utils.unregister_class(GRAPH_OT_add_advanced_custom_preset)
    bpy.utils.unregister_class(GRAPH_OT_apply_custom_simple_preset)
    bpy.utils.unregister_class(GRAPH_OT_apply_custom_advanced_preset)
    bpy.utils.unregister_class(GRAPH_OT_rename_custom_preset)
    bpy.utils.unregister_class(GRAPH_OT_delete_custom_preset)
    bpy.utils.unregister_class(GRAPH_PT_easing_presets_main)
    bpy.utils.unregister_class(GRAPH_PT_easing_simple)
    bpy.utils.unregister_class(GRAPH_PT_easing_advanced)
    bpy.utils.unregister_class(DOPESHEET_PT_easing_presets_main)
    bpy.utils.unregister_class(DOPESHEET_PT_easing_simple)
    bpy.utils.unregister_class(DOPESHEET_PT_easing_advanced)
    unload_icons()

if __name__ == "__main__":
    register()
