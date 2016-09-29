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

component_type = EnumProperty(
    items=(
        ('INSTANCE_GROUPS', "Instance Groups", ""),
        ('NONINSTANCE_GROUPS', "Non Instance Groups", ""),
        ('GROUP_REFERENCE_OBJECTS', "Group Reference Objects", ""),
        ),
    default='INSTANCE_GROUPS',
    name="Component Type",
    description="",
)


# load single json library file
asset_categories = {}
with open(os.path.join(os.path.dirname(__file__), "lib.json")) as data_file:
    asset_categories = json.load(data_file)


# Data Structure ##############################################################

class AssetItemComponent(PropertyGroup):
    name = StringProperty(
        name="",
        description="",
    )

    filepath = StringProperty(
        name="",
        description="",
        subtype='FILE_PATH',
    )


class AssetItemComponents(PropertyGroup):
    """The components that build an asset (groups, group_reference_objects,
        scripts).
    """
    component_type = component_type

    components = CollectionProperty(
        name='',
        description='',
        type=AssetItemComponent,
    )

    @staticmethod
    def getComponentType(name):
        lookup = {
            'instance_groups': 'INSTANCE_GROUPS',
            'noninstance_groups': 'NONINSTANCE_GROUPS',
            'group_reference_objects': 'GROUP_REFERENCE_OBJECTS',
        }

        value = lookup.get(name)
        if value is None:
            raise Exception("Component type not supported: {0}".format(name))
        return value


class AssetItem(PropertyGroup):
    name = StringProperty(
        name="",
        description="",
    )
    items = CollectionProperty(
        name='',
        type=AssetItemComponents)


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
            and wm.powerlib_collections[wm.powerlib_active_col])


class ColAndAssetRequiredOperator(ColRequiredOperator):
    @classmethod
    def poll(self, context):
        if super().poll(context):
            wm = context.window_manager
            col = wm.powerlib_collections[wm.powerlib_active_col]
            return (col.active_asset < len(col.assets)
                and col.active_asset >= 0)
        return False


class ASSET_OT_powerlib_reload_from_json(Operator):
    bl_idname = "wm.powerlib_reload_from_json"
    bl_label = "Reload from JSON"
    bl_description = "Loads the library from the JSON file. Overrides non saved local edits!"
    bl_options = {'UNDO', 'REGISTER'}

    @classmethod
    def poll(self, context):
        return True

    def execute(self, context):
        wm = context.window_manager
        wm.powerlib_collections.clear()

        # Characters
        for collection_name in asset_categories:
            asset_collection_prop = wm.powerlib_collections.add()
            asset_collection_prop.name = collection_name

            # Boris
            for asset_name, asset_items in asset_categories[collection_name].items():
                asset_prop = asset_collection_prop.assets.add()
                asset_prop.name = asset_name

                # instance_groups
                for item_name, item_components in asset_items.items():
                    item_prop = asset_prop.items.add()
                    item_prop.component_type = item_prop.getComponentType(item_name)

                    # filepath, name
                    for filepath, name in item_components:
                        asset_item = item_prop.components.add()
                        asset_item.name = name
                        asset_item.filepath = filepath

        # todo verify, clear, frees nested, default value for asset active?
        return {'FINISHED'}


class ASSET_OT_powerlib_save_to_json(Operator):
    bl_idname = "wm.powerlib_save_to_json"
    bl_label = "Save to JSON"
    bl_description = "Saves the edited library to the json file. Overrides the previous content!"
    bl_options = {'UNDO', 'REGISTER'}

    @classmethod
    def poll(self, context):
        return True

    def execute(self, context):
        wm = context.window_manager
        with open(os.path.join(
            os.path.dirname(__file__), 'lib.json'), 'w') as data_file:
            collections_json_dict = {}
            # Characters
            for collection in wm.powerlib_collections:
                assets_json_dict = {}

                # Boris
                for asset_name, asset_items in collection.assets.items():
                    assets_json_dict[asset_name] = {}

                    # instance_groups
                    for item_components in asset_items.items:
                        component_type = item_components.component_type.lower()
                        if component_type not in assets_json_dict[asset_name]:
                            assets_json_dict[asset_name][component_type] = []

                        for i in item_components.components:
                            assets_json_dict[asset_name][component_type].append([
                                i.filepath, i.name])
                collections_json_dict[collection.name] = assets_json_dict
            # print(json.dumps(collections_json_dict, indent=4, sort_keys=True,))
            json.dump(collections_json_dict, data_file, indent=4, sort_keys=True,)
        return {'FINISHED'}


class ASSET_OT_powerlib_collection_rename(ColRequiredOperator):
    bl_idname = "wm.powerlib_collection_rename"
    bl_label = "Rename Collection"
    bl_description = "Rename the asset collection"
    bl_options = {'UNDO', 'REGISTER'}

    name = StringProperty(name="Name", description="Name of the collection")

    def invoke(self, context, event):
        wm = context.window_manager
        # fill in the field with the current value
        self.name = wm.powerlib_collections[wm.powerlib_active_col].name
        return wm.invoke_props_dialog(self)

    def execute(self, context):
        wm = context.window_manager
        col = wm.powerlib_collections[wm.powerlib_active_col]
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
        col = wm.powerlib_collections.add()
        col.name = self.name
        wm.powerlib_active_col = self.name
        return {'FINISHED'}


class ASSET_OT_powerlib_collection_del(ColRequiredOperator):
    bl_idname = "wm.powerlib_collection_del"
    bl_label = "Delete Collection"
    bl_description = "Delete the selected asset collection"
    bl_options = {'UNDO', 'REGISTER'}

    def execute(self, context):
        wm = context.window_manager
        idx = wm.powerlib_collections.find(wm.powerlib_active_col)
        wm.powerlib_collections.remove(idx)
        wm.powerlib_active_col = ""
        return {'FINISHED'}


class ASSET_OT_powerlib_assetitem_add(ColRequiredOperator):
    bl_idname = "wm.powerlib_assetitem_add"
    bl_label = "Add Asset"
    bl_description = "Add a new asset to the selected collection"
    bl_options = {'UNDO', 'REGISTER'}

    def execute(self, context):
        wm = context.window_manager
        col = wm.powerlib_collections[wm.powerlib_active_col]

        asset = col.assets.add()

        # naming
        default_name = "NewAsset"
        if default_name not in col.assets:
            asset.name  = default_name
        else:
            sorted_assets = []
            for a in col.assets:
                if a.name.startswith(default_name + "."):
                    index = a.name[len(default_name) + 1:]
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


class ASSET_OT_powerlib_assetitem_del(ColAndAssetRequiredOperator):
    bl_idname = "wm.powerlib_assetitem_del"
    bl_label = "Delete Asset"
    bl_description = "Delete the selected asset"
    bl_options = {'UNDO', 'REGISTER'}

    def execute(self, context):
        wm = context.window_manager
        col = wm.powerlib_collections[wm.powerlib_active_col]

        col.assets.remove(col.active_asset)

        # change currently active asset
        num_assets = len(col.assets)
        if (col.active_asset > (num_assets - 1) and num_assets > 0):
            col.active_asset = num_assets - 1

        return {'FINISHED'}


class ASSET_OT_powerlib_assetitemcomponent_add(ColAndAssetRequiredOperator):
    bl_idname = "wm.powerlib_assetitemcomponent_add"
    bl_label = "Add Asset Component"
    bl_description = "Add a new component to the selected asset"
    bl_options = {'UNDO', 'REGISTER'}

    component_type = component_type

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context):
        wm = context.window_manager
        asset_collection = wm.powerlib_collections[wm.powerlib_active_col]
        active_asset = asset_collection.assets[asset_collection.active_asset]
        item_prop = active_asset.items.add()
        item_prop.component_type = item_prop.getComponentType(self.component_type.lower())
        item_prop.components.add()

        return {'FINISHED'}


class ASSET_OT_powerlib_assetitemcomponent_del(ColAndAssetRequiredOperator):
    bl_idname = "wm.powerlib_assetitemcomponent_del"
    bl_label = "Delete Asset Component"
    bl_description = "Delete the selected asset component"
    bl_options = {'UNDO', 'REGISTER'}

    item_index = IntProperty(
        name="Index in the list",
        default=0,
    )

    def execute(self, context):
        wm = context.window_manager

        asset_collection = wm.powerlib_collections[wm.powerlib_active_col]
        active_asset = asset_collection.assets[asset_collection.active_asset]
        active_asset.items.remove(self.item_index)

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
            wm, "powerlib_collections",      # Collection to search
            text="", icon="QUESTION"# UI icon and label
        )
        if wm.powerlib_is_edit_mode:
            row.operator("wm.powerlib_collection_rename", text="", icon='OUTLINER_DATA_FONT')
            row.operator("wm.powerlib_collection_add", text="", icon='ZOOMIN')
            row.operator("wm.powerlib_collection_del", text="", icon='ZOOMOUT')

        # UI List with the assets of the selected category

        row = layout.row()
        if (wm.powerlib_active_col):
            asset_collection = wm.powerlib_collections[wm.powerlib_active_col]
            row.template_list(
               "ASSET_UL_collection_assets", "", # type and unique id
                asset_collection, "assets",      # pointer to the CollectionProperty
                asset_collection, "active_asset",# pointer to the active identifier
                rows=6,
            )
            # add/remove/specials UI list Menu
            if wm.powerlib_is_edit_mode:
                col = row.column(align=True)
                col.operator("wm.powerlib_assetitem_add", icon='ZOOMIN', text="")
                col.operator("wm.powerlib_assetitem_del", icon='ZOOMOUT', text="")
                #col.menu("ASSET_MT_powerlib_assetlist_specials", icon='DOWNARROW_HLT', text="")
        else:
            row.enabled = False
            row.label("No Asset Collection Selected")

        if (wm.powerlib_active_col) and wm.powerlib_is_edit_mode:
            active_asset = asset_collection.assets[asset_collection.active_asset]
            layout.separator()
            for item_components in active_asset.items:
                row = layout.row()
                row.label(item_components.component_type)
                for idx, i in enumerate(item_components.components):
                    row = layout.row()
                    row.prop(i, "filepath")
                    row.prop(i, "name")
                    op = row.operator("wm.powerlib_assetitemcomponent_del", text="", icon='FILE_REFRESH')
                    op.item_index = idx



        if wm.powerlib_is_edit_mode:
            layout.separator()
            row = layout.row()
            row.operator("wm.powerlib_assetitemcomponent_add", icon='ZOOMIN')
            row = layout.row()
            row.operator("wm.powerlib_save_to_json", icon='FILE_REFRESH')


# Registry ####################################################################

classes = (
    AssetItemComponent,
    AssetItemComponents,
    AssetItem,
    AssetCollection,
    ASSET_UL_collection_assets,
    ASSET_PT_powerlib,
    ASSET_OT_powerlib_reload_from_json,
    ASSET_OT_powerlib_save_to_json,
    ASSET_OT_powerlib_collection_rename,
    ASSET_OT_powerlib_collection_add,
    ASSET_OT_powerlib_collection_del,
    ASSET_OT_powerlib_assetitem_add,
    ASSET_OT_powerlib_assetitem_del,
    ASSET_OT_powerlib_assetitemcomponent_add,
    ASSET_OT_powerlib_assetitemcomponent_del,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.WindowManager.powerlib_is_edit_mode = BoolProperty(
        name="",
        description="",
        default=False,
    )

    bpy.types.WindowManager.powerlib_collections = CollectionProperty(
        name="Powerlib Add-on CollectionProperties",
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
    del bpy.types.WindowManager.powerlib_collections
    del bpy.types.WindowManager.powerlib_is_edit_mode

    for cls in classes:
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
