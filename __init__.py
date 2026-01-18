bl_info = {
    "name": "EaseIt",
    "author": "Andy Cuccaro",
    "version": (1, 0, 0),
    "blender": (2, 80, 0),
    "location": "Graph Editor > Sidebar > Easing",
    "description": "Apply easing presets to selected keyframes",
    "category": "Animation",
}

import bpy
import bmesh
from mathutils import Vector

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
        # Get all visible and editable fcurves
        fcurves = []

        # Try to get fcurves from Graph Editor context first
        if hasattr(context, 'selected_visible_fcurves') and context.selected_visible_fcurves:
            fcurves = context.selected_visible_fcurves
        elif hasattr(context, 'active_editable_fcurve') and context.active_editable_fcurve:
            fcurves = [context.active_editable_fcurve]
        else:
            # Fallback for Dope Sheet and other editors
            # Get fcurves from selected objects' animation data
            if context.selected_objects:
                for obj in context.selected_objects:
                    if obj.animation_data and obj.animation_data.action:
                        fcurves.extend(obj.animation_data.action.fcurves)
            # Also try to get from scene animation data
            if context.scene.animation_data and context.scene.animation_data.action:
                fcurves.extend(context.scene.animation_data.action.fcurves)
        
        if not fcurves:
            self.report({'ERROR'}, "No F-Curves found")
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
                
                # Store original handle types and positions to preserve unaffected handles
                kf1_left_handle_type = kf1.handle_left_type
                kf1_left_handle_pos = kf1.handle_left.copy()
                kf2_right_handle_type = kf2.handle_right_type
                kf2_right_handle_pos = kf2.handle_right.copy()
                
                # Apply to first keyframe (ease out)
                # Only modify the right handle, preserve left handle unless it's the first keyframe
                if i == 0 or kf1.handle_right_type != 'ALIGNED':
                    kf1.handle_right_type = 'ALIGNED'
                kf1.handle_right = (kf1.co.x + handle_extension_out, kf1.co.y)
                
                # For first keyframe in sequence, preserve left handle
                if i == 0:
                    kf1.handle_left_type = kf1_left_handle_type
                    if kf1_left_handle_type in ['FREE', 'ALIGNED']:
                        kf1.handle_left = kf1_left_handle_pos
                
                # Apply to second keyframe (ease in)  
                # Only modify the left handle, preserve right handle unless it's the last keyframe
                if i == len(selected_keyframes) - 2 or kf2.handle_left_type != 'ALIGNED':
                    kf2.handle_left_type = 'ALIGNED'
                kf2.handle_left = (kf2.co.x - handle_extension_in, kf2.co.y)
                
                # For last keyframe in sequence, preserve right handle
                if i == len(selected_keyframes) - 2:
                    kf2.handle_right_type = kf2_right_handle_type
                    if kf2_right_handle_type in ['FREE', 'ALIGNED']:
                        kf2.handle_right = kf2_right_handle_pos
            
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
    # [x_pos, y_pos, slope_left, ease_left_x, slope_right, ease_right_x, flag1, flag2, flag3]
    spatial_data = []
    preset_name = "Advanced Default"

    def execute(self, context):        
        # Get all visible and editable fcurves
        fcurves = []

        # Try to get fcurves from Graph Editor context first
        if hasattr(context, 'selected_visible_fcurves') and context.selected_visible_fcurves:
            fcurves = context.selected_visible_fcurves
        elif hasattr(context, 'active_editable_fcurve') and context.active_editable_fcurve:
            fcurves = [context.active_editable_fcurve]
        else:
            # Fallback for Dope Sheet and other editors
            # Get fcurves from selected objects' animation data
            if context.selected_objects:
                for obj in context.selected_objects:
                    if obj.animation_data and obj.animation_data.action:
                        fcurves.extend(obj.animation_data.action.fcurves)
            # Also try to get from scene animation data
            if context.scene.animation_data and context.scene.animation_data.action:
                fcurves.extend(context.scene.animation_data.action.fcurves)
        
        if not fcurves:
            self.report({'ERROR'}, "No F-Curves found")
            return {'CANCELLED'}
        
        if not self.spatial_data:
            self.report({'ERROR'}, "No spatial data defined for this preset")
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
            
            # Get the first and last selected keyframes
            first_kf = selected_keyframes[0][1]
            last_kf = selected_keyframes[-1][1]
            
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
            for i, data_point in enumerate(self.spatial_data):
                x_pos, y_pos, slope_left, ease_left_x, slope_right, ease_right_x, flag1, flag2, flag3 = data_point
                
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
                
                created_keyframes.append(kf)
            
            # Select the first and last keyframes to match original selection
            if created_keyframes:
                created_keyframes[0].select_control_point = True
                created_keyframes[-1].select_control_point = True
            
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
        [0, 0, 0, 65, 0, 0.1, 0, 0, 0],
        [0.321, 1.189, 0, 81.207, 0, 19.154, 0, 0, 0],
        [1, 1, 0, 65, 0, 0.1, 0, 0, 0]
    ]

class GRAPH_OT_apply_overshoot1_easing(GRAPH_OT_apply_advanced_easing_base):
    """Apply Overshoot 1 easing preset to selected keyframes"""
    bl_idname = "graph.apply_overshoot1_easing"
    bl_label = "Apply Overshoot 1 Easing"
    preset_name = "Overshoot 1"
    spatial_data = [
        [0, 0, 0, 72.124, 0, 45, 0, 0, 0],
        [0.412, 1.148, 0, 56.011, 0, 17.461, 0, 0, 0],
        [1, 1, 0, 72.124, 0, 45, 0, 0, 0]
    ]

class GRAPH_OT_apply_overshoot2_easing(GRAPH_OT_apply_advanced_easing_base):
    """Apply Overshoot 2 easing preset to selected keyframes"""
    bl_idname = "graph.apply_overshoot2_easing"
    bl_label = "Apply Overshoot 2 Easing"
    preset_name = "Overshoot 2"
    spatial_data = [
        [0, 0, 0, 57.711, 0, 89.414, 0, 0, 0],
        [0.5, 1.176, 0, 50, 0, 36.321, 0, 0, 0],
        [1, 1, 0, 57.711, 0, 89.414, 0, 0, 0]
    ]

class GRAPH_OT_apply_easy_going_easing(GRAPH_OT_apply_advanced_easing_base):
    """Apply Easy Going easing preset to selected keyframes"""
    bl_idname = "graph.apply_easy_going_easing"
    bl_label = "Apply Easy Going Easing"
    preset_name = "Easy Going"
    spatial_data = [
        [0, 0, 0, 62.286, 0, 33, 0, 0, 0],
        [0.182, -0.077, 0, 33, 0, 40, 0, 0, 0],
        [0.649, 1.07, 0, 60, 0, 29.209, 0, 0, 0],
        [1, 1, 0, 62.286, 0, 33, 0, 0, 0]
    ]

class GRAPH_OT_apply_anticipation_overshoot_easing(GRAPH_OT_apply_advanced_easing_base):
    """Apply Anticipation + Overshoot easing preset to selected keyframes"""
    bl_idname = "graph.apply_anticipation_overshoot_easing"
    bl_label = "Apply Anticipation + Overshoot Easing"
    preset_name = "Anticipation + Overshoot"
    spatial_data = [
        [0, 0, 0, 62.286, 0, 33, 0, 0, 0],
        [0.276, -0.097, 0, 41.892, 0, 45, 0, 0, 0],
        [0.567, 1.084, 0, 85, 0, 29.209, 0, 0, 0],
        [1, 1, 0, 62.286, 0, 33, 0, 0, 0]
    ]

class GRAPH_OT_apply_anticipation1_easing(GRAPH_OT_apply_advanced_easing_base):
    """Apply Anticipation 1 easing preset to selected keyframes"""
    bl_idname = "graph.apply_anticipation1_easing"
    bl_label = "Apply Anticipation 1 Easing"
    preset_name = "Anticipation 1"
    spatial_data = [
        [0, 0, 0, 85, 0, 55.742, 0, 0, 0],
        [0.235, -0.067, 0, 33, 0, 31.545, 0, 0, 0],
        [1, 1, 0, 85, 0, 55.742, 0, 0, 0]
    ]

class GRAPH_OT_apply_anticipation2_easing(GRAPH_OT_apply_advanced_easing_base):
    """Apply Anticipation 2 easing preset to selected keyframes"""
    bl_idname = "graph.apply_anticipation2_easing"
    bl_label = "Apply Anticipation 2 Easing"
    preset_name = "Anticipation 2"
    spatial_data = [
        [0, 0, 0, 85, 0, 45, 0, 0, 0],
        [0.317, -0.116, 0, 60, 0, 45, 0, 0, 0],
        [1, 1, 0, 85, 0, 45, 0, 0, 0]
    ]

class GRAPH_OT_apply_anticipation3_easing(GRAPH_OT_apply_advanced_easing_base):
    """Apply Anticipation 3 easing preset to selected keyframes"""
    bl_idname = "graph.apply_anticipation3_easing"
    bl_label = "Apply Anticipation 3 Easing"
    preset_name = "Anticipation 3"
    spatial_data = [
        [0, 0, 0, 95, 0, 55, 0, 0, 0],
        [0.5, -0.116, 0, 33, 0, 60, 0, 0, 0],
        [1, 1, 0, 95, 0, 55, 0, 0, 0]
    ]

class GRAPH_OT_apply_agitated_easing(GRAPH_OT_apply_advanced_easing_base):
    """Apply Agitated easing preset to selected keyframes"""
    bl_idname = "graph.apply_agitated_easing"
    bl_label = "Apply Agitated Easing"
    preset_name = "Agitated"
    spatial_data = [
        [0, 0, 0, 50, 0, 50, 0, 0, 0],
        [0.12, 0.029, 0, 27.877, 0, 35.111, 0, 0, 0],
        [0.3, -0.115, 0, 35.041, 0, 40.258, 0, 0, 0],
        [0.68, 1.083, 0, 84, 0, 33, 0, 0, 0],
        [1, 1, 0, 50, 0, 50, 0, 0, 0]
    ]

class GRAPH_OT_apply_springy_easing(GRAPH_OT_apply_advanced_easing_base):
    """Apply Springy easing preset to selected keyframes"""
    bl_idname = "graph.apply_springy_easing"
    bl_label = "Apply Springy Easing"
    preset_name = "Springy"
    spatial_data = [
        [0, 0, 0, 39.907, 0, 33, 0, 0, 0],
        [0.217, -0.312, 0, 57.248, 0, 67.792, 0, 0, 0],
        [0.529, 1.312, 0, 46.008, 0, 35.041, 0, 0, 0],
        [0.773, 0.928, 0, 39.907, 0, 28.093, 0, 0, 0],
        [1, 1, 0, 39.907, 0, 33, 0, 0, 0]
    ]

class GRAPH_OT_apply_very_late_stop_easing(GRAPH_OT_apply_advanced_easing_base):
    """Apply Very Late Stop easing preset to selected keyframes"""
    bl_idname = "graph.apply_very_late_stop_easing"
    bl_label = "Apply Very Late Stop Easing"
    preset_name = "Very Late Stop"
    spatial_data = [
        [0, 0, 0, 57.711, 0, 45, True, True, True],
        [0.238, 0.863, 0.75, 80, 0.75, 16.84, True, True, True],
        [1, 1, 0, 57.711, 0, 45, True, True, True]
    ]

class GRAPH_OT_apply_weird_easing(GRAPH_OT_apply_advanced_easing_base):
    """Apply Weird easing preset to selected keyframes"""
    bl_idname = "graph.apply_weird_easing"
    bl_label = "Apply Weird Easing"
    preset_name = "Weird"
    spatial_data = [
        [0, 0, 0, 90, 0, 90, 0, 0, 0],
        [0.289, -0.185, -2.55, 0.1, 2.55, 0.1, 0, 0, 0],
        [1, 1, 0, 90, 0, 90, 0, 0, 0]
    ]

class GRAPH_OT_apply_overshoot_x3_easing(GRAPH_OT_apply_advanced_easing_base):
    """Apply Overshoot x3 easing preset to selected keyframes"""
    bl_idname = "graph.apply_overshoot_x3_easing"
    bl_label = "Apply Overshoot x3 Easing"
    preset_name = "Overshoot x3"
    spatial_data = [
        [0, 0, 0, 70, 0, 90, 0, 0, 0],
        [0.427, 1.3, 0, 23.423, 0, 35.041, 0, 0, 0],
        [0.596, 0.85, 0, 39.907, 0, 28.093, 0, 0, 0],
        [0.767, 1.05, 0, 39.907, 0, 21.693, 0, 0, 0],
        [1, 1, 0, 70, 0, 90, 0, 0, 0]
    ]

class GRAPH_OT_apply_spring_back_easing(GRAPH_OT_apply_advanced_easing_base):
    """Apply Spring Back easing preset to selected keyframes"""
    bl_idname = "graph.apply_spring_back_easing"
    bl_label = "Apply Spring Back Easing"
    preset_name = "Spring Back"
    spatial_data = [
        [0, 0, 0, 42.456, 0, 0.1, True, True, True],
        [0.147, 1.448, 0, 45, 0, 35, True, True, True],
        [0.318, 0.776, 0, 37.685, 0, 30.603, True, True, True],
        [0.49, 1.108, 0, 33.226, 0, 31.246, True, True, True],
        [0.655, 0.947, 0, 36.147, 0, 29.785, True, True, True],
        [0.827, 1.014, 0, 35.987, 0, 23.974, True, True, True],
        [1, 1, 0, 42.456, 0, 0.1, True, True, True]
    ]

class GRAPH_OT_apply_bouncy_easing(GRAPH_OT_apply_advanced_easing_base):
    """Apply Bouncy easing preset to selected keyframes"""
    bl_idname = "graph.apply_bouncy_easing"
    bl_label = "Apply Bouncy Easing"
    preset_name = "Bouncy"
    spatial_data = [
        [0, 0, 1.024, 23.549, 0, 86.165, True, True, True],
        [0.412, 1, 0, 0.1, -2.481, 26.738, True, True, True],
        [0.592, 0.829, 0, 36.181, 0, 39.572, True, True, True],
        [0.776, 1, 2.631, 21.96, -1.613, 31.677, True, True, True],
        [0.845, 0.951, 0, 33.135, 0, 39.94, True, True, True],
        [0.917, 1, 1.65, 23.219, -0.677, 32.684, True, True, True],
        [0.962, 0.986, 0, 32.082, 0, 40.356, True, True, True],
        [1, 1, 1.024, 23.549, 0, 86.165, True, True, True]
    ]

class EASING_PT_presets_base:
    """Base class for easing presets panel"""
    bl_label = "Easing Presets"
    bl_region_type = 'UI'
    bl_category = "Easing"

    def draw(self, context):
        layout = self.layout
        
        # Add some instructions
        layout.label(text="Select 2+ keyframes per curve")
        layout.separator()
        
        # Symmetric easing presets
        layout.label(text="Symmetric Easing:")
        row = layout.row(align=True)
        row.operator("graph.apply_default_easing", text="Default") #, icon='IPO_EASE_IN_OUT')
        row.operator("graph.apply_just_fine_easing", text="Just Fine") #, icon='IPO_SINE')
        
        row = layout.row(align=True)
        row.operator("graph.apply_cubic_easing", text="Cubic") #, icon='IPO_CUBIC')
        row.operator("graph.apply_exponential_easing", text="Exponential") #, icon='IPO_EXPO')
        
        row = layout.row(align=True)
        row.operator("graph.apply_extreme_easing", text="Extreme") #, icon='IPO_EASE_IN_OUT')
        row.operator("graph.apply_linear_easing", text="Linear") #, icon='IPO_LINEAR')
        
        layout.operator("graph.apply_max_easing", text="Max") #, icon='IPO_EASE_IN_OUT')
        
        layout.separator()
        
        # Asymmetric easing presets
        layout.label(text="Asymmetric Easing:")
        row = layout.row(align=True)
        row.operator("graph.apply_smooth_easing", text="Smooth") #, icon='IPO_EASE_IN_OUT')
        row.operator("graph.apply_easy_easing", text="Easy") #, icon='IPO_EASE_IN_OUT')
        
        row = layout.row(align=True)
        row.operator("graph.apply_super_smooth_easing", text="Super Smooth") #, icon='IPO_EASE_IN_OUT')
        row.operator("graph.apply_smooth_out_easing", text="Smooth Out") #, icon='IPO_EASE_IN_OUT')
        
        row = layout.row(align=True)
        row.operator("graph.apply_easy_out_easing", text="Easy Out") #, icon='IPO_EASE_IN_OUT')
        row.operator("graph.apply_super_smooth_out_easing", text="Super Smooth Out") #, icon='IPO_EASE_IN_OUT')
        
        layout.separator()
        
        # One-sided easing presets
        layout.label(text="One-Sided Easing:")
        row = layout.row(align=True)
        row.operator("graph.apply_ease_in_only_easing", text="Ease In Only") #, icon='IPO_EASE_OUT')
        row.operator("graph.apply_ease_out_only_easing", text="Ease Out Only") #, icon='IPO_EASE_IN')
        
        layout.separator()
        
        # Advanced/Special easing presets
        layout.label(text="Advanced Easing:")
        row = layout.row(align=True)
        row.operator("graph.apply_explosive_easing", text="Explosive") #, icon='IPO_EASE_IN_OUT')
        row.operator("graph.apply_springy_easing", text="Springy") #, icon='IPO_EASE_IN_OUT')
        
        row = layout.row(align=True)
        row.operator("graph.apply_overshoot1_easing", text="Overshoot 1") #, icon='IPO_BACK')
        row.operator("graph.apply_overshoot2_easing", text="Overshoot 2") #, icon='IPO_BACK')
        
        row = layout.row(align=True)
        row.operator("graph.apply_anticipation1_easing", text="Anticipation 1") #, icon='IPO_EASE_IN_OUT')
        row.operator("graph.apply_anticipation2_easing", text="Anticipation 2") #, icon='IPO_EASE_IN_OUT')
        
        row = layout.row(align=True)
        row.operator("graph.apply_anticipation3_easing", text="Anticipation 3") #, icon='IPO_EASE_IN_OUT')
        row.operator("graph.apply_easy_going_easing", text="Easy Going") #, icon='IPO_EASE_IN_OUT')
        
        row = layout.row(align=True)
        row.operator("graph.apply_anticipation_overshoot_easing", text="Antic + Over") #, icon='IPO_EASE_IN_OUT')
        row.operator("graph.apply_agitated_easing", text="Agitated") #, icon='IPO_EASE_IN_OUT')
        
        row = layout.row(align=True)
        row.operator("graph.apply_very_late_stop_easing", text="Very Late Stop") #, icon='IPO_EASE_IN_OUT')
        row.operator("graph.apply_overshoot_x3_easing", text="Overshoot x3") #, icon='IPO_EASE_IN_OUT')
        
        row = layout.row(align=True)
        row.operator("graph.apply_spring_back_easing", text="Spring Back") #, icon='IPO_ELASTIC')
        row.operator("graph.apply_bouncy_easing", text="Bouncy") #, icon='IPO_BOUNCE')
        
        layout.operator("graph.apply_weird_easing", text="Weird") #, icon='SHARPCURVE')

# Panel for Graph Editor
class GRAPH_PT_easing_presets(EASING_PT_presets_base, bpy.types.Panel):
    """Panel for easing presets in Graph Editor sidebar"""
    bl_idname = "GRAPH_PT_easing_presets"
    bl_space_type = 'GRAPH_EDITOR'

# Panel for Dope Sheet
class DOPESHEET_PT_easing_presets(EASING_PT_presets_base, bpy.types.Panel):
    """Panel for easing presets in Dope Sheet sidebar"""
    bl_idname = "DOPESHEET_PT_easing_presets"
    bl_space_type = 'DOPESHEET_EDITOR'

def register():
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
    bpy.utils.register_class(GRAPH_PT_easing_presets)
    bpy.utils.register_class(DOPESHEET_PT_easing_presets)

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
    bpy.utils.unregister_class(GRAPH_PT_easing_presets)
    bpy.utils.unregister_class(DOPESHEET_PT_easing_presets)

if __name__ == "__main__":
    register()