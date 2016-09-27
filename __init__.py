# ***** BEGIN GPL LICENSE BLOCK *****
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ***** END GPL LICENCE BLOCK *****

# <pep8 compliant>

bl_info = {
    "name": "Powerlib",
    "author": "Inês Almeida, Francesco Siddi, Olivier Amrein",
    "version": (2, 0, 0),
    "blender": (2, 78, 0),
    "location": "View3D > Tool Shelf (T)",
    "description": "todo",
    "warning": "",
    "wiki_url": "http://wiki.blender.org/index.php/Extensions:2.6/Py/"
                "Scripts/Workflow/-todo-create-new-documentation-page!",
    "category": "Workflow",
}

import os
import json

import bpy
from bpy.types import (
    Operator,
    Menu,
    Panel,
    UIList,
    PropertyGroup,
)
from bpy.props import (
    BoolProperty,
    IntProperty,
    StringProperty,
    EnumProperty,
    CollectionProperty,
    PointerProperty,
)


# load single json library file
asset_categories = {}
with open(os.path.join(os.path.dirname(__file__), "lib.json")) as data_file:
    asset_categories = json.load(data_file)


# Data Structure ##############################################################

class AssetItem(PropertyGroup):
    name = StringProperty(
        name="",
        description="",
    )
    # type = enum?


class AssetCollection(PropertyGroup):
    name = StringProperty(
        name="Asset Collection Name",
        description="",
    )
    active_asset = IntProperty(
        name="",
        description="",
    )
    assets = CollectionProperty(
        name="",
        description="",
        type=AssetItem,
    )


# Operators ###################################################################

class ColRequiredOperator(Operator):
    @classmethod
    def poll(self, context):
        wm = context.window_manager
        return (wm.powerlib_active_col
            and wm.powerlib_cols[wm.powerlib_active_col])

class ColAndAssetRequiredOperator(ColRequiredOperator):
    @classmethod
    def poll(self, context):
        if super().poll(context):
            wm = context.window_manager
            col = wm.powerlib_cols[wm.powerlib_active_col]
            return (col.active_asset < len(col.assets)
                and col.active_asset >= 0)
        return False

class ASSET_OT_powerlib_reload_from_json(Operator):
    bl_idname = "wm.powerlib_reload_from_json"
    bl_label = "Reload from JSON"
    bl_description = ""
    bl_options = {'UNDO', 'REGISTER'}

    @classmethod
    def poll(self, context):
        return True

    def execute(self, context):
        wm = context.window_manager
        wm.powerlib_cols.clear()
        for col_name in asset_categories:
            asset_collection_prop = wm.powerlib_cols.add()
            asset_collection_prop.name = col_name
            for asset_name, asset_def in asset_categories[col_name].items():
                asset_prop = asset_collection_prop.assets.add()
                asset_prop.name = asset_name
                # TODO to be continued
        # todo verify, clear, frees nested, default value for asset active?
        return {'FINISHED'}

class ASSET_OT_powerlib_collection_rename(AssetColRequiredOperator):
    bl_idname = "wm.powerlib_collection_rename"
    bl_label = "Rename Collection"
    bl_description = "Rename the asset collection"
    bl_options = {'UNDO', 'REGISTER'}

    name = StringProperty(name="Name", description="Name of the collection")

    def invoke(self, context, event):
        wm = context.window_manager
        # fill in the field with the current value
        self.name = wm.powerlib_cols[wm.powerlib_active_col].name
        return wm.invoke_props_dialog(self)

    def execute(self, context):
        wm = context.window_manager
        col = wm.powerlib_cols[wm.powerlib_active_col]
        col.name = self.name
        wm.powerlib_active_col = self.name
        return {'FINISHED'}

class ASSET_OT_powerlib_collection_add(Operator):
    bl_idname = "wm.powerlib_collection_add"
    bl_label = "Add Collection"
    bl_description = "Add a new asset collection"
    bl_options = {'UNDO', 'REGISTER'}

    name = StringProperty(name="Name", description="Name of the collection")

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context):
        wm = context.window_manager
        col = wm.powerlib_cols.add()
        col.name = self.name
        wm.powerlib_active_col = self.name
        return {'FINISHED'}

class ASSET_OT_powerlib_collection_del(AssetColRequiredOperator):
    bl_idname = "wm.powerlib_collection_del"
    bl_label = "Delete Collection"
    bl_description = "Delete the selected asset collection"
    bl_options = {'UNDO', 'REGISTER'}

    def execute(self, context):
        wm = context.window_manager
        idx = wm.powerlib_cols.find(wm.powerlib_active_col)
        wm.powerlib_cols.remove(idx)
        wm.powerlib_active_col = ""
        return {'FINISHED'}

class ASSET_OT_powerlib_assetlist_add(AssetColRequiredOperator):
    bl_idname = "wm.powerlib_assetlist_add"
    bl_label = "Add Asset"
    bl_description = "Add a new asset to the selected collection"
    bl_options = {'UNDO', 'REGISTER'}

    def execute(self, context):
        wm = context.window_manager
        col = wm.powerlib_cols[wm.powerlib_active_col]

        asset = col.assets.add()

        # naming
        default_name = "NewAsset"
        if default_name not in col.assets:
            asset.name  = default_name
        else:
            sorted_assets = []
            for a in col.assets:
                if a.name.startswith(default_name+"."):
                    index = a.name[len(default_name)+1:]
                    if index.isdigit():
                        sorted_assets.append(index)
            sorted_assets = sorted(sorted_assets)
            min_index = 1
            for num in sorted_assets:
                num = int(num)
                if min_index < num:
                    break
                min_index = num + 1
            asset.name = "{:s}.{:03d}".format(default_name, min_index)

        # select newly created asset
        col.active_asset = len(col.assets) - 1

        return {'FINISHED'}

class ASSET_OT_powerlib_assetlist_del(ColAndAssetRequiredOperator):
    bl_idname = "wm.powerlib_assetlist_del"
    bl_label = "Delete Asset"
    bl_description = "Delete the selected asset"
    bl_options = {'UNDO', 'REGISTER'}

    def execute(self, context):
        wm = context.window_manager
        col = wm.powerlib_cols[wm.powerlib_active_col]

        col.assets.remove(col.active_asset)

        # change currently active asset
        num_assets = len(col.assets)
        if (col.active_asset > (num_assets - 1) and num_assets > 0):
            col.active_asset = num_assets - 1

        return {'FINISHED'}

# Panel #######################################################################

class ASSET_UL_collection_assets(UIList):
    def draw_item(self, context, layout, data, set, icon, active_data, active_propname, index):
        layout.prop(set, "name", text="", icon='QUESTION', emboss=False)


class ASSET_PT_powerlib(Panel):
    bl_label = 'Powerlib'       # panel section name
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_category = 'Powerlib'    # tab name

    @classmethod
    def poll(cls, context):
        # restrict availability?
        return True #(context.mode == 'OBJECT')

    def draw_header(self, context):
        wm = context.window_manager

        row = self.layout.row(align=True)
        row.prop(wm, "powerlib_is_edit_mode", icon='GREASEPENCIL' if wm.powerlib_is_edit_mode else 'HAND')
        row.operator("wm.powerlib_reload_from_json", text="", icon='FILE_REFRESH')

    def draw(self, context):
        wm = context.window_manager

        layout = self.layout

        # Category selector

        row = layout.row(align=True)
        row.prop_search(
            wm, "powerlib_active_col",# Currently active
            wm, "powerlib_cols",      # Collection to search
            text="", icon="QUESTION"# UI icon and label
        )
        if wm.powerlib_is_edit_mode:
            row.operator("wm.powerlib_collection_rename", text="", icon='OUTLINER_DATA_FONT')
            row.operator("wm.powerlib_collection_add", text="", icon='ZOOMIN')
            row.operator("wm.powerlib_collection_del", text="", icon='ZOOMOUT')

        # UI List with the assets of the selected category

        row = layout.row()
        if (wm.powerlib_active_col):
            asset_collection = wm.powerlib_cols[wm.powerlib_active_col]
            row.template_list(
               "ASSET_UL_collection_assets", "", # type and unique id
                asset_collection, "assets",      # pointer to the CollectionProperty
                asset_collection, "active_asset",# pointer to the active identifier
                rows=14,
            )
            # add/remove/specials UI list Menu
            if wm.powerlib_is_edit_mode:
                col = row.column(align=True)
                col.operator("wm.powerlib_assetlist_add", icon='ZOOMIN', text="")
                col.operator("wm.powerlib_assetlist_del", icon='ZOOMOUT', text="")
                #col.menu("ASSET_MT_powerlib_assetlist_specials", icon='DOWNARROW_HLT', text="")
        else:
            row.enabled = False
            row.label("No Asset Collection Selected")



# Registry ####################################################################

classes = (
    AssetItem,
    AssetCollection,
    ASSET_UL_collection_assets,
    ASSET_PT_powerlib,
    ASSET_OT_powerlib_reload_from_json,
    ASSET_OT_powerlib_collection_rename,
    ASSET_OT_powerlib_collection_add,
    ASSET_OT_powerlib_collection_del,
    ASSET_OT_powerlib_assetlist_add,
    ASSET_OT_powerlib_assetlist_del,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.WindowManager.powerlib_is_edit_mode = BoolProperty(
        name="",
        description="",
        default=False,
    )

    bpy.types.WindowManager.powerlib_cols = CollectionProperty(
        name="Powerlib Add-on ColProperties",
        description="Properties and data used by the Powerlib Add-on",
        type=AssetCollection,
    )

    bpy.types.WindowManager.powerlib_active_col = StringProperty(
        name="",
        description="",
    )
    # could be pointer instead of string?
    #PointerProperty(type=AssetCollection, options={'EDITABLE'}) # needs PROP_EDITABLE but it's not exposed yet?
    # Sev pointed to:
    # https://www.blender.org/api/blender_python_api_current/bpy.types.Property.html#bpy.types.Property.is_readonly


def unregister():

    del bpy.types.WindowManager.powerlib_active_col
    del bpy.types.WindowManager.powerlib_cols
    del bpy.types.WindowManager.powerlib_is_edit_mode

    for cls in classes:
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
